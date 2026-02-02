from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Attendance, PlannedShifts, ChangeReason
from rest_framework.authtoken.models import Token
from django.conf import settings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

@receiver(post_save, sender=Attendance)
def mark_planned_shift_transferred_on_save(sender, instance, created, **kwargs):
    if created:
        planned = instance.planned_shift
        if planned and not planned.transferred:
            planned.transferred = True
            planned.save(update_fields=['transferred'])

@receiver(post_delete, sender=Attendance)
def unmark_planned_shift_transferred_on_delete(sender, instance, **kwargs):
    if not Attendance.objects.filter(user=instance.user, date=instance.date).exists():
        planned = instance.planned_shift
        if planned and planned.transferred:
            planned.transferred = False
            planned.note=""
            planned.save(update_fields=['transferred','note'])
@receiver(post_save, sender=Attendance)
def mark_planned_shift_transferred_on_save(sender, instance, created, **kwargs):
    """
    Keď sa vytvorí/upraví dochádzka, označí priradenú plánovanú smenu ako 'transferred' (odrobenú).
    """
    if created:
        planned = instance.planned_shift
        if planned and not planned.transferred:
            planned.transferred = True
            planned.save(update_fields=['transferred'])

@receiver(post_delete, sender=Attendance)
def handle_planned_shift_on_delete(sender, instance, **kwargs):
    
    """
    Rieši čo sa stane s Plánom, keď sa vymaže Dochádzka.
    """
    planned = instance.planned_shift
    
    if not planned:
        return

    # 1. SCENÁR: Zmazanie EXTRA smeny (ID 22)
    # Ak bola dochádzka naviazaná na "Innú činnosť" (ID 22), ktorá vznikla automaticky,
    # chceme zmazať aj ten plán, aby tam neostalo "smeti".
    if planned.type_shift and planned.type_shift.id == 22:
        print(f"🗑️ Zmazaná automatická extra smena {planned.id} po zmazaní dochádzky.")
        planned.delete() # Úplné vymazanie z DB
        return

    # 2. SCENÁR: Zmazanie BEŽNEJ smeny (napr. ID 15, 20...)
    # Ak sme zmazali dochádzku k bežnej smene, chceme smenu len "odznačiť" (transferred = False),
    # aby svietila, že ju treba znova odrobiť.
    # Kontrolujeme, či k tomuto plánu neexistuje ešte iná dochádzka (napr. pri duplicite).
    if not Attendance.objects.filter(planned_shift=planned).exists():
        if planned.transferred:
            planned.transferred = False
            # Nemazeme 'note', lebo tam moze byt dolezita poznamka od managera
            planned.save(update_fields=['transferred'])
            print(f"backtrack: Plánovaná smena {planned.id} vrátená do stavu transferred=False")






from django.utils import timezone
from .models import Employees

@receiver(post_save, sender=Employees)
def cleanup_future_shifts_on_deactivation(sender, instance, created, **kwargs):
    """
    Spustí sa automaticky po každom uložení modelu Employees.
    Ak je zamestnanec nastavený na is_active=False, zmaže jeho budúce smeny.
    """
    # Kontrolujeme, či je zamestnanec neaktívny
    if not instance.is_active:
        today = timezone.now().date()
        
        # Nájdeme všetky smeny, ktoré sú v budúcnosti (od zajtra)
        # Dnešok necháme tak, ak by náhodou ešte pracoval
        future_shifts = PlannedShifts.objects.filter(
            user=instance,
            date__gt=today
        )
        
        count = future_shifts.count()
        
        if count > 0:
            # --- MOŽNOSŤ A: ÚPLNÉ ZMAZANIE (Odporúčané) ---
            future_shifts.delete()
            print(f"🧹 SIGNAL: Zamestnanec {instance} deaktivovaný. Zmazaných {count} budúcich smien.")

            # --- MOŽNOSŤ B: LEN SKRYTIE (Alternatíva) ---
            # Ak si chcete nechať históriu, že "mal mať smenu", ale zrušila sa:
            # future_shifts.update(
            #     hidden=True, 
            #     is_changed=True, 
            #     note="ZRUŠENÉ: Zamestnanec deaktivovaný"
            # )
            # print(f"🙈 SIGNAL: Skrytých {count} budúcich smien pre {instance}.")