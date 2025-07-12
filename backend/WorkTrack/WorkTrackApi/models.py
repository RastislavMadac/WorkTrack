from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from decimal import Decimal
from datetime import date, datetime, timedelta, time
import threading
import calendar

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



class TypeShift(models.Model):
    nameShift = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_time = models.DecimalField(
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

    def __str__(self):
        return self.nameShift

    def clean(self):
        if not self.allow_variable_time:
            if self.end_time <= self.start_time:
                raise ValidationError("Koniec smeny musí byť neskôr ako začiatok.")

"""emploee time at work"""
class Attendance(models.Model):
    user= models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField()
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
        set_force_shift_times(True)
        try:
            change_reason_obj = ChangeReason.objects.filter(category="cdr").first()
            if not change_reason_obj:
                print("⚠️ Chýba ChangeReason pre 'skorší príchod' s kategóriou 'absence'")

            print("Spúšťam handle_any_shift_time...")

            type_shift_id = 22
            changed_shift = TypeShift.objects.get(id=type_shift_id)

            # Spracovávame len plánované smeny, ktoré nie sú skryté
            for plan in PlannedShifts.objects.filter(hidden=False):
                try:
                    att = cls.objects.filter(
                        user=plan.user,
                        date=plan.date
                    ).filter(
                        models.Q(exchanged_with__isnull=True) | models.Q(exchanged_with__hidden=False)
                    ).order_by('id').first()

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
                            PlannedShifts.objects.create(
                                user=plan.user,
                                date=plan.date,
                                custom_start=att.custom_start,
                                custom_end=plan.custom_start,
                                type_shift=changed_shift,
                                transferred=True,
                                is_changed=True,
                                change_reason=change_reason_obj,
                                note="Automaticky: Skorší príchod"
                            )
                            att.custom_start = plan.custom_start
                            att.save(update_fields=['custom_start'])
                            changed = True

                        except ValidationError:
                            print(f"⚠️ Prekrývanie: nevytvorený rozdiel za skorší príchod pre {plan.user} {plan.date}")

                    # Neskorší odchod
                    if att.custom_end and plan.custom_end and att.custom_end > plan.custom_end:
                        try:
                            cls.objects.create(
                                user=plan.user,
                                date=plan.date,
                                custom_start=plan.custom_end,
                                custom_end=att.custom_end,
                                type_shift=changed_shift,
                                note="Neskorší odchod"
                            )
                            PlannedShifts.objects.create(
                                user=plan.user,
                                date=plan.date,
                                custom_start=plan.custom_end,
                                custom_end=att.custom_end,
                                type_shift=changed_shift,
                                transferred=True,
                                is_changed=True,
                                change_reason=change_reason_obj,
                                note="Neskorší odchod"
                            )
                            att.custom_end = plan.custom_end
                            att.save(update_fields=['custom_end'])
                            changed = True

                        except ValidationError:
                            print(f"⚠️ Prekrývanie: nevytvorený rozdiel za neskorší odchod pre {plan.user} {plan.date}")

                    if changed:
                        if not plan.transferred:
                            plan.transferred = True
                            plan.save(update_fields=['transferred'])

                except cls.DoesNotExist:
                    continue
                except Exception as e:
                    print(f"🛑 Chyba pri spracovaní plánovaného záznamu pre {plan.user} - {e}")

        finally:
            set_force_shift_times(False)

        
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
           
            note=f"Výmena smeny s {target_shift.user}"
        )

        new_shift.save()  # 🔴 Toto je kľúčové – musí sa uložiť pred použitím
        # 🗑 inaktivuj pôvodnú smenu kolegu
        target_shift.hidden = True
        target_shift.save(update_fields=["hidden"])

        # 3. Priradíme referenciu na tú pôvodnú smenu (alebo tú novú)
        self.exchanged_with = new_shift

        # ✅ Ulož aktualizovaný Attendance
        self.save()


    def save(self, *args, **kwargs):
        if not get_force_shift_times():
        # Ak nemáme force flag, doplni custom časy z plánovanej smeny alebo typu smeny
        # Dopĺňanie z planned_shift alebo type_shift, ak nie sú ručne zadané
            if self.planned_shift:
                if not self.date:
                    self.date = self.planned_shift.date
                if not self.custom_start:
                    self.custom_start = self.planned_shift.custom_start  # ✅ správne pole
                if not self.custom_end:
                    self.custom_end = self.planned_shift.custom_end      # ✅ správne pole
                if not self.type_shift:
                    self.type_shift = self.planned_shift.type_shift      # ✅ doplníš aj typ smeny

            elif self.type_shift:
                if not self.custom_start:
                    self.custom_start = self.type_shift.start_time
                if not self.custom_end:
                    self.custom_end = self.type_shift.end_time

        # Zaokrúhlenie na najbližšiu polhodinu
        if self.custom_start:
            self.custom_start = self.round_to_nearest_half_hour(self.custom_start)
        if self.custom_end:
            self.custom_end = self.round_to_nearest_half_hour(self.custom_end)

        # Validácia časov (aj cez polnoc)
        if self.custom_start and self.custom_end:
            start_dt = datetime.combine(date.today(), self.custom_start)
            end_dt = datetime.combine(date.today(), self.custom_end)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
                if end_dt <= start_dt:
                    raise ValidationError("Koniec smeny musí byť po začiatku (alebo správna nočná smena).")
    # Doplním automatické nastavenie calendar_day podľa date/planned_shift.date, ak nie je nastavené
        if not self.calendar_day:
            day_date = self.date or (self.planned_shift.date if self.planned_shift else None)
            if day_date:
                calendar_day = CalendarDay.objects.filter(date=day_date).first()
                if calendar_day:
                    self.calendar_day = calendar_day

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


class PlannedShifts(models.Model):
    user = models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField(null=True, blank=True)
    type_shift = models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    custom_start = models.TimeField(null=True, blank=True)
    custom_end = models.TimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    transferred = models.BooleanField(default=False)
    is_changed = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    change_reason = models.ForeignKey('WorkTrackApi.ChangeReason',on_delete=models.CASCADE, related_name="change_reason", blank=True, null=True)
    calendar_day = models.ForeignKey('WorkTrackApi.CalendarDay', on_delete=models.CASCADE, related_name="calendar_day",null=True, blank=True)
   
    class Meta:
      unique_together = ('user', 'date', 'custom_start', 'custom_end')

    def __str__(self):
        return f"{self.user} {self.type_shift}"

    def save(self, *args, **kwargs):
        if self.pk:
            orig = PlannedShifts.objects.get(pk=self.pk)
            # Kontrola zmien časov
            if orig.custom_start and self.custom_start and self.custom_start != orig.custom_start:
                raise ValidationError("Zmena časov plánovanej smeny nie je povolená (začiatok).")

            if orig.custom_end and self.custom_end and self.custom_end != orig.custom_end:
                raise ValidationError("Zmena časov plánovanej smeny nie je povolená (koniec).")
            # ⚠️ Skontroluj, či sa zmenil dátum a nastav calendar_day nanovo
            if self.date != orig.date:
                try:
                    self.calendar_day = CalendarDay.objects.get(date=self.date)
                except CalendarDay.DoesNotExist:
                    raise ValidationError(f"Pre dátum {self.date} neexistuje CalendarDay.")

        else:
            # Vytváranie novej smeny
            if not self.calendar_day and self.date:
                try:
                    self.calendar_day = CalendarDay.objects.get(date=self.date)
                except CalendarDay.DoesNotExist:
                    raise ValidationError(f"CalendarDay pre dátum {self.date} neexistuje.")

         # ⏰ Doplnenie časov zo smeny (iba pri vytváraní)
        if self.type_shift:
            if not self.custom_start:
                self.custom_start = self.type_shift.start_time
            if not self.custom_end:
                self.custom_end = self.type_shift.end_time

                  

        # Potom môžeš overiť, či je daný deň sviatok alebo víkend
        if self.calendar_day:
            print(f"Calendar day: {self.calendar_day.date}, sviatok: {self.calendar_day.is_holiday}, víkend: {self.calendar_day.is_weekend}")
            if self.calendar_day.is_holiday:
            # sprav niečo, ak je sviatok
                print("Toto je sviatok")
            elif self.calendar_day.is_weekend:
            # sprav niečo, ak je víkend
                print("Toto je víkend")
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
        print(f"Ukladám PlannedShift pre dátum {self.date}")

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