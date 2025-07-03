from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import time, date
from .models import Employees, TypeShift, PlannedShifts, ChangeReason

class PlannedShiftsModelTest(TestCase):
    def setUp(self):
        # Vytvor zamestnanca
        self.employee = Employees.objects.create_user(
            username='worker1',
            password='testpass123',
            email='worker1@example.com',
            first_name='Meno',
            last_name='Priezvisko',
            personal_number='001',
            role='worker'
        )
        # Vytvor typ smeny
        self.shift_type = TypeShift.objects.create(
            nameShift='Ranna',
            start_time=time(7,0),
            end_time=time(15,0),
            duration_time=8
        )
        # Vytvor dovod zmeny
        self.reason = ChangeReason.objects.create(
            code='SHIFT_CHANGE',
            description='Zmena smeny z dôvodu...'
        )

    def test_save_without_change_reason_raises(self):
        # Vytvor plán smeny
        planned = PlannedShifts.objects.create(
            user=self.employee,
            date=date.today(),
            type_shift=self.shift_type,
            custom_start=time(7,0),
            custom_end=time(15,0),
            change_reason=self.reason
        )

        # Skús zmeniť smenu bez change_reason a očakávaj chybu
        planned.type_shift = None
        planned.change_reason = None
        with self.assertRaises(ValidationError):
            planned.save()

    def test_save_with_change_reason_succeeds(self):
        planned = PlannedShifts.objects.create(
            user=self.employee,
            date=date.today(),
            type_shift=self.shift_type,
            custom_start=time(7,0),
            custom_end=time(15,0),
            change_reason=self.reason
        )
        # Zmeniť typ smeny a nastaviť dovod
        planned.type_shift = None
        planned.change_reason = self.reason
        try:
            planned.save()
        except ValidationError:
            self.fail("Ukladanie s change_reason vyhodilo ValidationError")

    def test_save_new_record_no_change_reason_ok(self):
        # Vytvor nový plán bez zmeny - change_reason môže byť None
        planned = PlannedShifts(
            user=self.employee,
            date=date.today(),
            type_shift=self.shift_type
        )
        try:
            planned.save()
        except ValidationError:
            self.fail("Ukladanie noveho záznamu bez change_reason vyhodilo ValidationError")
