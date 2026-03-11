from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def generate_payslip_pdf(payroll):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Payslip", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Employee: {payroll.employee.user.first_name} {payroll.employee.user.last_name}", styles['Normal']))
    story.append(Paragraph(f"Period: {payroll.month}/{payroll.year}", styles['Normal']))
    story.append(Spacer(1, 12))

    data = [
        ['Description', 'Amount'],
        ['Base Salary', f"${payroll.base_salary}"],
        ['Deductions', f"-${payroll.salary_deduction}"],
        ['Net Salary', f"${payroll.net_salary}"],
    ]
    table = Table(data, colWidths=[300, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer