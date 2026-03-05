from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Employee, Department, Attendance

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
