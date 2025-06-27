from django.urls import path, include 
from rest_framework import routers 
from .views import EmployeesViewSet,TypeShiftViewSet,AttendanceViewSet

router=routers.DefaultRouter() 
router.register(r'employees', EmployeesViewSet)
router.register(r'typeshift', TypeShiftViewSet)
router.register(r'attendance', AttendanceViewSet)

urlpatterns = [ 

    path('', include(router.urls)), 

] 

 
