from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from datetime import datetime
from decimal import Decimal


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
    nameShift=models.CharField(max_length=20,
                               unique=True,
                               validators=[RegexValidator(regex=r'^[A-Za-z0-9\s,\-]+$',
        message="Názov smeny môže obsahovať len písmená, čísla, medzery a pomlčky.")])
    start_time=models.TimeField(max_length=4)
    end_time=models.TimeField(max_length=4)
    duration_time=models.DecimalField(max_digits=4, decimal_places=2, validators=[
         MinValueValidator(Decimal("0.5"), message="Trvanie musí byť aspoň 0.5 hodiny"),
        MaxValueValidator(Decimal("24.0"), message="Trvanie nemôže byť viac ako 24 hodín")
    ])
   
    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("Koniec smeny musí byť neskôr ako začiatok.")
        

class Attendance(models.Model):
    user= models.ForeignKey(Employees, on_delete=models.CASCADE)
    date = models.DateField()
    type_shift= models.ForeignKey(TypeShift, null=True, blank=True, on_delete=models.SET_NULL)
    custom_start= models.TimeField(null=True, blank=True)
    custom_end= models.TimeField(null=True,blank=True)
    note= models.TextField(blank=True)

    class Meta:
        unique_together=('user', 'date')