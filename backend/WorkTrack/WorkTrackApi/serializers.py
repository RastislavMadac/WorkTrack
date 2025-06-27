from rest_framework import serializers
from .models import Employees, TypeShift


class EmployeesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employees
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'personal_number', 'role']

class TypeShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeShift
        fields = ['id', 'nameShift', 'start_time', 'end_time', 'duration_time']