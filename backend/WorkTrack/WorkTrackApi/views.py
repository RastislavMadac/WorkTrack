from rest_framework import viewsets, permissions
from .models import Employees,TypeShift,Attendance,PlannedShifts
from .serializers import EmployeesSerializer, TypeShiftSerializer, AttendanceSerializer, PlannedShiftsSerializer
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from datetime import time, timedelta



class EmployeesViewSet(viewsets.ModelViewSet):
    queryset = Employees.objects.all()
    serializer_class = EmployeesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user=self.request.user
        if user.role == 'worker':
            return Employees.objects.filter(id=user.id)
        return Employees.objects.all()
    
    def get_permissions(self):
        user = self.request.user
        if user.role == 'worker':
            # worker môže iba GET
            self.http_method_names = ['get', 'head', 'options']
        else:
            # admin a manažér môžu všetko
            self.http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
        return super().get_permissions()
    
class TypeShiftViewSet(viewsets.ModelViewSet):
    queryset = TypeShift.objects.all()
    serializer_class = TypeShiftSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        user = self.request.user
        if user.role == 'worker':
            # worker môže iba GET
            self.http_method_names = ['get', 'head', 'options']
        else:
            # admin a manažér môžu všetko
            self.http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'worker':
            # worker by nemal vytvárať (ak nechceš povoliť ani to)
            raise PermissionDenied("Nemáte oprávnenie vytvárať smeny.")
        serializer.save()

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
        data = serializer.validated_data

        if 'user' not in data:
            instance = serializer.save(user=self.request.user)
        else:
            instance = serializer.save()

        # Zavoláme metódu z modelu
        instance.handle_night_shift()
        Attendance.handle_any_shift_time()

       
    

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


class PlannerShiftsViewSet(viewsets.ModelViewSet):
    queryset = PlannedShifts.objects.all()
    serializer_class = PlannedShiftsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return PlannedShifts.objects.filter(user=user)
        return PlannedShifts.objects.all()

    def get_permissions(self):
        user = self.request.user
        if user.role == 'worker':
            # worker môže iba GET
            self.http_method_names = ['get', 'head', 'options']
        else:
            # admin a manažér môžu všetko
            self.http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'worker':
            # worker by nemal vytvárať (ak nechceš povoliť ani to)
            raise PermissionDenied("Nemáte oprávnenie vytvárať smeny.")
        serializer.save()

    # už nemusíš implementovať perform_update a perform_destroy,
    # worker tam prístup nemá kvôli get_permissions