from django.urls import path, include 
from rest_framework import routers 
from .views import EmployeesViewSet,TypeShiftViewSet

router=routers.DefaultRouter() 
router.register(r'employees', EmployeesViewSet)
router.register(r'typeshift', TypeShiftViewSet)

urlpatterns = [ 

    path('', include(router.urls)), 

] 

 
