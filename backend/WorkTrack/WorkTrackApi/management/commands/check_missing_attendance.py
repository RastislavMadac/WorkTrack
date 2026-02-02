from django.core.management.base import BaseCommand
from datetime import date
from WorkTrackApi.models import PlannedShifts, Attendance

class Command(BaseCommand):
    help = "Spracuje minulé smeny: Dovolenky/PN potvrdí, Absencie označí na schválenie"

    def handle(self, *args, **kwargs):
        today = date.today()

        # Nájdeme kandidátov (Staršie ako dnes, neskryté, bez zmeny)
        planned_shifts = PlannedShifts.objects.filter(
            date__lt=today,
            hidden=False,
            is_changed=False,
            transferred=False 
        )

        count_absences = 0
        count_auto_created = 0

        for shift in planned_shifts:
            # Hľadáme dochádzku k tejto smene
            exists = Attendance.objects.filter(planned_shift=shift).exists()

            if not exists:
                # =========================================================
                # SCENÁR A: Je to DOVOLENKA (21) alebo PN (23)?
                # -> Automaticky vytvoríme Attendance (potvrdenie čerpania)
                # =========================================================
                if shift.type_shift.id in [21, 23]:
                    Attendance.objects.create(
                        user=shift.user,
                        date=shift.date,
                        planned_shift=shift,
                        type_shift=shift.type_shift,
                        # Predpokladáme, že plán má vyplnené časy. 
                        # Ak nie, treba tu dať fallback (napr. 08:00 - 16:00)
                        custom_start=shift.custom_start, 
                        custom_end=shift.custom_end,
                        calendar_day=shift.calendar_day,
                        note="Automaticky potvrdené systémom (Plánované voľno)"
                    )
                    count_auto_created += 1
                    self.stdout.write(f"✅ {shift.user} {shift.date} – Vytvorená dochádzka ({shift.type_shift.nameShift})")

                # =========================================================
                # SCENÁR B: Bežná smena bez dochádzky (Absencia)
                # -> Skryjeme, nastavíme is_changed, ale NEZADÁME dôvod
                # =========================================================
                else:
                    shift.is_changed = True
                    shift.hidden = True          # Skryjeme z výpočtov
                    
                    shift.change_reason = None   # Dôvod musí zadať človek
                    shift.approval_status = 'pending' # Svieti na Dashboarde
                    
                    shift.note = "⚠️ Chýbajúca dochádzka - Nutné zadať dôvod!"
                    
                    shift.save(update_fields=[
                        "is_changed", "hidden", "change_reason", 
                        "approval_status", "note"
                    ])
                    
                    count_absences += 1
                    self.stdout.write(f"❗ {shift.user} {shift.date} – Čaká na manažéra (Dôvod nezadaný)")

        # Finálny výpis
        self.stdout.write(self.style.SUCCESS(
            f"HOTOVO:\n"
            f" - Automaticky potvrdené (Dovolenka/PN): {count_auto_created}\n"
            f" - Vyžaduje zásah manažéra (Absencie): {count_absences}"
        ))