from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models

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
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

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