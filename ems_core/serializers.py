from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Employee, Department, Attendance, LeavesType, LeavesBalance, LeavesRequest, Payroll

User = get_user_model()

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Department
        fields = '__all__'
    
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'password', 'confirm_password']

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        # fields = '__all__'
        exclude = ['user']
    
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['password']

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'created_at']

class EmployeeListSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = '__all__'

class EmployeeMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name']

class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['status', 'work_hours', 'created_at']
        extra_kwargs = {'employee': {'write_only': True}}

class LeavesTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavesType
        fields = '__all__'

class LeavesBalanceSerializer(serializers.ModelSerializer):
    # employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    leaves_type = LeavesTypeSerializer(read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeavesBalance
        fields = ['id', 'leaves_type', 'year', 'remaining_days', 'used_days']

class LeavesBalanceAdminSerializer(serializers.ModelSerializer):
    leaves_type = LeavesTypeSerializer(read_only = True)
    employee = EmployeeListSerializer(read_only=True)
    # employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeavesBalance
        fields = '__all__'

class LeavesRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavesRequest
        fields = ['leaves_type', 'start_date', 'end_date', 'reason']

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise ValidationError({'error': 'Start date cannot be after end date.'})
        data['total_days'] = (data['end_date'] - data['start_date']).days + 1
        return data

class ReviewedBySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'role']

class LeavesRequestDetailSerializer(serializers.ModelSerializer):
    employee = EmployeeMinimalSerializer(read_only=True)
    leaves_type = LeavesTypeSerializer(read_only=True)
    reviewed_by = ReviewedBySerializer(read_only=True)

    class Meta:
        model = LeavesRequest
        fields = '__all__'

class PayrollSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payroll
        fields = '__all__'
        read_only_fields=['base_salary', 'net_salary', 'month', 'year']