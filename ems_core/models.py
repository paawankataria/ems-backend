from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('employee', 'Employee'),
    ]

    email = models.EmailField(unique=True) 
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    department_head = models.OneToOneField(
        "Employee", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="manage_department",
        limit_choices_to={'user__role': 'manager'}
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    
class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee'
    )
    employee_id = models.CharField(max_length=20, unique=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    phone = models.CharField(max_length=15, blank=True)
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees'
    )

    def __str__(self):
        return f"{self.user.email} ({self.user.role})"

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('on_leave', 'On Leave'),
        ('half_day', 'Half Day'),
        ('work_from_home', 'Work From Home'),
    ]

    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='attendance'
    )
    date = models.DateField(default=timezone.now)
    clock_in = models.DateTimeField(blank=True, null=True)
    clock_out = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    work_hours = models.DurationField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    leaves_request = models.ForeignKey(
        'LeavesRequest', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='attendances'
)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_employee_date')
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee} ({self.date}) - {self.status}"

class LeavesType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    total_days = models.PositiveIntegerField()
    carryover_limit = models.PositiveIntegerField(default=0)
    department = models.ForeignKey(
        'Department', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="leaves_types"
    )

    def __str__(self):
        return f"{self.name} {self.department} ({self.total_days} days)"


class LeavesBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances')
    leaves_type = models.ForeignKey(LeavesType, on_delete=models.CASCADE, related_name='balances')
    year = models.PositiveIntegerField()
    used_days = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ['employee', 'leaves_type', 'year']

    @property
    def remaining_days(self):
        return self.leaves_type.total_days - self.used_days
    
    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.leaves_type.name} {self.year} ({self.remaining_days} days left)"


class LeavesRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leaves_type = models.ForeignKey(LeavesType, on_delete=models.CASCADE, related_name='requests')
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_leaves')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee.user.get_full_name()} - {self.leaves_type.name} {self.start_date} to {self.end_date} ({self.status})" 
    
class Payroll(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid')
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll')
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    class Meta:
        unique_together = ['employee', 'year', 'month']