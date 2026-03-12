import base64
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Attendance, Employee, Department, LeavesType, LeavesBalance, LeavesRequest, Payroll
from .serializers import (
    DepartmentSerializer,
    UserSerializer,
    EmployeeSerializer,
    EmployeeListSerializer,
    UserUpdateSerializer,
    AttendanceSerializer,
    LeavesTypeSerializer,
    LeavesBalanceSerializer,
    LeavesBalanceAdminSerializer,
    LeavesRequestSerializer,
    LeavesRequestDetailSerializer,
    PayrollSerializer
)
from .permissions import IsAdminRole, IsAdminOrManagerRole
from .utils.payslip_pdf import generate_payslip_pdf

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
    serializer_class = DepartmentSerializer
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), IsAdminOrManagerRole()]
        return [IsAuthenticated(), IsAdminRole()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            return Department.objects.filter(pk=user.employee.manage_department.pk)
        return Department.objects.all().order_by('name')

    # GET /api/departments/

    def _validate_department_head(self, employee_id, department_pk=None):
        employee = Employee.objects.select_related('user', 'manage_department').filter(pk=employee_id).first()

        if not employee:
            return Response({'error': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        if employee.user.role != 'manager':
            return Response({'error': 'Department head must have a manager role.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if manager is already head of a DIFFERENT department
        if hasattr(employee, 'manage_department'):
            already_managing = employee.manage_department
            if department_pk is None or already_managing.pk != int(department_pk):
                return Response(
                    {'error': f'This manager is already head of "{already_managing.name}" department.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return None

    # POST /api/departments/
    def create(self, request):
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)
        err = check_unique(Department, 'name__iexact', name, error_msg='Department already exists.')
        if err: return err

        department_head_id = request.data.get('department_head')
        if department_head_id:
            head_err = self._validate_department_head(department_head_id)
            if head_err: return head_err
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Department created successfully.', 'department': serializer.data}, status=status.HTTP_201_CREATED)

    # GET /api/departments/{id}/

    # PUT /api/departments/{id}
    def update(self, request, pk=None):
        department = get_object_or_404(Department, pk=pk)
        name = request.data.get('name', '').strip()
        if name:
            err = check_unique(Department, 'name__iexact', name, exclude_pk=pk, error_msg='Department already exists.')
            if err: return err
        
        department_head_id = request.data.get('department_head')
        if department_head_id:
            head_err = self._validate_department_head(department_head_id, department_pk=pk)
            if head_err: return head_err
        
        serializer = DepartmentSerializer(department, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message':    'Department updated successfully.','department': serializer.data
        }, status=status.HTTP_200_OK)
    
    # DELETE /api/departments/{id}/
    
# Employees
class EmployeesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = EmployeeListSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), IsAdminOrManagerRole()]
        return [IsAuthenticated(), IsAdminRole()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            return Employee.objects.filter(department=user.employee.manage_department).order_by('-user__created_at')
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
            return Attendance.objects.all().order_by('-created_at')
        return Attendance.objects.filter(employee=user.employee).order_by('-created_at')
    
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
            return Response({'error': 'Only admin can delete attendance.'}, status=status.HTTP_403_FORBIDDEN)
        
        attendance = self.get_object()
        if attendance.leaves_request and attendance.status == 'on_leave':
            with transaction.atomic():
                balance = LeavesBalance.objects.get(
                    employee=attendance.employee,
                    leaves_type=attendance.leaves_request.leaves_type,
                    year=attendance.date.year
                )
                balance.used_days -= 1
                balance.save()
        attendance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class CurrentUserViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        serializer = EmployeeListSerializer(request.user.employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LeavesTypeViewSet(viewsets.ModelViewSet):
    serializer_class = LeavesTypeSerializer
    queryset = LeavesType.objects.all()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminRole()]

    def perform_create(self, serializer):
        leaves_type = serializer.save()
        year = timezone.now().year
        employees = Employee.objects.filter(department=leaves_type.department) if leaves_type.department else Employee.objects.all()
        LeavesBalance.objects.bulk_create([
            LeavesBalance(employee=employee, leaves_type=leaves_type, year=year, used_days=0)
            for employee in employees
        ])

    def perform_update(self, serializer):
        old_department = serializer.instance.department
        leaves_type = serializer.save()
        new_department = leaves_type.department

        if old_department != new_department:
            year = timezone.now().year
            LeavesBalance.objects.filter(leaves_type=leaves_type, year=year).exclude(
                employee__department=new_department
            ).delete()

            existing = LeavesBalance.objects.filter(leaves_type=leaves_type, year=year).values_list('employee_id', flat=True)
            new_employees = Employee.objects.filter(department=new_department).exclude(id__in=existing)
            LeavesBalance.objects.bulk_create([
                LeavesBalance(employee=employee, leaves_type=leaves_type, year=year, used_days=0)
                for employee in new_employees
            ])
    
class LeavesBalanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    def get_serializer_class(self):
        if self.request.user.role == 'admin':
            return LeavesBalanceAdminSerializer
        return LeavesBalanceSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return LeavesBalance.objects.select_related('employee', 'leaves_type').all()
        return LeavesBalance.objects.select_related('employee', 'leaves_type').filter(
            employee=user.employee,
            year=timezone.now().year
        )
    
    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'error': 'Only admin can edit leave balances.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

class LeavesRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LeavesRequestSerializer
        return LeavesRequestDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'manager']:
            return LeavesRequest.objects.select_related('employee', 'leaves_type', 'reviewed_by').all().order_by('-created_at')
        return LeavesRequest.objects.select_related('employee', 'leaves_type', 'reviewed_by').filter(employee=user.employee).order_by('-created_at')

    def perform_create(self, serializer):
        employee = self.request.user.employee
        leaves_type = serializer.validated_data['leaves_type']
        total_days = serializer.validated_data['total_days']
        year = serializer.validated_data['start_date'].year

        try:
            balance = LeavesBalance.objects.get(employee=employee, leaves_type=leaves_type, year=year)
        except LeavesBalance.DoesNotExist:
            raise ValidationError({'error': 'No leaves balance found for this leave type.'})

        if balance.remaining_days < total_days:
            raise ValidationError({'error': f'Insufficient balance. {balance.remaining_days} days left.'})

        serializer.save(employee=employee)

    def perform_update(self, serializer):
        leaves_request = self.get_object()
        if leaves_request.status != 'pending':
            raise ValidationError({'error': 'Only pending requests can be updated.'})
        serializer.save()
    
    @action(detail=True, methods=['POST'])
    def approve(self, request, pk=None):
        if request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admin or manager can approve leaves.'}, status=status.HTTP_403_FORBIDDEN)
    
        leaves_request = self.get_object()
    
        if leaves_request.status != 'pending':
            return Response({'error': 'Only pending requests can be approved.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            leaves_request.status = 'approved'
            leaves_request.reviewed_by = request.user
            leaves_request.reviewed_at = timezone.now()
            leaves_request.save()

            balance = LeavesBalance.objects.get(
                employee=leaves_request.employee,
                leaves_type=leaves_request.leaves_type,
                year=leaves_request.start_date.year
            )
            balance.used_days += leaves_request.total_days
            balance.save()

            current_date = leaves_request.start_date
            while current_date <= leaves_request.end_date:
                attendance, _ = Attendance.objects.get_or_create(
                    employee=leaves_request.employee,
                    date=current_date,
                )
                attendance.status = 'on_leave'
                attendance.leaves_request = leaves_request
                attendance.clock_in = None
                attendance.clock_out = None
                attendance.work_hours = None
                attendance.save()
                current_date += timedelta(days=1)

        return Response({'message': 'Leaves approved.', 'leaves_request': LeavesRequestDetailSerializer(leaves_request).data})
    
    @action(detail=True, methods=['POST'])
    def reject(self, request, pk=None):
        if request.user.role not in ['admin', 'manager']:
            return Response({'error': 'Only admin or manager can reject leaves.'}, status=status.HTTP_403_FORBIDDEN)
    
        leaves_request = self.get_object()
    
        if leaves_request.status != 'pending':
            return Response({'error': 'Only pending requests can be rejected.'}, status=status.HTTP_400_BAD_REQUEST)

        leaves_request.status = 'rejected'
        leaves_request.reviewed_by = request.user
        leaves_request.reviewed_at = timezone.now()
        leaves_request.save()

        return Response({'message': 'Leaves rejected.', 'leaves_request': LeavesRequestDetailSerializer(leaves_request).data})

    def perform_destroy(self, instance):
        if instance.status == 'approved':
            with transaction.atomic():
                Attendance.objects.filter(leaves_request=instance).update(status='absent',
                    leaves_request=None,
                    clock_in=None,
                    clock_out=None,
                    work_hours=None
                )
                balance = LeavesBalance.objects.get(
                    employee=instance.employee,
                    leaves_type=instance.leaves_type,
                    year=instance.start_date.year
                )
                balance.used_days -= instance.total_days
                balance.save()
        instance.delete()

class PayrollViewset(viewsets.ModelViewSet):
    serializer_class = PayrollSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminRole()]
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin']:
            return Payroll.objects.select_related('employee__user', 'employee__department').all().order_by('-year', '-month')
        return Payroll.objects.select_related('employee__user', 'employee__department').filter(employee=user.employee).order_by('-year', '-month')
    
    def perform_create(self, serializer):
        employee = Employee.objects.get(id=self.request.data['employee']['id'])
        deduction = serializer.validated_data.get('salary_deduction', 0)
        now = timezone.now()
        serializer.save(
            employee=employee,
            base_salary=employee.salary,
            net_salary=employee.salary - deduction,
            month=now.month,
            year=now.year
        )
    
    def perform_update(self, serializer):
        employee = serializer.validated_data.get('employee', serializer.instance.employee)
        deduction = serializer.validated_data.get('salary_deduction', serializer.instance.salary_deduction)
        serializer.save(net_salary=employee.salary - deduction)

    @action(detail=True, methods=['get'], url_path='payslip')
    def payslip(self, request, pk=None):
        payroll = self.get_object()  # handles 404 + permissions automatically
        buffer = generate_payslip_pdf(payroll)
        return FileResponse(buffer, as_attachment=True, filename=f"payslip_{payroll.month}_{payroll.year}.pdf")