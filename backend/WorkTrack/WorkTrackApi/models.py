from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from decimal import Decimal
from datetime import date, datetime, timedelta, time


class Employees(AbstractUser):
    personal_number=models.CharField(max_length=3, 
                                     unique=True,
                                     validators=[RegexValidator(
                                         regex=r'^\d{3}$', message='Osobné číslo musí mať presne 3 číslice (napr. 001, 123).'
                                     )])
    
    ROLE_CHOICES=[
         ('admin', 'Administrátor'),
        ('manager', 'Manažér'),
        ('worker', 'Zamestnanec'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='worker')

    

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name', 'personal_number']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.personal_number})"

"""Types of shifts all shifts are fixed"""
class TypeShift(models.Model):
    nameShift=models.CharField(max_length=50)
    start_time=models.TimeField(max_length=4)
    end_time=models.TimeField(max_length=4)
    duration_time=models.DecimalField(max_digits=4, decimal_places=2, validators=[
         MinValueValidator(Decimal("0.5"), message="Trvanie musí byť aspoň 0.5 hodiny"),
        MaxValueValidator(Decimal("24.0"), message="Trvanie nemôže byť viac ako 24 hodín")
    ])

    def __str__(self):
        return self.nameShift
    
    
   
    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("Koniec smeny musí byť neskôr ako začiatok.")
        

"""emploee time at work"""
class Attendance(models.Model):
    user= models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField()
    type_shift= models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    custom_start= models.TimeField(null=True, blank=True)
    custom_end= models.TimeField(null=True,blank=True)
    note= models.TextField(blank=True)


    class Meta:
        unique_together=('user', 'date')

    def handle_night_shift(self):
        if self.type_shift and self.type_shift.id == 20:
            self.custom_end = time(0, 0)
            self.save()

            next_day = self.date + timedelta(days=1)

            Attendance.objects.create(
                user=self.user,
                date=next_day,
                type_shift=self.type_shift,
                custom_start=time(0, 0),
                custom_end=time(9, 0),
                note="Pokračovanie nočnej smeny",
            )

    def save(self, *args, **kwargs):
    # 1. Doplniť časy zo smeny, ak nie sú zadané ručne
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

         # 2. Validácia - musí byť zmysluplný interval
        if self.custom_start and self.custom_end:
            start = datetime.combine(date.today(), self.custom_start)
            end = datetime.combine(date.today(), self.custom_end)
            if end <= start:
                # výnimka pre nočnú smenu – prechod cez polnoc
                end += timedelta(days=1)
                if end <= start:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")

        



         # 3. Porovnanie s PlannedShifts
        try:
            planned_shift = PlannedShifts.objects.get(user=self.user, date=self.date)
            # Porovnávanie smien - zjednodušene môžeme porovnávať type_shift a custom časy
            shift_changed = False

            
            

            # Porovnanie typu smeny
            if planned_shift.type_shift != self.type_shift:
                shift_changed = True

            # Porovnanie časov, ak sú definované v oboch záznamoch
            if (planned_shift.custom_start and self.custom_start and planned_shift.custom_start != self.custom_start) or \
               (planned_shift.custom_end and self.custom_end and planned_shift.custom_end != self.custom_end):
                shift_changed = True

            if shift_changed:
                # Označíme, že došlo ku zmene
                planned_shift.is_changed = True
                # Ak máš change_reason, tu by si mohol nastaviť napríklad "Zmena od Attendance"
                # planned_shift.change_reason = ... (doplniť podľa potreby)
                planned_shift.save()
        except PlannedShifts.DoesNotExist:
            # Ak nemá plánovanú smenu, môžeš riešiť čo sa stane - napríklad vytvoriť PlannedShift?
            pass

        super().save(*args, **kwargs)

"""Change reason"""
class ChangeReason(models.Model):
    code = models.CharField(max_length=50, unique=True)  # napr. "SHIFT_SWAP"
    description = models.CharField(max_length=255)      # napr. "Zmena z dôvodu výmeny smeny"

    def __str__(self):
        return self.description
    

"""planned shifts"""
class PlannedShifts(models.Model):
    user= models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField()
    type_shift= models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    custom_start= models.TimeField(null=True, blank=True)
    custom_end= models.TimeField(null=True,blank=True)
    note= models.TextField(blank=True)
    is_changed = models.BooleanField(default=False)  # <- toto pole pridáme
     # Dôvod zmeny (povinný pri každej úprave/pláne)
    change_reason = models.ForeignKey(ChangeReason, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together=('user', 'date')
    
    def save(self, *args, **kwargs):
        # Ak ide o existujúci záznam, skontroluj zmeny
        if self.pk is not None:
            orig = PlannedShifts.objects.get(pk=self.pk)
            changed = (
                orig.type_shift != self.type_shift or
                orig.custom_start != self.custom_start or
                orig.custom_end != self.custom_end
            )
            if changed:
                self.is_changed = True
                if not self.change_reason:
                    raise ValidationError("Pri zmene smeny musí byť vyplnený dôvod zmeny.")
            else:
                # Ak sa nezmenilo, môže byť is_changed False a change_reason prázdny
                self.is_changed = False
                self.change_reason = None

        else:
            # Nový záznam - nemá zmenu, môže byť prázdny change_reason
            self.is_changed = False
            if not self.change_reason:
                 self.change_reason = None

        # Ak nie sú zadané časy, doplň ich zo shift_type
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

        # Validácia časov (napr. nočná smena)
        if self.custom_start and self.custom_end:
            start = datetime.combine(date.today(), self.custom_start)
            end = datetime.combine(date.today(), self.custom_end)
            if end <= start:
                end += timedelta(days=1)
                if end <= start:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")

        super().save(*args, **kwargs)

    