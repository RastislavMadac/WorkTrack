from django.urls import path, include 
from rest_framework import routers 
from .views import EmployeesViewSet,TypeShiftViewSet,AttendanceViewSet, PlannerShiftsViewSet

router=routers.DefaultRouter() 
router.register(r'employees', EmployeesViewSet)
router.register(r'typeshift', TypeShiftViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'plannedshift', PlannerShiftsViewSet)

urlpatterns = [ 

    path('', include(router.urls)), 

] 

 
