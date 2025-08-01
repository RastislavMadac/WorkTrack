# Generated by Django 5.2 on 2025-06-27 18:44

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('WorkTrackApi', '0002_typeshift'),
    ]

    operations = [
        migrations.AlterField(
            model_name='typeshift',
            name='nameShift',
            field=models.CharField(max_length=20, unique=True, validators=[django.core.validators.RegexValidator(message='Názov smeny môže obsahovať len písmená, čísla, medzery a pomlčky.', regex='^[A-Za-z0-9\\s,\\-]+$')]),
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('custom_start', models.TimeField(blank=True, null=True)),
                ('custom_end', models.TimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True)),
                ('type_shift', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='WorkTrackApi.typeshift')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'date')},
            },
        ),
    ]
