from django.core.management.base import BaseCommand
from datetime import date
from WorkTrackApi.models import PlannedShifts, Attendance

class Command(BaseCommand):
    help = "Označí plánované smeny bez dochádzky ako zmenené"

    def handle(self, *args, **kwargs):
        today = date.today()

        planned_shifts = PlannedShifts.objects.filter(
            date__lt=today,
            hidden=False,
            is_changed=False,
            transferred=False
        )

        count = 0

        for shift in planned_shifts:
            exists = Attendance.objects.filter(
                user=shift.user,
                date=shift.date,
                custom_start=shift.custom_start
            ).exists()

            if not exists:
                shift.is_changed = True
                shift.note = "Chýbajúca dochádzka k plánovanej smene"
                shift.save(update_fields=["is_changed", "note"])
                count += 1
                self.stdout.write(f"❗ {shift.user} {shift.date} – chýbajúca dochádzka")

        self.stdout.write(self.style.SUCCESS(f"Označených {count} smien ako is_changed=True"))
