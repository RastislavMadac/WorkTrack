from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from decimal import Decimal
from datetime import date, datetime, timedelta, time
import threading

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
    exchanged_with = models.ForeignKey('WorkTrackApi.PlannedShifts',                   
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                help_text="Pôvodná smena kolegu, ktorú zamestnanec prebral",
            )

    # class Meta:
    #     unique_together=('user', 'date')

   

    def clean(self):
        # Overenie neprekrytia časových intervalov pre rovnakého user a date
        overlapping = Attendance.objects.filter(
            user=self.user,
            date=self.date,
        ).exclude(pk=self.pk)  # nezahrňujem seba samého

        for att in overlapping:
            # Intervaly [custom_start, custom_end)
            if self.custom_start and self.custom_end and att.custom_start and att.custom_end:
                # Check overlap
                if (self.custom_start < att.custom_end and self.custom_end > att.custom_start):
                    raise ValidationError("Časové intervaly sa prekrývajú s iným záznamom.")
      
    def round_to_nearest_half_hour(self,t: time) -> time:
        dt = datetime.combine(datetime.today(), t)
        minute = dt.minute
        # Rozdiel k dolnej a hornej 30-minútovej hranici
        down = minute % 30
        up = 30 - down

        if down < up:
            dt_rounded = dt - timedelta(minutes=down)
        else:
            dt_rounded = dt + timedelta(minutes=up)
        return dt_rounded.time()
  
        #ZMENA NOčNEJ  
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
    

    #  """PREPISUJE NOVE CASY V PLANNED SHIFT"""   
    @classmethod
    def handle_any_shift_time(cls):
        print("Spúšťam handle_any_shift_time...")

        set_force_shift_times(True)
        type_shift_id = 22
        changed_shift = TypeShift.objects.get(id=type_shift_id)

        for plan in PlannedShifts.objects.all():
            try:
                att = cls.objects.filter(user=plan.user, date=plan.date).order_by('id').first()
                if not att:
                    continue

                changed = False

                # Skorší príchod
                if att.custom_start and plan.custom_start and att.custom_start < plan.custom_start:
                    try:
                        cls.objects.create(
                            user=plan.user,
                            date=plan.date,
                            custom_start=att.custom_start,
                            custom_end=plan.custom_start,
                            type_shift=changed_shift,
                            note="Skorší príchod "
                        )
                         # 2. Vytvor nový PlannedShift pre rozdiel
                        PlannedShifts.objects.create(
                            user=plan.user,
                            date=plan.date,
                            custom_start=att.custom_start,
                            custom_end=plan.custom_start,
                            type_shift=changed_shift,
                            transferred=True,
                            is_changed=True,
                            change_reason="Automaticky: Skorší príchod doplniť dôvod!!!"
                        )
                        # 3. Aktualizuj hlavný attendance na plánovaný začiatok
                        att.custom_start = plan.custom_start
                        att.save(update_fields=['custom_start'])
                        changed = True

                    except ValidationError:
                        print(f"⚠️ Prekrývanie: nevytvorený rozdiel za skorší príchod pre {plan.user} {plan.date}")

                # Neskorší odchod
                if att.custom_end and plan.custom_end and att.custom_end > plan.custom_end:
                    try:
                         # 1. Vytvor nový attendance záznam za neskorší odchod
                        cls.objects.create(
                            user=plan.user,
                            date=plan.date,
                            custom_start=plan.custom_end,
                            custom_end=att.custom_end,
                            type_shift=changed_shift,
                            note="Neskorší odchod"
                        )
                        # 2. Vytvor nový PlannedShift pre rozdiel
                        PlannedShifts.objects.create(
                            user=plan.user,
                            date=plan.date,
                            custom_start=plan.custom_end,
                            custom_end=att.custom_end,
                            type_shift=changed_shift,
                            transferred=True,
                            is_changed=True,
                            change_reason="Automaticky: neskorší odchod doplniť dôvod!!!"
                        )
                       # 3. Aktualizuj hlavný attendance na plánovaný koniec
                        att.custom_end = plan.custom_end
                        att.save(update_fields=['custom_end'])
                        changed = True

                    except ValidationError:
                       print(f"⚠️ Prekrývanie: nevytvorený rozdiel za neskorší odchod pre {plan.user} {plan.date}")


                if changed:
                # označ pôvodnú plánovanú smenu ako prenesenú, ale nemeníme ju
                    if not plan.transferred:
                        plan.transferred = True
                        plan.save(update_fields=['transferred'])

            except cls.DoesNotExist:
                continue
            except Exception as e:
                print(f"🛑 Chyba pri spracovaní plánovaného záznamu pre {plan.user} - {e}")

    set_force_shift_times(False)
        # Na konci resetni prepínač
       
    def exchange_shift(self, target_shift):
        if not target_shift:
            raise ValidationError("Nebola vybraná smena na výmenu.")

        if self.user == target_shift.user:
            raise ValidationError("Nemôžeš si vymeniť smenu sám so sebou.")

        if self.date != target_shift.date or self.type_shift != target_shift.type_shift:
            raise ValidationError("Smena na výmenu musí byť rovnakého typu a dňa.")

        # 🔤 Vygeneruj dynamický dôvod
        self.exchange_reason = f"výmena smien s {target_shift.user.full_name if hasattr(target_shift.user, 'full_name') else str(target_shift.user)}"
        self.exchanged_with = target_shift

        # 💾 Vytvor nový plánovaný záznam pre tohto zamestnanca (ak chceš)
        new_shift=PlannedShifts.objects.create(
            user=self.user,
            date=self.date,
            type_shift=self.type_shift,
            custom_start=self.custom_start,
            custom_end=self.custom_end,
            transferred=True,
            is_changed=True,
            change_reason=self.exchange_reason,
            note=f"Výmena smeny s {target_shift.user}"
        )

        new_shift.save()  # 🔴 Toto je kľúčové – musí sa uložiť pred použitím
        # 🗑 Vymaž pôvodnú smenu kolegu
        target_shift.delete()

        # 3. Priradíme referenciu na tú pôvodnú smenu (alebo tú novú)
        self.exchanged_with = new_shift

        # ✅ Ulož aktualizovaný Attendance
        self.save()


    def save(self, *args, **kwargs):
        # 1. Zaokrúhlenie časov na najbližšiu polhodinu
        if self.custom_start:
             self.custom_start = self.round_to_nearest_half_hour(self.custom_start)
        if self.custom_end:
            self.custom_end = self.round_to_nearest_half_hour(self.custom_end)
        # 🟡 1. Doplnenie časov zo smeny, ak nie sú zadané ručne
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

        # 🔴 2. Validácia časového intervalu (aj cez polnoc)
        if self.custom_start and self.custom_end:
            start_dt = datetime.combine(date.today(), self.custom_start)
            end_dt = datetime.combine(date.today(), self.custom_end)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
                if end_dt <= start_dt:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")

        # ✅ 3. Ulož samotný záznam dochádzky (ostatné spracujú signály)
        super().save(*args, **kwargs)


"""Change reason"""
class ChangeReason(models.Model):
    code = models.CharField(max_length=50, unique=True)  # napr. "SHIFT_SWAP"
    description = models.CharField(max_length=255)      # napr. "Zmena z dôvodu výmeny smeny"

    def __str__(self):
        return self.description
    

"""planned shifts"""


class PlannedShifts(models.Model):
    user = models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField()
    type_shift = models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    custom_start = models.TimeField(null=True, blank=True)
    custom_end = models.TimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    transferred = models.BooleanField(default=False)
    is_changed = models.BooleanField(default=False)
    change_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
      unique_together = ('user', 'date', 'custom_start', 'custom_end')

    def __str__(self):
        return f"{self.user} {self.type_shift}"

    def save(self, *args, **kwargs):
        if self.pk:
            orig = PlannedShifts.objects.get(pk=self.pk)

            if orig.custom_start and self.custom_start and self.custom_start != orig.custom_start:
                raise ValidationError("Zmena časov plánovanej smeny nie je povolená (začiatok).")

            if orig.custom_end and self.custom_end and self.custom_end != orig.custom_end:
                raise ValidationError("Zmena časov plánovanej smeny nie je povolená (koniec).")


         # ⏰ Doplnenie časov zo smeny (iba pri vytváraní)
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

        # 🕒 Validácia
        if self.custom_start and self.custom_end:
            start = datetime.combine(date.today(), self.custom_start)
            end = datetime.combine(date.today(), self.custom_end)
            if end <= start:
                end += timedelta(days=1)
                if end <= start:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")

    
        # 💾 Ulož záznam
        super().save(*args, **kwargs)
