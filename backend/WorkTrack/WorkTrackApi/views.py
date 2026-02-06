# Súbor: WorkTrackApi/views.py

from rest_framework import viewsets, permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication

from django.db import transaction
from django.utils.dateparse import parse_time
from datetime import date, datetime, time, timedelta
from calendar import monthrange

# Importy modelov a serializerov
from .models import Employees, TypeShift, Attendance, PlannedShifts, ChangeReason, CalendarDay
from .serializers import (
    BulkRosterSerializer, EmployeesSerializer, TypeShiftSerializer, 
    AttendanceSerializer, PlannedShiftsSerializer, ChangeReasonSerializers, 
    CalendarDaySerializers
)
from .export import MonthlyRosterExporter, AttendancePdfExporter, VacationFormExporter
from .permissions import IsManagerOrReadOnly, IsManagerOrWorkerExchangeOnly

# DÔLEŽITÉ: Import všetkých servisných funkcií
from .services import (
    calculate_working_fund, calculate_worked_hours, calculate_saturday_sunday_hours,
    calculate_weekend_hours, calculate_holiday_hours, compare_worked_time_working_fund,
    calculate_total_hours_with_transfer, calculate_night_shift_hours, copy_monthly_plan,
    get_planned_monthly_summary, get_balances_up_to, get_full_monthly_stats, get_yearly_report_data
)

from WorkTrackApi.utils.attendance_utils import (
    split_night_planned_shift, handle_night_shift, 
    handle_start_shift_time, handle_end_shift_time
)

# ==========================================
# 1. ŠPECIÁLNE ENDPOINTY (Stats, Dashboard, Auth)
# ==========================================

class MonthlyStatsView(APIView):
    """
    Endpoint: /api/plannedshift/stats/?year=2025&month=1
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            year = int(request.query_params.get('year'))
            month = int(request.query_params.get('month'))
            data = get_full_monthly_stats(year, month)
            return Response(data)
        except (ValueError, TypeError):
            return Response({"error": "Invalid year or month"}, status=400)

class MonthlyBalancesAPIView(APIView):
    def get(self, request, year, month):
        balances = get_balances_up_to(year, month)
        return Response(balances)

class WorkingFundAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, year: int, month: int):
        fund = calculate_working_fund(year, month)
        holidays_query = CalendarDay.objects.filter(
            date__year=year, date__month=month, is_holiday=True
        )
        holiday_days = [h.date.day for h in holidays_query]
        return Response({
            "year": year, "month": month,
            "working_fund_hours": fund,
            "holidays": holiday_days
        })

class DashboardView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        return Response({"message": f"Ahoj {request.user.username}, toto je tvoj dashboard"})

class TestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        return Response({"message": "OK"})

class ActiveUserListView(generics.ListAPIView):
    serializer_class = EmployeesSerializer
    def get_queryset(self):
         return Employees.objects.all().prefetch_related('planned_shifts')

class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        serializer = EmployeesSerializer(request.user)
        return Response(serializer.data)

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key, 'user_id': user.id,
            'username': user.username, 'role': user.role
        })

# ==========================================
# 2. VIEWSETS (CRUD Operácie)
# ==========================================

class PlannerShiftsViewSet(viewsets.ModelViewSet):
    queryset = PlannedShifts.objects.all()
    serializer_class = PlannedShiftsSerializer
    permission_classes = [IsManagerOrWorkerExchangeOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous: return PlannedShifts.objects.none()
        
        queryset = PlannedShifts.objects.filter(hidden=False)
        if user.role == 'worker':
            queryset = queryset.filter(user=user)
        
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')
        user_id_param = self.request.query_params.get('user')
        
        if month and year:
            queryset = queryset.filter(date__year=year, date__month=month)
        if user_id_param:
            queryset = queryset.filter(user_id=user_id_param)
        return queryset

    def create(self, request, *args, **kwargs):
        is_many = isinstance(request.data, list)
        serializer = self.get_serializer(data=request.data, many=is_many)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        created_data = serializer.save()
        if isinstance(created_data, list):
            for shift in created_data:
                if shift.type_shift and shift.type_shift.id == 20:
                    split_night_planned_shift(shift)
        else:
            if created_data.type_shift and created_data.type_shift.id == 20:
                split_night_planned_shift(created_data)

    def perform_update(self, serializer):
        planned_shift = serializer.save()
        if planned_shift.type_shift and planned_shift.type_shift.id == 20:
            split_night_planned_shift(planned_shift)

    # def destroy(self, request, *args, **kwargs):
    #     instance = self.get_object()
    #     instance.hidden = True
    #     instance.save()
    #     return Response({"detail": "Smena bola skrytá."}, status=status.HTTP_200_OK)
    def perform_destroy(self, instance):
            """
            Vymaže záznam z databázy úplne.
            """
            instance.delete()
    @action(detail=False, methods=['post'], url_path='save-roster-matrix')
    def save_roster_matrix(self, request):
        serializer = BulkRosterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        year, month, shifts_data = data['year'], data['month'], data['shifts']
        
        saved_count = 0
        try:
            with transaction.atomic():
                for item in shifts_data:
                    shift_date = item['date']
                    if shift_date.year != year or shift_date.month != month: continue

                    if item.get('type_shift_id') is None:
                        PlannedShifts.objects.filter(user_id=item['user_id'], date=shift_date).delete()
                        continue

                    defaults = {
                        'type_shift_id': item['type_shift_id'],
                        'custom_start': item.get('custom_start'),
                        'custom_end': item.get('custom_end'),
                        'note': item.get('note', ''),
                        'hidden': False
                    }
                    if not defaults['custom_start']:
                        ts = TypeShift.objects.get(id=item['type_shift_id'])
                        defaults['custom_start'] = ts.start_time
                        defaults['custom_end'] = ts.end_time

                    shift, _ = PlannedShifts.objects.update_or_create(
                        user_id=item['user_id'], date=shift_date, defaults=defaults
                    )
                    if shift.type_shift and shift.type_shift.id == 20:
                        split_night_planned_shift(shift)
                    saved_count += 1
            return Response({"detail": f"Uložených {saved_count} záznamov."}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='export-complex-roster')
    def export_complex_roster(self, request):
        try:
            year = int(request.query_params.get('year', 2025))
            month = int(request.query_params.get('month', 4))
        except ValueError:
            return Response({"error": "Chyba parametrov"}, status=400)
        exporter = MonthlyRosterExporter(year, month)
        return exporter.generate_response()

    @action(detail=False, methods=['get'], url_path='export-vacation-forms')
    def export_vacation_forms(self, request):
        try:
            year = int(request.query_params.get('year'))
            month = int(request.query_params.get('month'))
            user_id = int(request.query_params.get('user_id'))
        except (TypeError, ValueError):
             return Response({"error": "Chýbajú parametre"}, status=400)
        exporter = VacationFormExporter(user_id, year, month)
        return exporter.generate_response()
    
    @action(detail=False, methods=['post'])
    def copy_plan(self, request):
        s_year = request.data.get('source_year')
        s_month = request.data.get('source_month')
        t_year = request.data.get('target_year')
        t_month = request.data.get('target_month')
        user_id = request.data.get('user_id')

        if not all([s_year, s_month, t_year, t_month]):
            return Response({"error": "Chýbajú povinné údaje."}, status=400)

        try:
            result = copy_monthly_plan(int(s_year), int(s_month), int(t_year), int(t_month), user_id)
            return Response({"detail": "Plán skopírovaný.", "stats": result}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=False, methods=['get'], url_path='summary/(?P<user_id>\d+)/(?P<year>\d+)/(?P<month>\d+)')
    def monthly_summary(self, request, user_id=None, year=None, month=None):
        if not user_id or not year or not month:
            return Response({"error": "Chýbajú parametre"}, status=400)
        try:
            summary_data = get_planned_monthly_summary(int(user_id), int(year), int(month))
            return Response(summary_data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    @action(detail=True, methods=['post'], url_path='request-exchange')
    def request_exchange(self, request, pk=None):
        source_shift = self.get_object()
        user = request.user # Prihlásený používateľ

        # --- BEZPEČNOSTNÁ KONTROLA ---
        # Ak je používateľ 'worker' A smena nie je jeho -> ERROR 403
        if user.role == 'worker' and source_shift.user.id != user.id:
            return Response(
                {"error": "Nemáte oprávnenie žiadať o výmenu cudzej smeny."}, 
                status=403 # Forbidden
            )
        target_user_id = request.data.get('target_user_id')
        
        # ID 40 (alebo iné existujúce ID pre "Výmena")
        EXCHANGE_REASON_ID = 40 

        if not target_user_id:
            return Response({"error": "Musíte vybrať kolegu na výmenu."}, status=400)

        try:
            target_user = Employees.objects.get(id=target_user_id)
        except Employees.DoesNotExist:
            return Response({"error": "Cieľový používateľ neexistuje."}, status=404)

        if source_shift.user.id == target_user.id:
             return Response({"error": "Nemôžete vymeniť smenu sám so sebou."}, status=400)

        # --- NOVÁ KONTROLA: Má už kolega túto smenu? ---
        duplicate_exists = PlannedShifts.objects.filter(
            user=target_user,
            date=source_shift.date,
            custom_start=source_shift.custom_start,
            custom_end=source_shift.custom_end
        ).exists()

        if duplicate_exists:
            return Response({
                "error": f"Kolega {target_user.last_name} už má presne túto smenu v pláne."
            }, status=400)
        # -----------------------------------------------

        try:
            with transaction.atomic():
                # 1. Skryjeme pôvodnú smenu
                source_shift.hidden = True
                source_shift.approval_status = 'pending'
                source_shift.note = f"{source_shift.note or ''} (Čaká na výmenu s {target_user.last_name})"
                source_shift.save()

                # 2. Vytvoríme novú smenu
                new_shift = PlannedShifts.objects.create(
                    user=target_user,
                    date=source_shift.date,
                    type_shift=source_shift.type_shift,
                    custom_start=source_shift.custom_start,
                    custom_end=source_shift.custom_end,
                    change_reason_id=EXCHANGE_REASON_ID,
                    is_changed=True,
                    approval_status='pending',
                    transferred=False,
                    exchange_link=source_shift,
                    note=f"Návrh výmeny od {source_shift.user.last_name}"
                )

            return Response({"detail": "Žiadosť o výmenu bola odoslaná.", "new_shift_id": new_shift.id}, status=200)
        
        except Exception as e:
            # Ak nastane iná chyba (napr. neexistujúce reason_id), vypíšeme ju
            import traceback
            print(traceback.format_exc())
            return Response({"error": str(e)}, status=500)
    @action(detail=True, methods=['post'], url_path='decide-exchange')
    def decide_exchange(self, request, pk=None):
        target_shift = self.get_object()
        new_status = request.data.get('status') 
        note = request.data.get('manager_note', '')

        if new_status not in ['approved', 'rejected']:
             return Response({"error": "Neplatný status."}, status=400)

        source_shift = target_shift.exchange_link
        
        if not source_shift:
             return Response({"error": "Chýba prepojenie na pôvodnú smenu."}, status=400)

        with transaction.atomic():
            target_shift.approval_status = new_status
            target_shift.manager_note = note
            
            if new_status == 'approved':
                # --- SCHVÁLENÉ ---
                target_shift.approval_status = 'approved'
                
                # NOVÁ ÚPRAVA: Smena sa stáva oficiálnou, rušíme príznak "zmena"
                target_shift.is_changed = False 
                
                target_shift.note = f"{target_shift.note or ''} (Schválená výmena od {source_shift.user.last_name})"
                target_shift.save()

                # Starú smenu vymažeme, lebo zodpovednosť bola prenesená
                source_shift.delete()
                
                msg = "Výmena schválená, smena je platná a pôvodná bola zmazaná."

            elif new_status == 'rejected':
                # --- ZAMIETNUTÉ ---
                # Novú smenu zmažeme
                target_shift.delete() 

                # Starú smenu vrátime pôvodnému majiteľovi
                source_shift.hidden = False
                source_shift.approval_status = 'approved'
                source_shift.note = f"{source_shift.note or ''} (Zamietnutá výmena: {note})"
                source_shift.save()
                
                msg = "Výmena zamietnutá, smena vrátená pôvodnému zamestnancovi."

        return Response({"detail": msg}, status=200) 
Testovanie vymeny formulara

    @action(detail=True, methods=['get'], url_path='download-exchange-pdf')
    def download_exchange_pdf(self, request, pk=None):
        target_shift = self.get_object()
        source_shift = target_shift.exchange_link

        if not source_shift:
            return Response({"error": "Toto nie je výmena smeny."}, status=400)

        # Použijeme novú triedu z export.py
        exporter = ExchangeFormExporter(source_shift, target_shift)
        return exporter.generate_response()
class EmployeesViewSet(viewsets.ModelViewSet):
    queryset = Employees.objects.all()
    serializer_class = EmployeesSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        # user = self.request.user
        # if user.role == 'worker': return Employees.objects.filter(id=user.id)
        # return Employees.objects.all()
        return Employees.objects.filter(is_active=True).order_by('last_name')

class TypeShiftViewSet(viewsets.ModelViewSet):
    queryset = TypeShift.objects.all()
    serializer_class = TypeShiftSerializer
    permission_classes = [permissions.IsAuthenticated]
    def perform_create(self, serializer):
        if self.request.user.role == 'worker': raise PermissionDenied()
        serializer.save()

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [] 

    def get_queryset(self):
        # 1. Začneme so všetkými dátami
        queryset = Attendance.objects.all().order_by('-date')
        user = self.request.user

        # Debug výpis do terminálu (uvidíš ho tam, kde beží runserver)
        print(f"--- FILTER DEBUG START ---")
        
        # 2. Základný filter podľa role (Worker vidí len svoje)
        if getattr(user, 'role', 'worker') == 'worker':
            queryset = queryset.filter(user=user)

        # 3. Získanie parametrov z URL
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        
        print(f"Prijaté parametre: Rok={year}, Mesiac={month}")

        # 4. APLIKÁCIA FILTRA
        if year and month:
            try:
                # Prevedieme na int, aby sme mali istotu
                y = int(year)
                m = int(month)
                
                # Samotné filtrovanie
                queryset = queryset.filter(date__year=y, date__month=m)
                
                print(f"✅ Filter úspešný. Vraciam {queryset.count()} záznamov pre {y}/{m}.")
            except ValueError:
                print("❌ Chyba: Rok alebo mesiac nie sú platné čísla.")
        else:
            print("⚠️ Žiadny filter roka/mesiaca - vraciam všetko.")

        print(f"--- FILTER DEBUG END ---")
        return queryset
   
    @action(detail=False, methods=['get'], url_path='export-attendance-pdf')
    def export_attendance_pdf(self, request):
        try:
            year = int(request.query_params.get('year'))
            month = int(request.query_params.get('month'))
            user_id = int(request.query_params.get('user_id'))
            exporter = AttendancePdfExporter(user_id, year, month)
            return exporter.generate_response()
        except: return Response({"error": "Chyba parametrov"}, status=400)

    

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.type_shift:
            if instance.type_shift.id == 20: handle_night_shift(instance)
            handle_start_shift_time(instance)
            handle_end_shift_time(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.type_shift:
            handle_start_shift_time(instance)
            handle_end_shift_time(instance)

class ChangeReasonViewSet(viewsets.ModelViewSet):
    queryset = ChangeReason.objects.all()
    serializer_class = ChangeReasonSerializers
    permission_classes = [permissions.IsAuthenticated]

class CalendarDayViewSet(viewsets.ModelViewSet):
    queryset = CalendarDay.objects.all()
    serializer_class = CalendarDaySerializers
    permission_classes = [permissions.IsAuthenticated]

# ==========================================
# 4. API VIEWS PRE REPORTY (Pôvodné - teraz kompletné)
# ==========================================

class BaseWorkedHoursAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def calculate_hours(self, employee_id, year, month):
        raise NotImplementedError("Potomok musí implementovať calculate_hours")

    def get(self, request, employee_id, year, month):
        user = request.user
        if user.role == "worker" and user.id != employee_id:
            return Response({"detail": "Nemáš oprávnenie vidieť údaje iných."}, status=403)

        hours = self.calculate_hours(employee_id, year, month)
        return Response({"worked_hours": hours})

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

class PlannedHoursSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id, year, month):
        data = get_planned_monthly_summary(employee_id, year, month)
        return Response(data)
    

# WorkTrackApi/views.py
class YearlyOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        try:
            year = int(request.query_params.get('year', datetime.now().year))
            data = get_yearly_report_data(year)
            return Response(data)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class CopyMonthlyPlanView(APIView):
    """
    Endpoint na skopírovanie zmien z jedného mesiaca do druhého.
    URL: POST /api/plannedshift/copy/
    Body: { "source_year": 2025, "source_month": 1, "target_year": 2025, "target_month": 2 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            data = request.data
            
            source_year = int(data.get('source_year'))
            source_month = int(data.get('source_month'))
            target_year = int(data.get('target_year'))
            target_month = int(data.get('target_month'))

            # Volanie funkcie zo services.py
            count = copy_monthly_plan(user, source_year, source_month, target_year, target_month)
            
            return Response({
                "message": f"Úspešne skopírovaných {count} smien.",
                "count": count
            }, status=status.HTTP_200_OK)

        except (ValueError, TypeError):
            return Response({"error": "Neplatné dáta (rok alebo mesiac)."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)