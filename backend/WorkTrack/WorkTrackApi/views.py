from rest_framework import viewsets, permissions,status
from .models import Employees,TypeShift,Attendance,PlannedShifts,ChangeReason,CalendarDay
from .serializers import EmployeesSerializer, TypeShiftSerializer, AttendanceSerializer, PlannedShiftsSerializer,ChangeReasonSerializers,CalendarDaySerializers
from.services import calculate_working_fund,calculate_worked_hours,calculate_saturday_sunday_hours,calculate_weekend_hours,calculate_holiday_hours,compare_worked_time_working_fund,calculate_total_hours_with_transfer,calculate_night_shift_hours
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from datetime import time, timedelta
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from WorkTrackApi.utils.attendance_utils import split_night_planned_shift
from django.utils.dateparse import parse_time


class BaseWorkedHoursAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # Potomok musí definovať túto metódu, ktorá vykoná výpočet
    def calculate_hours(self, employee_id, year, month):
        raise NotImplementedError("Potomok musí implementovať calculate_hours")

    def get(self, request, employee_id, year, month):
        user = request.user

        # Overenie, či môže worker vidieť len seba
        if user.role == "worker" and user.id != employee_id:
            return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        hours = self.calculate_hours(employee_id, year, month)
        return Response({"worked_hours": hours})

class WorkingFundAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, year: int, month: int):
        fund = calculate_working_fund(year, month)
        return Response({
            "year": year,
            "month": month,
            "working_fund_hours": fund,
        })


class WorkedHoursAPIView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_worked_hours(employee_id, year, month)

class SaturdaySundayHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_saturday_sunday_hours(employee_id, year, month)

class WeekendHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_weekend_hours(employee_id, year, month)

class CompareHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return compare_worked_time_working_fund(employee_id, year, month)

class HolidayHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_holiday_hours(employee_id, year, month)

class TotalHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_total_hours_with_transfer(employee_id, year, month)

class NightShiftHoursApiView(BaseWorkedHoursAPIView):
    def calculate_hours(self, employee_id, year, month):
        return calculate_night_shift_hours(employee_id, year, month)


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
        if user.is_authenticated and user.role == 'worker':
            self.http_method_names = ['get', 'head', 'options']
        else:
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
     

    def get_queryset(self):
        user = self.request.user
        if user.role == 'worker':
            return Attendance.objects.filter(user=user)
        return Attendance.objects.all()

       
    def perform_create(self, serializer):
        input_custom_start_str = serializer.initial_data.get("custom_start")
        input_custom_end_str = serializer.initial_data.get("custom_end")

        input_custom_start = parse_time(input_custom_start_str) if input_custom_start_str else None
        input_custom_end = parse_time(input_custom_end_str) if input_custom_end_str else None

        instance = serializer.save()

        if not instance.type_shift:
            return instance

        from WorkTrackApi.utils.attendance_utils import (
            handle_any_shift_time,
            handle_start_shift_time,
            handle_end_shift_time,
            handle_night_shift,
        )

        # 1️⃣ Najprv riešime rozdelenie nočnej smeny (ak je potrebné)
        if instance.type_shift.id == 20:  # alebo iná podmienka
            handle_night_shift(instance)

        # 2️⃣ Potom riešime úpravy časov podľa vstupu
        if input_custom_start and input_custom_end:
            if (input_custom_start != instance.type_shift.start_time) or (input_custom_end != instance.type_shift.end_time):
                handle_any_shift_time(instance)
        else:
            if input_custom_start and input_custom_start != instance.type_shift.start_time:
                instance.custom_start = input_custom_start
                handle_start_shift_time(instance)
            if input_custom_end and input_custom_end != instance.type_shift.end_time:
                instance.custom_end = input_custom_end
                handle_end_shift_time(instance)

        return instance



   


    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        if user.role == 'worker' and instance.user != user:
            self.raise_function("upraviť")

        # Ulož si pôvodné hodnoty pred aktualizáciou
        original_custom_start = instance.custom_start
        original_custom_end = instance.custom_end

        # Ulož nové hodnoty
        if 'user' not in serializer.validated_data:
            instance = serializer.save(user=instance.user)
        else:
            instance = serializer.save()

        # Porovnaj nové hodnoty s pôvodnými
        new_custom_start = instance.custom_start
        new_custom_end = instance.custom_end

        from WorkTrackApi.utils.attendance_utils import (
            handle_any_shift_time,
            handle_start_shift_time,
            handle_end_shift_time,
        )

        if instance.type_shift:
            if new_custom_start and new_custom_end:
                if new_custom_start != instance.type_shift.start_time or new_custom_end != instance.type_shift.end_time:
                    handle_any_shift_time(instance)
            elif new_custom_start and new_custom_start != instance.type_shift.start_time:
                handle_start_shift_time(instance)
            elif new_custom_end and new_custom_end != instance.type_shift.end_time:
                handle_end_shift_time(instance)


    def perform_destroy(self, instance):
        user = self.request.user
        if user.role == 'worker' and instance.user != user:
            self.raise_function("zmazať")
            print("Záznam bol zmazaný")
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
            raise PermissionDenied("Nemáte oprávnenie vytvárať smeny.")
        planned_shift = serializer.save()

        # Zavoláme rozdelenie iba ak je to nocná smena (id=20)
        if planned_shift.type_shift_id == 20:
            split_night_planned_shift(planned_shift)
    
    def perform_update(self, serializer):
        planned_shift = serializer.save()
        if planned_shift.type_shift_id == 20:
            split_night_planned_shift(planned_shift)



    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        # Worker už metódu DELETE ani nevidí (get_permissions),
        # ale kontrolujeme aj pre manažéra
        if user.role == 'manager':
            if instance.user != user:
                raise PermissionDenied("Nemáte oprávnenie zmazať túto smenu.")

        # Admin môže všetko
        self.perform_destroy(instance)
        return Response(
            {"detail": "Záznam bol úspešne vymazaný."},
        status=status.HTTP_200_OK
    )


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