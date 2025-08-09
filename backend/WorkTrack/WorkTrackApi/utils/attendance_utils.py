# utils/attendance_utils.py

from datetime import datetime, timedelta, time
from django.core.exceptions import ValidationError


def prevziat_smenu_logic(request_user, target_shift_id, user_id=None, note=None):
    from WorkTrackApi.models import PlannedShifts, Attendance, Employees
    try:
        target_shift = PlannedShifts.objects.get(pk=target_shift_id)
    except PlannedShifts.DoesNotExist:
        return None, "Plánovaná smena neexistuje."

    # Určíme používateľa, ktorý preberá smenu
    if request_user.role in ['admin', 'manager'] and user_id:
        try:
            user_to_assign = Employees.objects.get(pk=user_id)
        except Employees.DoesNotExist:
            return None, "Používateľ neexistuje."
    else:
        user_to_assign = request_user

    attendance = Attendance.objects.create(
        user=user_to_assign,
        date=target_shift.date,
        type_shift=target_shift.type_shift,
        custom_start=target_shift.custom_start,
        custom_end=target_shift.custom_end,
        note=note or f"Preberám smenu od {target_shift.user}",
    )

    # Tu voláme metódy podľa tvojho modelu
    attendance.exchange_shift(target_shift)
    attendance.create_planned_shift(attendance)

    return attendance, None

def create_attendance_from_planned_shift(user, date, planned_shift_id):
    from WorkTrackApi.models import PlannedShifts, Attendance
    """
    Vytvorí Attendance pre daného používateľa a dátum na základe plánovanej smeny.

    Args:
        user: používateľ (zamestnanec)
        date: dátum (datetime.date alebo string YYYY-MM-DD)
        planned_shift_id: ID plánovanej smeny, ktorú má použiť

    Returns:
        attendance objekt, alebo None ak sa nenašla platná plánovaná smena
    """

    planned_shift = PlannedShifts.objects.filter(
        id=planned_shift_id,
        user=user,
        date=date,
        hidden=False,
    ).first()

    if not planned_shift:
        return None

    attendance = Attendance.objects.create(
        user=user,
        date=planned_shift.date,
        custom_start=planned_shift.custom_start,
        custom_end=planned_shift.custom_end,
        type_shift=planned_shift.type_shift,
        planned_shift=planned_shift,
        note=planned_shift.note or "Vytvorená dochácka na základe plôanovanej smeny",
    )
    return attendance

def round_to_nearest_half_hour(t: time) -> time:
    """
    Zaokrúhli čas na najbližšiu polhodinu (nahor alebo nadol).
    """
    dt = datetime.combine(datetime.today(), t)
    minute = dt.minute
    down = minute % 30
    up = 30 - down

    if down < up:
        dt_rounded = dt - timedelta(minutes=down)
    else:
        dt_rounded = dt + timedelta(minutes=up)

    return dt_rounded.time()


def create_extra_attendance(user, date, start, end, reason=""):
    from WorkTrackApi.models import Attendance, TypeShift  # ⬅ LAZY IMPORT

    """
    Vytvorí nový Attendance záznam mimo plánovanej smeny.
    Používa TypeShift s ID=22 (extra smena).
    """
    extra_shift_type = TypeShift.objects.get(id=22)
    att = Attendance(
        user=user,
        date=date,
        custom_start=start,
        custom_end=end,
        type_shift=extra_shift_type,
        note=reason or "Automatický záznam mimo plán"
    )
    att.save(skip_extra_attendance=True)
    return att




def reset_auto_changed_attendance(user, target_date):
    from WorkTrackApi.models import PlannedShifts  # ⬅ LAZY IMPORT
    """
    Vyčistí automaticky generované záznamy v PlannedShifts.
    Týka sa len tých, ktoré obsahujú poznámku "Chýbajúca dochádzka k plánovanej smene"
    """
    auto_records = PlannedShifts.objects.filter(
        user=user,
        date=target_date,
        hidden=False,
        is_changed=True,
        note__icontains="Chýbajúca dochádzka k plánovanej smene"
    )
    updated_count = auto_records.update(is_changed=False, note="")
    print(f"🔁 Resetovaných {updated_count} automatických záznamov.")
"""vytvarame json na vytvorenie plannedshift s nocnou smenou """

def handle_night_shift(attendance):
    from WorkTrackApi.models import Attendance  # ⬅ LAZY IMPORT
    """
    POUZIVA SA
    Rozdelí nočnú 12h smenu (21:00–09:00) na dve časti:
    - dnes: 21:00–00:00 (koniec = 0:00)
    - zajtra: 00:00–09:00 (nový Attendance)
    Používa sa iba pre typ smeny ID=20.
    """
    if attendance.type_shift and attendance.type_shift.id == 20:
        attendance.custom_end = time(0, 0)
        attendance.save()

        next_day = attendance.date + timedelta(days=1)

        Attendance.objects.create(
            user=attendance.user,
            date=next_day,
            type_shift=attendance.type_shift,
            custom_start=time(0, 0),
            custom_end=time(9, 0),
            note="Pokračovanie nočnej smeny"
        )
        print(f"🌙 Nočná smena rozdelená pre {attendance.user}")


def add_calendar_day(attendance):
    from WorkTrackApi.models import CalendarDay  # ⬅ LAZY IMPORT
    """
    Priradí k Attendance objektu záznam z CalendarDay podľa dátumu.
    Používa sa ak calendar_day ešte nie je nastavený.
    """
    if not attendance.calendar_day:
        cal = CalendarDay.objects.filter(date=attendance.date).first()
        if cal:
            attendance.calendar_day = cal


# WorkTrackApi/utils/attendance_utils.py

def handle_any_shift_time(attendance_instance):
    from WorkTrackApi.models import Attendance, PlannedShifts, TypeShift, ChangeReason

    try:
        change_reason_obj = ChangeReason.objects.filter(category="cdr").first()
        if not change_reason_obj:
            print("⚠️ Chýba ChangeReason pre 'cdr'")

        plan = PlannedShifts.objects.filter(
            user=attendance_instance.user,
            date=attendance_instance.date,
            hidden=False
        ).first()

        if not plan:
            print("⚠️ Nenájdená plánovaná smena pre daný deň a užívateľa")
            return

        type_shift_extra = TypeShift.objects.get(id=22)  # "extra" zmena

        # --- Skorší príchod ---
        if attendance_instance.custom_start and attendance_instance.custom_start < plan.custom_start:
            start = attendance_instance.custom_start
            end = plan.custom_start

            if not PlannedShifts.objects.filter(
                user=plan.user, date=plan.date,
                custom_start=start, custom_end=end,
                type_shift=type_shift_extra
            ).exists():
                new_plan = PlannedShifts.objects.create(
                    user=plan.user,
                    date=plan.date,
                    custom_start=start,
                    custom_end=end,
                    type_shift=type_shift_extra,
                    transferred=True,
                    is_changed=True,
                    change_reason=change_reason_obj,
                    note="Skorší príchod - extra čas"
                )
                print(f"🟢 Vytvorený extra plán: {start} - {end}")

                Attendance.objects.create(
                    user=plan.user,
                    date=plan.date,
                    planned_shift=new_plan,
                    custom_start=start,
                    custom_end=end,
                    type_shift=type_shift_extra,
                    note="Automaticky vytvorený skorší príchod"
                )
                print(f"🟢 Vytvorený extra attendance: {start} - {end}")

        # --- Neskorší odchod ---
        if attendance_instance.custom_end and attendance_instance.custom_end > plan.custom_end:
            start = plan.custom_end
            end = attendance_instance.custom_end

            if not PlannedShifts.objects.filter(
                user=plan.user, date=plan.date,
                custom_start=start, custom_end=end,
                type_shift=type_shift_extra
            ).exists():
                new_plan = PlannedShifts.objects.create(
                    user=plan.user,
                    date=plan.date,
                    custom_start=start,
                    custom_end=end,
                    type_shift=type_shift_extra,
                    transferred=True,
                    is_changed=True,
                    change_reason=change_reason_obj,
                    note="Neskorší odchod - extra čas"
                )
                print(f"🟢 Vytvorený extra plán: {start} - {end}")

                Attendance.objects.create(
                    user=plan.user,
                    date=plan.date,
                    planned_shift=new_plan,
                    custom_start=start,
                    custom_end=end,
                    type_shift=type_shift_extra,
                    note="Automaticky vytvorený neskorší odchod"
                )
                print(f"🟢 Vytvorený extra attendance: {start} - {end}")

        # ** Nepretriedzujem hlavný attendance späť na pôvodný plánovaný čas **
        # pretože to často spôsobuje nežiaduce prepisovanie údajov

    except Exception as e:
        print(f"🛑 Chyba v handle_any_shift_time: {e}")


def handle_start_shift_time(attendance_instance):
    from WorkTrackApi.models import PlannedShifts, Attendance, TypeShift

    # Nájde pôvodnú plánovanú smenu
    planned_shift = PlannedShifts.objects.filter(
        hidden=False,
        user=attendance_instance.user,
        date=attendance_instance.date
    ).order_by("custom_end").first()

    if not planned_shift:
        print("❌ Žiadna plánovaná smena")
        return

    print(f"DEBUG: Attendance start={attendance_instance.custom_start}, PlannedShift start={planned_shift.custom_start}")

    # Ak sa začiatok líši od plánovanej smeny → vytvoríme novú smenu pre skorší čas
    if attendance_instance.custom_start and attendance_instance.custom_start != planned_shift.custom_start:
        try:
            type_shift_obj = TypeShift.objects.get(id=22)
        except TypeShift.DoesNotExist:
            print("⚠️ Typ smeny (id=22) neexistuje!")
            return

        # Overíme, či podobná neplánovaná smena už neexistuje
        if PlannedShifts.objects.filter(
            user=attendance_instance.user,
            date=attendance_instance.date,
            custom_start=attendance_instance.custom_start,
            custom_end=planned_shift.custom_start,
            type_shift=type_shift_obj
        ).exists():
            print("⚠️ Podobná neplánovaná smena už existuje – preskakujem.")
            return

        print(f"🟢 Vytváram PlannedShift {attendance_instance.custom_start} - {planned_shift.custom_start}")

        # 1️⃣ Vytvor novú PlannedShift
        new_planned_shift = PlannedShifts.objects.create(
            user=attendance_instance.user,
            date=attendance_instance.date,
            custom_start=attendance_instance.custom_start,
            custom_end=planned_shift.custom_start,
            type_shift=type_shift_obj,
            transferred=True,
            is_changed=True,
            note="⚠️ Neplánovaná zmena času – treba zadať dôvod!",
            calendar_day=planned_shift.calendar_day,
        )

        # 2️⃣ Vytvor k nej Attendance
        Attendance.objects.create(
            user=attendance_instance.user,
            date=attendance_instance.date,
            planned_shift=new_planned_shift,  # <- priradené ID
            custom_start=new_planned_shift.custom_start,
            custom_end=new_planned_shift.custom_end,
            type_shift=type_shift_obj,
            note="✅ Automaticky vytvorené pre skorší príchod",
            calendar_day=new_planned_shift.calendar_day,
        )

        print(f"✅ Vytvorený nový Attendance pre {attendance_instance.custom_start} - {planned_shift.custom_start}")

    else:
        print("ℹ️ Začiatok smeny sa nelíši – nič netvorím.")


"""IDEME TERAZ ROBIT NOCNU SMENU CREATE"""

def handle_end_shift_time(attendance_instance):
    from WorkTrackApi.models import PlannedShifts, Attendance, TypeShift

    planned_shift = PlannedShifts.objects.filter(
        hidden=False,
        user=attendance_instance.user,
        date=attendance_instance.date
    ).order_by("-custom_start").first()  # Dôležité: najneskorší začiatok

    if not planned_shift:
        print("❌ Žiadna plánovaná smena")
        return

    print(f"DEBUG: Attendance end={attendance_instance.custom_end}, PlannedShift end={planned_shift.custom_end}")

    # Pridali sme podmienku, že custom_end musí byť väčší (neskorší) než plánovaný koniec
    if attendance_instance.custom_end and attendance_instance.custom_end != planned_shift.custom_end and attendance_instance.custom_end > planned_shift.custom_end:
        try:
            type_shift_obj = TypeShift.objects.get(id=22)
        except TypeShift.DoesNotExist:
            print("⚠️ Typ smeny (id=22) neexistuje!")
            return

        if PlannedShifts.objects.filter(
            user=attendance_instance.user,
            date=attendance_instance.date,
            custom_start=planned_shift.custom_end,
            custom_end=attendance_instance.custom_end,
            type_shift=type_shift_obj
        ).exists():
            print("⚠️ Podobná neplánovaná smena už existuje – preskakujem.")
            return

        print(f"🟢 Vytváram PlannedShift {planned_shift.custom_end} - {attendance_instance.custom_end}")

        new_planned_shift = PlannedShifts.objects.create(
            user=attendance_instance.user,
            date=attendance_instance.date,
            custom_start=planned_shift.custom_end,
            custom_end=attendance_instance.custom_end,
            type_shift=type_shift_obj,
            transferred=True,
            is_changed=True,
            note="⚠️ Neplánovaná zmena času – treba zadať dôvod!",
            calendar_day=planned_shift.calendar_day,
        )

        Attendance.objects.create(
            user=attendance_instance.user,
            date=attendance_instance.date,
            planned_shift=new_planned_shift,
            custom_start=new_planned_shift.custom_start,
            custom_end=new_planned_shift.custom_end,
            type_shift=type_shift_obj,
            note="✅ Automaticky vytvorené pre neskorší odchod",
            calendar_day=new_planned_shift.calendar_day,
        )

        # ✅ Odstránili sme aktualizáciu hlavného Attendance späť na pôvodný čas

        print(f"✅ Vytvorený nový Attendance pre {planned_shift.custom_end} - {attendance_instance.custom_end}")

    else:
        print("ℹ️ Koniec smeny sa nelíši alebo je skôr – nič netvorím.")

       


def exchange_shift_logic(attendance, target_shift):
    """
    Vykoná výmenu smeny medzi dvoma zamestnancami:
    - vytvorí nový záznam pre zamestnanca, ktorý preberá smenu
    - skryje pôvodnú smenu kolegu
    - zapíše odkaz na výmenu do attendance.exchanged_with
    """
    from WorkTrackApi.models import PlannedShifts
    from django.core.exceptions import ValidationError

    if not target_shift:
        raise ValidationError("Nebola vybraná smena na výmenu.")

    if attendance.user == target_shift.user:
        raise ValidationError("Nemôžeš si vymeniť smenu sám so sebou.")

    if attendance.date != target_shift.date or attendance.type_shift != target_shift.type_shift:
        raise ValidationError("Smena na výmenu musí byť rovnakého typu a dňa.")

    new_shift = PlannedShifts.objects.create(
        user=attendance.user,
        date=attendance.date,
        type_shift=attendance.type_shift,
        custom_start=attendance.custom_start,
        custom_end=attendance.custom_end,
        transferred=True,
        is_changed=True,
        note=f"Pozor Výmena smeny s {target_shift.user} – treba zadať dôvod"
    )

    # Skryj pôvodnú smenu kolegu
    target_shift.hidden = True
    target_shift.save(update_fields=["hidden"])

    # Priraď novú smenu do exchanged_with
    attendance.exchanged_with = new_shift
    attendance.save()

    print(f"🔁 Výmena smeny: {attendance.user} ↔ {target_shift.user}")




def split_night_planned_shift(planned_shift):
    """
    Rozdelí nočnú smenu (napr. 21:00 - 09:00 ďalšieho dňa) na dve PlannedShifts:
    - Prvá časť: pôvodný deň, od custom_start do polnoci (00:00)
    - Druhá časť: nasledujúci deň, od 00:00 do custom_end

    Predpoklad: nočná smena má typ_shift_id = 20.
    """

    # Overenie, či ide o nočnú smenu
    if planned_shift.type_shift_id != 20:
        return  # Nie je nočná smena, nič nerobíme

    start = planned_shift.custom_start
    end = planned_shift.custom_end
    date = planned_shift.date

    # Kontrola, či smena prekračuje polnoc (custom_end menší ako custom_start)
    if end > start:
        # Smena neprekračuje polnoc, nič nedelíme
        return

    # 1) Prvá časť: od start do polnoci (00:00) na pôvodný dátum
    midnight = time(0, 0)

    planned_shift.custom_end = midnight
    planned_shift.save()

    # 2) Druhá časť: od polnoci do end na ďalší deň
    next_day = date + timedelta(days=1)

    from WorkTrackApi.models import PlannedShifts

    # Skontroluj, či už druhá časť neexistuje (aby sa nevytvárali duplicity)
    exists = PlannedShifts.objects.filter(
        user=planned_shift.user,
        date=next_day,
        custom_start=midnight,
        custom_end=end,
        type_shift=planned_shift.type_shift,
        hidden=False,
    ).exists()

    if exists:
        return  # Už existuje, nevytváraj duplikát

    PlannedShifts.objects.create(
        user=planned_shift.user,
        date=next_day,
        custom_start=midnight,
        custom_end=end,
        type_shift=planned_shift.type_shift,
        transferred=planned_shift.transferred,
        is_changed=planned_shift.is_changed,
        note=f"{planned_shift.note} (rozdelená nočná smena)",
        calendar_day=None,  # prípadne priradiť kalendárny deň podľa next_day
        hidden=False,
    )
