from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, DepartmentViewSet, EmployeesViewSet, AttendanceViewSet, CurrentUserViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'departments', DepartmentViewSet, basename='departments')
router.register(r'employees', EmployeesViewSet, basename='employees')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'me', CurrentUserViewSet, basename='me')

urlpatterns = router.urls
