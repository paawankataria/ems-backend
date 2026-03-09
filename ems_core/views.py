import base64
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Attendance, Employee, Department, LeaveType, LeaveBalance, LeaveRequest
from .serializers import (
    DepartmentSerializer,
    UserSerializer,
    EmployeeSerializer,
    EmployeeListSerializer,
    UserUpdateSerializer,
    AttendanceSerializer,
    LeaveTypeSerializer,
    LeaveBalanceSerializer,
    LeaveBalanceAdminSerializer,
    LeaveRequestSerializer,
    LeaveRequestDetailSerializer
)
from .permissions import IsAdminRole

User = get_user_model()

def check_unique(model, field, value, exclude_pk=None, error_msg=''):
    qs = model.objects.filter(**{field: value})
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

# Auth
class AuthViewSet(viewsets.ViewSet):
    
    @action(detail=False, methods=['POST'], url_path='login')
    def login(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        try:
            email = base64.b64decode(email).decode('utf-8')
            password = base64.b64decode(password).decode('utf-8')
        except Exception:
            return Response({'error': 'Invalid encoding'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # user = authenticate(request, email=email, password=password)
        verify_password = user.check_password(password)
        if verify_password is False:
            return Response({'error': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        token = AccessToken.for_user(user)
        token['role'] = user.role
        return Response({'token': str(token),}, status=status.HTTP_200_OK)
    
# Departments
class DepartmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all().order_by('name')

    # GET /api/departments/
    # def list(self, request):
    #     departments = Department.objects.all().order_by('name')
    #     serializer  = DepartmentSerializer(departments, many=True)
    #     return Response(serializer.data)

    # POST /api/departments/
    def create(self, request):
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)
        err = check_unique(Department, 'name__iexact', name, error_msg='Department already exists.')
        if err: return err
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Department created successfully.', 'department': serializer.data}, status=status.HTTP_201_CREATED)

    # GET /api/departments/{id}/
    # def retrieve(self, request, pk=None):
    #     return Response(DepartmentSerializer(get_object_or_404(Department, pk=pk)).data)

    # PUT /api/departments/{id}
    def update(self, request, pk=None):
        department = get_object_or_404(Department, pk=pk)
        name = request.data.get('name', '').strip()
        if name:
            err = check_unique(Department, 'name__iexact', name, exclude_pk=pk, error_msg='Department already exists.')
            if err: return err
        serializer = DepartmentSerializer(department, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message':    'Department updated successfully.','department': serializer.data
        }, status=status.HTTP_200_OK)
    
    # DELETE /api/departments/{id}/
    # def destroy(self, request, pk=None):
    #     get_object_or_404(Department, pk=pk).delete()
    #     return Response(status=status.HTTP_204_NO_CONTENT)
    
# Employees
class EmployeesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = EmployeeListSerializer

    def get_queryset(self):
        return Employee.objects.select_related('user', 'department').order_by('-user__created_at')
    
    # GET /api/employees/list/
    
    # POST /api/employees/register/
    @action(detail=False, methods=['POST'], url_path='register')
    def register(self, request):
        user_serializer = UserSerializer(data = request.data)
        employee_serializer = EmployeeSerializer(data = request.data)
        
        user_serializer.is_valid(raise_exception=True)
        employee_serializer.is_valid(raise_exception=True)

        user_data = user_serializer.validated_data
        employee_data = employee_serializer.validated_data

        try:
            user_data['password'] = base64.b64decode(user_data['password']).decode('utf-8')
            user_data['confirm_password'] = base64.b64decode(user_data['confirm_password']).decode('utf-8')
        except Exception:
            return Response({'error': 'Invalid encoding'}, status=status.HTTP_400_BAD_REQUEST)
        
        if user_data['password'] != user_data.pop('confirm_password'):
            return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(user_data['password'])
        except ValidationError as e:
            return Response({'error': e.messages}, status=status.HTTP_400_BAD_REQUEST)
        
        for err in [
            check_unique(User, 'email', user_data['email'], error_msg="Email already registered."),
            check_unique(User, 'username', user_data['username'], error_msg="username already taken."),
            check_unique(Employee, 'employee_id', employee_data['employee_id'], error_msg="Employee ID already registered."),
        ]:
            if err: return err

        if employee_data['salary'] <= 0:
            return Response({'error': 'Salary must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            user = User.objects.create_user(**user_data)
            employee = Employee.objects.create(user=user, **employee_data)

        return Response({
            "message": "Employee Registered Successfully", "employee": EmployeeListSerializer(employee).data
        }, status=status.HTTP_201_CREATED)
    
    # # PUT /api/employees/{id}/
    def update(self, request, pk=None, **kwargs):
        partial = kwargs.pop('partial', False)
        employee = get_object_or_404(Employee, pk=pk)

        user_serializer = UserUpdateSerializer(employee.user, data = request.data, partial=partial)
        employee_serializer = EmployeeSerializer(employee, data = request.data, partial=partial)
        user_serializer.is_valid(raise_exception=True)
        employee_serializer.is_valid(raise_exception=True)

        user_data = user_serializer.validated_data
        employee_data = employee_serializer.validated_data

        for err in [
            check_unique(User, 'email', user_data['email'], exclude_pk=employee.user.pk, error_msg="Email already registered."),
            check_unique(User, 'username', user_data['username'], exclude_pk=employee.user.pk, error_msg="username already taken."),
            check_unique(Employee, 'employee_id', employee_data['employee_id'], exclude_pk=pk, error_msg="Employee ID already registered."),
        ]:
            if err: return err

        if employee_data['salary'] <= 0:
            return Response({'error': 'Salary must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            user_data.pop('password', None)
            user_data.pop('confirm_password', None)
            user_serializer.save()
            employee_serializer.save()

        return Response({
            'message': 'Employee updated successfully', 'employee': EmployeeListSerializer(employee).data
        }, status=status.HTTP_200_OK)

    # GET /api/employees/{id}/
    
    # DELETE /api/employees/{id}/
    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        user = employee.user
        user.delete()  # This will cascade delete the employee
        return Response(status=status.HTTP_204_NO_CONTENT)

class AttendanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AttendanceSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Attendance.objects.all()
        return Attendance.objects.filter(employee=user.employee)
    
    @action(detail=False, methods=['POST'])
    def clock_in(self, request):
        employee = request.user.employee
        today = timezone.localdate()
        
        if Attendance.objects.filter(employee=employee, date=today, clock_in__isnull=False).exists():
            return Response({'detail': 'Already clocked in today'}, status=status.HTTP_400_BAD_REQUEST)
        
        attendance = Attendance.objects.create(employee=employee, date=today, clock_in=timezone.now())
        serializer = self.get_serializer(attendance)
        return Response({'detail': 'Clocked in successfully', 'attendance': serializer.data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['POST'])
    def clock_out(self, request):
        employee = request.user.employee
        today = timezone.localdate()
        
        try:
            attendance = Attendance.objects.get(employee=employee, date=today)
        except Attendance.DoesNotExist:
            return Response({"message": 'You have not clocked in'}, status=status.HTTP_400_BAD_REQUEST)

        if attendance.clock_out:
            return Response({'message': 'Already clocked out today'}, status=status.HTTP_400_BAD_REQUEST)
        
        attendance.clock_out = timezone.now()
        attendance.work_hours = attendance.clock_out - attendance.clock_in
        status_value = request.data.get('status', 'present')
        if status_value not in ['present', 'half_day', 'work_from_home']:
            return Response({'error': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)

        attendance.status = status_value
        attendance.save()
        serializer = self.get_serializer(attendance)
        return Response({'message': 'Clocked out successfully', 'attendance': serializer.data}, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Only admin can delete attendance.'}, status=403)
        return super().destroy(request, *args, **kwargs)

class CurrentUserViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        serializer = EmployeeListSerializer(request.user.employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LeaveTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = LeaveTypeSerializer
    queryset = LeaveType.objects.all()

    def perform_create(self, serializer):
        leave_type = serializer.save()
        year = timezone.now().year
        employees = Employee.objects.all()
        LeaveBalance.objects.bulk_create([
            LeaveBalance(employee=employee, leave_type=leave_type, year=year, used_days=0)
            for employee in employees
        ])
    
class LeaveBalanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.request.user.role == 'admin':
            return LeaveBalanceAdminSerializer
        return LeaveBalanceSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return LeaveBalance.objects.select_related('employee', 'leave_type').all()
        return LeaveBalance.objects.select_related('employee', 'leave_type').filter(
            employee=user.employee,
            year=timezone.now().year
        )
    
    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Only admin can edit leave balances.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

class LeaveRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LeaveRequestSerializer
        return LeaveRequestDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'manager']:
            return LeaveRequest.objects.select_related('employee', 'leave_type', 'reviewed_by').all()
        return LeaveRequest.objects.select_related('employee', 'leave_type', 'reviewed_by').filter(employee=user.employee)

    def perform_create(self, serializer):
        employee = self.request.user.employee
        leave_type = serializer.validated_data['leave_type']
        total_days = serializer.validated_data['total_days']
        year = serializer.validated_data['start_date'].year

        try:
            balance = LeaveBalance.objects.get(employee=employee, leave_type=leave_type, year=year)
        except LeaveBalance.DoesNotExist:
            raise ValidationError({'error': 'No leave balance found for this leave type.'})

        if balance.remaining_days < total_days:
            raise ValidationError({'error': f'Insufficient balance. {balance.remaining_days} days left.'})

        serializer.save(employee=employee)

    def perform_update(self, serializer):
        leave_request = self.get_object()
        if leave_request.status != 'pending':
            raise ValidationError({'error': 'Only pending requests can be updated.'})
        serializer.save()
    
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        if request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admin or manager can approve leaves.'}, status=status.HTTP_403_FORBIDDEN)
    
        leave_request = self.get_object()
    
        if leave_request.status != 'pending':
            return Response({'error': 'Only pending requests can be approved.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            leave_request.status = 'approved'
            leave_request.reviewed_by = request.user
            leave_request.reviewed_at = timezone.now()
            leave_request.save()

            balance = LeaveBalance.objects.get(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=leave_request.start_date.year
            )
            balance.used_days += leave_request.total_days
            balance.save()

            current_date = leave_request.start_date
            while current_date <= leave_request.end_date:
                Attendance.objects.update_or_create(
                    employee=leave_request.employee,
                    date=current_date,
                    defaults={'status': 'on_leave', 'leave_request': leave_request}
                )
                current_date += timedelta(days=1)

        return Response({'message': 'Leave approved.', 'leave_request': LeaveRequestDetailSerializer(leave_request).data})
    
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        if request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admin or manager can reject leaves.'}, status=status.HTTP_403_FORBIDDEN)
    
        leave_request = self.get_object()
    
        if leave_request.status != 'pending':
            return Response({'error': 'Only pending requests can be rejected.'}, status=status.HTTP_400_BAD_REQUEST)

        leave_request.status = 'rejected'
        leave_request.reviewed_by = request.user
        leave_request.reviewed_at = timezone.now()
        leave_request.save()

        return Response({'message': 'Leave rejected.', 'leave_request': LeaveRequestDetailSerializer(leave_request).data})

    def perform_destroy(self, instance):
        if instance.status == 'approved':
            with transaction.atomic():
                Attendance.objects.filter(leave_request=instance).update(status='absent')
                balance = LeaveBalance.objects.get(
                    employee=instance.employee,
                    leave_type=instance.leave_type,
                    year=instance.start_date.year
                )
                balance.used_days -= instance.total_days
                balance.save()
        instance.delete()