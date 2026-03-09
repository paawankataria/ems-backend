from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Employee, Department, Attendance, LeaveType, LeaveBalance, LeaveRequest

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

class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['status', 'work_hours', 'created_at']
        extra_kwargs = {'employee': {'write_only': True}}

class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'

class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeSerializer(read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'leave_type', 'year', 'remaining_days']

class LeaveBalanceAdminSerializer(serializers.ModelSerializer):
    leave_type = LeaveTypeSerializer(read_only = True)
    employee = EmployeeListSerializer(read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = '__all__'

class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise ValidationError({'error': 'Start date cannot be after end date.'})
        data['total_days'] = (data['end_date'] - data['start_date']).days + 1
        return data

class LeaveRequestDetailSerializer(serializers.ModelSerializer):
    employee = EmployeeListSerializer(read_only=True)
    leave_type = LeaveTypeSerializer(read_only=True)
    reviewed_by = UserMinimalSerializer(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = '__all__'