from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Attendance, PlannedShifts, ChangeReason


@receiver(post_save, sender=Attendance)
def mark_planned_shift_transferred_on_save(sender, instance, created, **kwargs):
    """
    Ak sa vytvorí nový záznam dochádzky,
    nastaví `transferred = True` v súvisiacej plánovanej smene (ak existuje).
    """
    if not created:
        return  # nerob nič pri úprave záznamu

    planned = PlannedShifts.objects.filter(user=instance.user, date=instance.date).first()
    if planned and not planned.transferred:
        planned.transferred = True
        planned.save(update_fields=["transferred"])
        print(f"🟢 Prenos aktivovaný: transferred=True pre {instance.user} {instance.date}")



@receiver(post_delete, sender=Attendance)
def unmark_planned_shift_transferred_on_delete(sender, instance, **kwargs):
    """
    Ak sa zmaže dochádzka a žiadna ďalšia na daný deň pre daného používateľa neexistuje,
    nastaví `transferred = False` v plánovanej smene.
    """
    if not Attendance.objects.filter(user=instance.user, date=instance.date).exists():
        planned_shifts = PlannedShifts.objects.filter(user=instance.user, date=instance.date)
        for planned in planned_shifts:
            if planned.transferred:
                planned.transferred = False
                planned.save(update_fields=["transferred"])
                print(f"🔴 Prenos zrušený: transferred=False pre {instance.user} {instance.date}")
