from rest_framework import serializers
from .models import Employees, TypeShift,Attendance, PlannedShifts,ChangeReason,CalendarDay
from.utils.attendance_utils import create_attendance_from_planned_shift
from datetime import date as dt_date
from django.core.exceptions import ValidationError
from datetime import time
from django.utils.dateparse import parse_time



class EmployeesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employees
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'personal_number', 'role']

class TypeShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeShift
        fields = ['id', 'nameShift', 'start_time', 'end_time', 'duration_time']

class ChangeReasonSerializers(serializers.ModelSerializer):
    class Meta:
        model = ChangeReason
        fields = '__all__'

class PlannedShiftsSerializer(serializers.ModelSerializer):
    custom_start = serializers.TimeField(required=False, allow_null=True)
    custom_end = serializers.TimeField(required=False, allow_null=True)

    class Meta:
        model = PlannedShifts
        fields = '__all__'
        read_only_fields = ['calendar_day']

    def to_internal_value(self, data):
        # Ak chýba custom_start alebo je null, doplníme z type_shift
        if ('custom_start' not in data or data['custom_start'] in [None, '']):
            type_shift_id = data.get('type_shift')
            if type_shift_id:
                ts = TypeShift.objects.filter(id=type_shift_id).first()
                if ts and ts.start_time:
                    data['custom_start'] = ts.start_time.isoformat()

        if ('custom_end' not in data or data['custom_end'] in [None, '']):
            type_shift_id = data.get('type_shift')
            if type_shift_id:
                ts = TypeShift.objects.filter(id=type_shift_id).first()
                if ts and ts.end_time:
                    data['custom_end'] = ts.end_time.isoformat()

        return super().to_internal_value(data)

    def validate(self, data):
        user = data.get('user') or getattr(self.instance, 'user', None)
        type_shift = data.get('type_shift') or getattr(self.instance, 'type_shift', None)
        custom_start = data.get('custom_start')
        custom_end = data.get('custom_end')

        if not user:
            raise ValidationError("Používateľ musí byť zadaný.")

        # Tu môžeš mať ďalšie validácie
        # Napr. kontrola rolí a povolení pri editácii

        return data

    def create(self, validated_data):
        date = validated_data.get('date')
        if date and not validated_data.get('calendar_day'):
            try:
                validated_data['calendar_day'] = CalendarDay.objects.get(date=date)
            except CalendarDay.DoesNotExist:
                raise ValidationError(f"Pre dátum {date} neexistuje CalendarDay.")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        date = validated_data.get('date', instance.date)
        if date and not validated_data.get('calendar_day', instance.calendar_day):
            try:
                validated_data['calendar_day'] = CalendarDay.objects.get(date=date)
            except CalendarDay.DoesNotExist:
                raise ValidationError(f"Pre dátum {date} neexistuje CalendarDay.")
        return super().update(instance, validated_data)

    



class CalendarDaySerializers(serializers.ModelSerializer):
    class Meta:
        model = CalendarDay
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=Employees.objects.all(), required=False
    )
    planned_shift = serializers.PrimaryKeyRelatedField(
        queryset=PlannedShifts.objects.filter(hidden=False), required=False
    )

    class Meta:
        model = Attendance
        fields = '__all__'
        extra_kwargs = {
            'date': {'required': False, 'allow_null': True},
        }

    def to_time(self, value):
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return parse_time(value)
        return None

    def validate_user(self, value):
        request_user = self.context['request'].user
        if request_user.role == 'worker' and value and value != request_user:
            raise serializers.ValidationError("Nemáte oprávnenie nastaviť iného používateľa.")
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        planned_shift = attrs.get('planned_shift') or (instance.planned_shift if instance else None)
        custom_start = attrs.get('custom_start') or (instance.custom_start if instance else None)
        custom_end = attrs.get('custom_end') or (instance.custom_end if instance else None)

      

        if not attrs.get("date") and planned_shift:
            attrs["date"] = planned_shift.date
        if not attrs.get("date"):
            attrs["date"] = dt_date.today()

        return attrs

    def create(self, validated_data):
        planned_shift = validated_data.get('planned_shift')

        input_custom_start = self.to_time(self.initial_data.get('custom_start'))
        input_custom_end = self.to_time(self.initial_data.get('custom_end'))

        if planned_shift:
            if input_custom_start and input_custom_start != planned_shift.custom_start:
                validated_data['custom_start'] = input_custom_start
            else:
                validated_data['custom_start'] = planned_shift.custom_start

            if input_custom_end and input_custom_end != planned_shift.custom_end:
                validated_data['custom_end'] = input_custom_end
            else:
                validated_data['custom_end'] = planned_shift.custom_end

            validated_data['type_shift'] = planned_shift.type_shift
            validated_data['calendar_day'] = planned_shift.calendar_day

        return Attendance.objects.create(**validated_data)

    def update(self, instance, validated_data):
        planned_shift = instance.planned_shift

        # Ak v PATCH príde custom_start a existuje planned_shift → uprav aj ju
        if 'custom_start' in validated_data and planned_shift:
            planned_shift.custom_start = validated_data['custom_start']
            planned_shift.save(update_fields=['custom_start'])

        # Rovnaké pre custom_end
        if 'custom_end' in validated_data and planned_shift:
            planned_shift.custom_end = validated_data['custom_end']
            planned_shift.save(update_fields=['custom_end'])

        # Aktualizácia samotného Attendance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance
