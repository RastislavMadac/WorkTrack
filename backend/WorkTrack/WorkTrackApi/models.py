from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from decimal import Decimal
from datetime import date, datetime, timedelta, time
import threading
import calendar
from .utils.attendance_utils import (
    round_to_nearest_half_hour
)

_thread_locals = threading.local()

def set_force_shift_times(value: bool):
    _thread_locals.force_shift_times = value

def get_force_shift_times():
    return getattr(_thread_locals, 'force_shift_times', False)
class Employees(AbstractUser):
    personal_number=models.CharField(max_length=3, 
                                     unique=True,
                                     validators=[RegexValidator(
                                         regex=r'^\d{3}$', message='Osobné číslo musí mať presne 3 číslice (napr. 001, 123).'
                                     )])
    
    ROLE_CHOICES=[
         ('admin', 'Administrátor' ),
        ('manager', 'Manažér'),
        ('worker', 'Zamestnanec'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')

    

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'personal_number']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.personal_number})"

"""VYTVORIT PODMINKU AK PLANUJEM SMENU NADAJU SA MENIT CASY"""

class TypeShift(models.Model):
    nameShift = models.CharField(max_length=50)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    duration_time = models.DecimalField(
        null=True, blank=True,
        max_digits=4, decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.5"), message="Trvanie musí byť aspoň 0.5 hodiny"),
            MaxValueValidator(Decimal("24.0"), message="Trvanie nemôže byť viac ako 24 hodín")
        ]
    )
    
    allow_variable_time = models.BooleanField(
        default=False,
        help_text="Ak je zapnuté, zamestnanec môže prísť a odísť kedykoľvek (napr. flexibilná smena)."
    )
    shortName = models.CharField(max_length=2,default="ds")
    def __str__(self):
        return self.nameShift

    def clean(self):
        # povinné len ak nejde o typ s id=22 (alebo ešte neexistuje a nameShift nie je špeciálne)
        if self.id != 22:
            missing = []
            if not self.start_time:
                missing.append("start_time")
            if not self.end_time:
                missing.append("end_time")
            if not self.duration_time:
                missing.append("duration_time")
            if missing:
                raise ValidationError(f"Tieto polia sú povinné pre túto smenu: {', '.join(missing)}")

    def save(self, *args, **kwargs):
        self.full_clean()  # spustí clean() pred uložením

         # prepočítavaj iba pre typ smeny s ID 22
        if self.pk == 22:  
            start_dt = datetime.combine(datetime.today(), self.start_time)
            end_dt = datetime.combine(datetime.today(), self.end_time)

            # ak smena ide cez polnoc (napr. 22:00 → 06:00)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            duration = end_dt - start_dt
            total_minutes = duration.seconds // 60
            h = total_minutes // 60
            m = total_minutes % 60

            self.duration_time = f"{h:02d}:{m:02d}"

        super().save(*args, **kwargs)

"""emploee time at work"""
class Attendance(models.Model):
    user= models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)
    type_shift= models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    planned_shift = models.ForeignKey('WorkTrackApi.PlannedShifts',
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    help_text="Vybraná plánovaná smena, z ktorej sa preberajú časy",
    related_name="attendances_as_planned"
)

    custom_start= models.TimeField(null=True, blank=True)
    custom_end= models.TimeField(null=True,blank=True)
    note= models.TextField(blank=True)
    exchanged_with = models.ForeignKey('WorkTrackApi.PlannedShifts',                   
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                help_text="Pôvodná smena kolegu, ktorú zamestnanec prebral",
                related_name="attendances_as_exchanged_with"
            )

    
    calendar_day = models.ForeignKey('WorkTrackApi.CalendarDay', on_delete=models.CASCADE, related_name="attendances",null=True, blank=True)

    class Meta:
            unique_together = ('user', 'date', 'custom_start', 'custom_end')
            ordering = ['date', 'user']

    def __str__(self):
        return f"{self.user} - {self.date} ({self.custom_start} - {self.custom_end})"


    def save(self, *args, **kwargs):
        # Pri update aktualizuj calendar_day, ak sa mení dátum
        if self.pk:
            orig_attendance = Attendance.objects.get(pk=self.pk)

            if self.date != orig_attendance.date:
                try:
                    self.calendar_day = CalendarDay.objects.get(date=self.date)
                except CalendarDay.DoesNotExist:
                    raise ValidationError(f"Pre dátum {self.date} neexistuje CalendarDay.")
        else:
            # Pri vytváraní nastav calendar_day podľa dátumu
            if self.date and not self.calendar_day:
                try:
                    self.calendar_day = CalendarDay.objects.get(date=self.date)
                except CalendarDay.DoesNotExist:
                    raise ValidationError(f"CalendarDay pre dátum {self.date} neexistuje.")

        # Ak attendance nemá custom časy, môžeš ich nastaviť podľa type_shift (ak existuje)
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

        # Validácia časov custom_start a custom_end
        if self.custom_start and self.custom_end:
            start = datetime.combine(date.today(), self.custom_start)
            end = datetime.combine(date.today(), self.custom_end)
            if end <= start:
                end += timedelta(days=1)
                if end <= start:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")

        super().save(*args, **kwargs)
       

   
    

"""Change reason"""
class ChangeReason(models.Model):
    CATEGORY_CHOICES = [
        ('absence', 'Neprítomnosť / zmena rozpisu'),
        ('cdr', 'Iná činnosť zamestnanca '),
    ]

    name = models.CharField(max_length=255, default="Dôvod nezadaný")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    def __str__(self):
        return self.name
    

"""planned shifts"""


# class PlannedShifts(models.Model):
#     user = models.ForeignKey(Employees, on_delete=models.CASCADE,related_name='planned_shifts')
#     date = models.DateField(null=True, blank=True)
#     type_shift = models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
#     custom_start = models.TimeField(null=True, blank=True)
#     custom_end = models.TimeField(null=True, blank=True)
#     note = models.TextField(blank=True)
#     transferred = models.BooleanField(default=False)
#     is_changed = models.BooleanField(default=False)
#     hidden = models.BooleanField(default=False)
#     change_reason = models.ForeignKey('WorkTrackApi.ChangeReason',on_delete=models.CASCADE, related_name="change_reason", blank=True, null=True)
#     calendar_day = models.ForeignKey('WorkTrackApi.CalendarDay', on_delete=models.CASCADE, related_name="calendar_day",null=True, blank=True)
   
#     class Meta:
#       unique_together = ('user', 'date', 'custom_start', 'custom_end')

#     def __str__(self):
#         return f"{self.user} {self.type_shift}"
#NOTE - nEW
class PlannedShifts(models.Model):
    user = models.ForeignKey('WorkTrackApi.Employees', on_delete=models.CASCADE, related_name='planned_shifts')
    date = models.DateField(null=True, blank=True)
    type_shift = models.ForeignKey('WorkTrackApi.TypeShift', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Časy smeny (ak sa líšia od defaultu v type_shift)
    custom_start = models.TimeField(null=True, blank=True)
    custom_end = models.TimeField(null=True, blank=True)
    
    note = models.TextField(blank=True)
    
    # Stavové polia
    transferred = models.BooleanField(default=False) # Či už bola preklopená do dochádzky
    is_changed = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False) # Soft delete
    
    change_reason = models.ForeignKey('WorkTrackApi.ChangeReason', on_delete=models.CASCADE, related_name="change_reason", blank=True, null=True)
    calendar_day = models.ForeignKey('WorkTrackApi.CalendarDay', on_delete=models.CASCADE, related_name="planned_calendar_day", null=True, blank=True)
   
    class Meta:
        # Povolíme viac záznamov na deň? Ak nie, nechaj toto. 
        # Ak chceš, aby mal rannú a potom nočnú v ten istý deň, toto treba zmazať.
        unique_together = ('user', 'date', 'custom_start', 'custom_end')

    def __str__(self):
        return f"{self.user} - {self.date} ({self.type_shift})"

    def save(self, *args, **kwargs):
        # Automatické priradenie CalendarDay podľa dátumu
        if self.date and not self.calendar_day:
            from WorkTrackApi.models import CalendarDay
            try:
                self.calendar_day = CalendarDay.objects.get(date=self.date)
            except CalendarDay.DoesNotExist:
                pass # Alebo raise ValidationError
        super().save(*args, **kwargs) 



class CalendarDay(models.Model):
    date = models.DateField(unique=True)
    day = models.CharField(max_length=20)
    is_weekend = models.BooleanField(default=False)
    is_holiday = models.BooleanField(default=False)
    holiday_name = models.CharField(max_length=100, blank=True, null=True)  

    def __str__(self):
        return f"{self.date} ({self.day})"

    @staticmethod
    def get_easter_sunday(year):
        "Výpočet dátumu Veľkonočnej nedele podľa algoritmu (Computus)"
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    @staticmethod
    def get_slovak_holidays(year):
        "Vráti zoznam sviatkov vo forme [(dátum, názov)]"
        fixed = [
            (1, 1, "Deň vzniku SR"),
            (1, 6, "Zjavenie Pána"),
            (5, 1, "Sviatok práce"),
            (5, 8, "Deň víťazstva nad fašizmom"),
            (7, 5, "Sviatok sv. Cyrila a Metoda"),
            (8, 29, "Výročie SNP"),
            (9, 1, "Deň Ústavy SR"),
            (9, 15, "Sedembolestná Panna Mária"),
            (11, 1, "Sviatok všetkých svätých"),
            (11, 17, "Deň boja za slobodu a demokraciu"),
            (12, 24, "Štedrý deň"),
            (12, 25, "1. sviatok vianočný"),
            (12, 26, "2. sviatok vianočný"),
        ]
        movable = []
        easter = CalendarDay.get_easter_sunday(year)
        movable.append((easter - timedelta(days=2), "Veľký piatok"))
        movable.append((easter + timedelta(days=1), "Veľkonočný pondelok"))

        return [(date(year, m, d), name) for m, d, name in fixed] + movable

    @classmethod
    def generate_calendar(cls, start_year, end_year):
        """
        Vygeneruje dni v kalendári pre dané roky, vrátane sviatkov.
        """
        for year in range(start_year, end_year + 1):
            holidays = dict(cls.get_slovak_holidays(year))

            d = date(year, 1, 1)
            while d.year == year:
                weekday_name = calendar.day_name[d.weekday()]
                is_weekend = weekday_name in ["Saturday", "Sunday"]
                is_holiday = d in holidays
                holiday_name = holidays.get(d, "")

                obj, created = cls.objects.get_or_create(
                    date=d,
                    defaults={
                         "day": weekday_name,
                        "is_weekend": is_weekend,
                        "is_holiday": is_holiday,
                        "holiday_name": holiday_name
                    }
                )

                if not created:
                    # aktualizuj ak sa zmenilo
                    obj.day = weekday_name
                    obj.is_weekend = is_weekend
                    obj.is_holiday = is_holiday
                    obj.holiday_name = holiday_name
                    obj.save()

                d += timedelta(days=1)