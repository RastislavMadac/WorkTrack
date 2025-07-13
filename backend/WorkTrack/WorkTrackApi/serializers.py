from rest_framework import serializers
from .models import Employees, TypeShift,Attendance, PlannedShifts,ChangeReason,CalendarDay


class EmployeesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employees
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'personal_number', 'role']

class TypeShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeShift
        fields = ['id', 'nameShift', 'start_time', 'end_time', 'duration_time']

class AttendanceSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=Employees.objects.all(), required=False
    )
    planned_shift = serializers.PrimaryKeyRelatedField(
        queryset=PlannedShifts.objects.filter(hidden=False)
    )
    date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = Attendance
        exclude = []

    def validate_user(self, value):
        request_user = self.context['request'].user
        if request_user.role == 'worker':
            if value and value != request_user:
                raise serializers.ValidationError("Nemáte oprávnenie nastaviť iného používateľa.")
        return value

    def create(self, validated_data):
        planned_shift = validated_data.get('planned_shift', None)

        if planned_shift:
            validated_data['date'] = planned_shift.date

        return super().create(validated_data)


class PlannedShiftsSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = PlannedShifts
        fields = ['id', 'user', 'date', 'type_shift', 'custom_start', 'custom_end', 'note', 'is_changed', 'change_reason' ]

class ChangeReasonSerializers(serializers.ModelSerializer):

    class Meta:
        model=ChangeReason
        fields=['id','name', 'description', 'category']


class CalendarDaySerializers(serializers.ModelSerializer):

    class Meta:
        model=CalendarDay
        fields=['id','date', 'day', 'is_weekend','is_holiday','holiday_name']
        
