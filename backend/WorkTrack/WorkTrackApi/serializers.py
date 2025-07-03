from rest_framework import serializers
from .models import Employees, TypeShift,Attendance, PlannedShifts


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

    class Meta:
        model = Attendance
        fields = ['id', 'user', 'date', 'type_shift', 'custom_start', 'custom_end', 'note']

    def validate_user(self, value):
        request_user = self.context['request'].user
        if request_user.role == 'worker':
            if value and value != request_user:
                raise serializers.ValidationError("Nemáte oprávnenie nastaviť iného používateľa.")
        return value
    
    

class PlannedShiftsSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = PlannedShifts
        fields = ['id', 'user', 'date', 'type_shift', 'custom_start', 'custom_end', 'note', 'is_changed', 'change_reason' ]