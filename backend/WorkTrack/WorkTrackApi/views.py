from rest_framework import viewsets, permissions
from .models import Employees,TypeShift
from .serializers import EmployeesSerializer, TypeShiftSerializer



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