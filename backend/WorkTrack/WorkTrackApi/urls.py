from django.urls import path, include 
from rest_framework import routers 
from .views import EmployeesViewSet,TypeShiftViewSet,AttendanceViewSet, PlannerShiftsViewSet,ChangeReasonViewSet,CalendarDayViewSet,WorkingFundAPIView, WorkedHoursAPIView,SaturdaySundayHoursApiView,WeekendHoursApiView,HolidayHoursApiView,CompareHoursApiView

router=routers.DefaultRouter() 
router.register(r'employees', EmployeesViewSet)
router.register(r'typeshift', TypeShiftViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'plannedshift', PlannerShiftsViewSet)
router.register(r'changereason', ChangeReasonViewSet)
router.register(r'calendarday', CalendarDayViewSet)


urlpatterns = [ 

    path('', include(router.urls)), 
    path('working_fund/<int:year>/<int:month>/', WorkingFundAPIView.as_view(), name='working-fund'),
    path('worked_hours/<int:employee_id>/<int:year>/<int:month>/', WorkedHoursAPIView.as_view(), name='worked-hours'),
    path('saturday_sunday_hours/<int:employee_id>/<int:year>/<int:month>/', SaturdaySundayHoursApiView.as_view(), name='saturday-sunday-hours'),
    path('weekend_hours/<int:employee_id>/<int:year>/<int:month>/', WeekendHoursApiView.as_view(), name='weekend-hours'),
    path('holiday_hours/<int:employee_id>/<int:year>/<int:month>/', HolidayHoursApiView.as_view(), name='holiday-hours'),
    path('compare_hours/<int:employee_id>/<int:year>/<int:month>/', CompareHoursApiView.as_view(), name='compare-hours'),


] 

 
