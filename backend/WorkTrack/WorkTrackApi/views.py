from rest_framework import viewsets, permissions
from .models import Employees,TypeShift,Attendance
from .serializers import EmployeesSerializer, TypeShiftSerializer, AttendanceSerializer
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied



class EmployeesViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Employees.objects.all()
    serializer_class = EmployeesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user=self.request.user
        if user.role == 'worker':
            return Employees.objects.filter(id=user.id)
        return Employees.objects.all()
    
class TypeShiftViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TypeShift.objects.all()
    serializer_class = TypeShiftSerializer
    permission_classes = [permissions.IsAuthenticated]

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def raise_function(self, action):
        raise PermissionDenied(detail=f"Nemáte oprávnenie {action} dochádzku iného používateľa.")



    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return Attendance.objects.filter(user=user)
        return Attendance.objects.all()

    def perform_create(self, serializer):
        user = self.request.user

        # Ak používateľ neposlal 'user', nastav ho manuálne
        if 'user' not in serializer.validated_data:
            serializer.save(user=user)
        else:
            # validate_user už overil, že to môže urobiť
            serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if user.role == 'worker' and instance.user != user:
            self.raise_function("upraviť")

        if 'user' not in serializer.validated_data:
            serializer.save(user=instance.user)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.role == 'worker' and instance.user != user:
            self.raise_function("zmazať")
        instance.delete()