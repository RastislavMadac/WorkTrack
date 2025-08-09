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
