from django.urls import path, include 
from rest_framework import routers 
from .views import EmployeesViewSet,TypeShiftViewSet,AttendanceViewSet, PlannerShiftsViewSet,ChangeReasonViewSet,CalendarDayViewSet

router=routers.DefaultRouter() 
router.register(r'employees', EmployeesViewSet)
router.register(r'typeshift', TypeShiftViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'plannedshift', PlannerShiftsViewSet)
router.register(r'changereason', ChangeReasonViewSet)
router.register(r'calendarday', CalendarDayViewSet)

urlpatterns = [ 

    path('', include(router.urls)), 

] 

 
