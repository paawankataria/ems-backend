from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, DepartmentViewSet, EmployeesViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'departments', DepartmentViewSet, basename='departments')
router.register(r'employees', EmployeesViewSet, basename='employees')\

urlpatterns = router.urls
