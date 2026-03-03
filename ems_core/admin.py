from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Employee

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # columns shown in the list view
    list_display  = ['username', 'email', 'role', 'is_active']
    list_filter   = ['role', 'is_active']
    search_fields = ['username', 'email']

    # add custom fields to the edit form
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {
            'fields': ('role',)
        }),
    )

    # add custom fields to the create form
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role', {
            'fields': ('email', 'role')
        }),
    )

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'description', 'created_at']
    search_fields = ['name']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display  = ['user', 'employee_id', 'salary', 'department']
    search_fields = ['user__email', 'employee_id']
    list_filter   = ['department']