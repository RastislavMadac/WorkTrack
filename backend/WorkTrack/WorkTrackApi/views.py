from rest_framework import viewsets, permissions,status
from .models import Employees,TypeShift,Attendance,PlannedShifts,ChangeReason,CalendarDay
from .serializers import EmployeesSerializer, TypeShiftSerializer, AttendanceSerializer, PlannedShiftsSerializer,ChangeReasonSerializers,CalendarDaySerializers
from.services import calculate_working_fund,calculate_worked_hours,calculate_saturday_sunday_hours,calculate_weekend_hours,calculate_holiday_hours,compare_worked_time_working_fund
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from datetime import time, timedelta
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView


class WorkingFundAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, year: int, month: int):
        fund = calculate_working_fund(year, month)
        return Response({
            "year": year,
            "month": month,
            "working_fund_hours": fund,
        })


class WorkedHoursAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    
    def get(self, request, employee_id, year, month):
        user = request.user

        # Ak je worker, smie vidieť len seba
        if user.role == "worker" and user.id != employee_id:
            return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        # Vypočítaj odpracované hodiny
        hours = calculate_worked_hours(employee_id, year, month)
        return Response({"worked_hours": hours})
        
class SaturdaySundayHoursApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id, year, month):
        user = request.user
        # Ak je worker, smie vidieť len seba
        if user.role == "worker" and user.id != employee_id:
                return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        # Vypočítaj odpracované hodiny
        hours = calculate_saturday_sunday_hours(employee_id, year, month)
        return Response({"worked_hours": hours})
    
class WeekendHoursApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id, year, month):
        user = request.user
        # Ak je worker, smie vidieť len seba
        if user.role == "worker" and user.id != employee_id:
                return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        # Vypočítaj odpracované hodiny
        hours = calculate_weekend_hours(employee_id, year, month)
        return Response({"worked_hours": hours})

class CompareHoursApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id, year, month):
        user = request.user
        # Ak je worker, smie vidieť len seba
        if user.role == "worker" and user.id != employee_id:
                return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        # Vypočítaj odpracované hodiny
        hours =compare_worked_time_working_fund(employee_id, year, month)
        return Response({"worked_hours": hours})

class HolidayHoursApiView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id, year, month):
        user = request.user
        # Ak je worker, smie vidieť len seba
        if user.role == "worker" and user.id != employee_id:
                return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        # Vypočítaj odpracované hodiny
        hours = calculate_holiday_hours(employee_id, year, month)
        return Response({"worked_hours": hours})




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
    
    @action(detail=False, methods=["post"], url_path="prevziat-smenu")
    def prevziat_smenu(self, request):
        try:
            target_shift_id = request.data.get("target_shift_id")
            user_id = request.data.get("user_id")  # nový parameter

            if not target_shift_id:
                return Response({"error": "target_shift_id je povinný."}, status=status.HTTP_400_BAD_REQUEST)

            target_shift = PlannedShifts.objects.get(pk=target_shift_id)

            # Kto preberá smenu?
            if request.user.role in ['admin', 'manager'] and user_id:
                # Admin/manager môže prebrať smenu pre iného zamestnanca
                user_to_assign = Employees.objects.get(pk=user_id)
            else:
                # Worker môže prebrať len svoju vlastnú smenu
                user_to_assign = request.user

            attendance = Attendance.objects.create(
                user=user_to_assign,
                date=target_shift.date,
                type_shift=target_shift.type_shift,
                custom_start=target_shift.custom_start,
                custom_end=target_shift.custom_end,
                note=request.data.get("note", "") or f"Preberám smenu od {target_shift.user}"
            )

            attendance.exchange_shift(target_shift)
            attendance.create_planned_shift(attendance)

            return Response(self.get_serializer(attendance).data, status=status.HTTP_201_CREATED)

        except PlannedShifts.DoesNotExist:
            return Response({"error": "Plánovaná smena neexistuje."}, status=status.HTTP_404_NOT_FOUND)

        except Employees.DoesNotExist:
            return Response({"error": "Používateľ neexistuje."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
        if instance.type_shift.nameShift == "Nočná služba 12 hod":
         instance.handle_night_shift()

        if instance.custom_start != instance.type_shift.start_time:
          instance.handle_any_shift_time()

        if instance.custom_end !=instance.type_shift.end_time:
            instance.handle_current_shift_time(instance)

    

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

class ChangeReasonViewSet(viewsets.ModelViewSet):
    queryset = ChangeReason.objects.all()
    serializer_class = ChangeReasonSerializers
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
            raise PermissionDenied("Nemáte oprávnenie vytvárať tieto dôvody.")
        serializer.save()

class CalendarDayViewSet(viewsets.ModelViewSet):
    queryset = CalendarDay.objects.all()
    serializer_class = CalendarDaySerializers
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        user = self.request.user
        if user.role == 'worker'and user.role == 'manager':
            # worker môže iba GET
            self.http_method_names = ['get', 'head', 'options']
        else:
            # admin a manažér môžu všetko
            self.http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'worker'and user.role == 'manager':
           
            raise PermissionDenied("Nemáte oprávnenie vytvárať tieto dôvody.")
        serializer.save()