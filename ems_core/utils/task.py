from background_task import background
from ..models import Attendance, Employee
from django.utils import timezone
from datetime import date, time

@background(schedule=0)
def mark_absent_for_date(date_str):
    parsed_date = date.fromisoformat(date_str)

    if parsed_date.weekday() >= 5:
        return

    now = timezone.localtime(timezone.now())
    cutoff = time(15, 32)
    if parsed_date == timezone.localdate() and now.time() < cutoff:
        return
        
    present_employee_ids = Attendance.objects.filter(
        date=parsed_date,
    ).exclude(
        clock_in__isnull=True, status='wfh_pending'
    ).values_list('employee_id', flat=True)

    absent_employees = Employee.objects.exclude(id__in=present_employee_ids)

    Attendance.objects.bulk_create([
        Attendance(employee=employee, date=date, status='absent')
        for employee in absent_employees
    ], ignore_conflicts=True)