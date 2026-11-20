"""
Django management command to send daily class attendance summary via email.
Run with: python manage.py send_daily_class_summary
"""
import io
import logging
from datetime import date, datetime

import pandas as pd
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.db.models import Q

from APIS.models import Center, ClassModel, Holidays, Student, User
from esswebapp.helpers import get_user_accessible_center_ids

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send daily class attendance summary email with Excel attachment'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date for the report (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument(
            '--recipients',
            type=str,
            help='Comma-separated email recipients. Defaults to DEFAULT_FROM_EMAIL.',
        )

    def handle(self, *args, **options):
        # Parse target date
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {options['date']}. Use YYYY-MM-DD"))
                return
        else:
            target_date = date.today()

        # Parse recipients
        if options['recipients']:
            recipients = [e.strip() for e in options['recipients'].split(',')]
        else:
            recipients = [settings.DEFAULT_FROM_EMAIL]

        self.stdout.write(f"Generating daily class summary for {target_date}...")
        self.stdout.write(f"Recipients: {', '.join(recipients)}")

        try:
            # Generate Excel file
            excel_buffer = self.generate_excel_report(target_date)

            # Send email
            self.send_email(target_date, excel_buffer, recipients)

            self.stdout.write(self.style.SUCCESS(f'Daily class summary sent successfully for {target_date}'))

        except Exception as e:
            logger.error(f"Failed to send daily class summary: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Failed: {e}"))

    def get_all_centers_with_classes(self):
        """Get all active centers that have active classes (SuperAdmin view)"""
        return Center.objects.filter(
            status=True,
            classes__active_status=True,
            classes__status__in=[1, 2, 3]
        ).distinct()

    def is_center_holiday(self, center_id, check_date):
        """Check if center has a holiday on the given date"""
        return Holidays.objects.filter(
            holiday_centers__center_id=center_id,
            status=True,
            start_date__date__lte=check_date,
            end_date__date__gte=check_date
        ).exists()

    def get_class_on_date(self, center, check_date):
        """Get the class that started on the given date for this center"""
        return ClassModel.objects.filter(
            center=center,
            active_status=True,
            status__in=[1, 2, 3],
            started_date__date=check_date
        ).first()

    def get_attendance_counts(self, cls, check_date):
        """Calculate present/absent counts for a class on a specific date"""
        if not cls.center_id:
            return 0, 0, False

        # Get all active students enrolled in this center
        enrolled_students = Student.objects.filter(
            center_id=cls.center_id,
            status=True
        ).values_list('id', flat=True)

        if not enrolled_students:
            return 0, 0, False

        # Get attendance records for these students on this date for this class
        attendance_records = cls.attendances.filter(
            status=True,
            scan_date__date=check_date,
            student_id__in=enrolled_students
        ).values_list('student_id', 'type')

        # Check if ANY attendance records exist at all
        has_records = len(attendance_records) > 0

        if not has_records:
            # No attendance marked at all by teacher
            return 0, 0, False

        # Build lookup: student_id -> type (True=Present, False=Absent)
        attendance_by_student = {sid: t for sid, t in attendance_records}

        present = 0
        absent = 0

        for student_id in enrolled_students:
            if student_id in attendance_by_student:
                if attendance_by_student[student_id] is True:
                    present += 1
                else:
                    absent += 1
            else:
                # No attendance record for this student = Absent
                absent += 1

        return present, absent, True

    def get_status_key(self, cls, check_date):
        """Determine the status key for a class on a specific date"""
        # Check if cancelled on this date
        if cls.cancel_date and cls.cancel_date.date() == check_date:
            return 'cancelled'

        # Check if class date is today (in progress)
        if cls.started_date and cls.started_date.date() == check_date:
            return 'in_progress'

        # For past dates
        if cls.started_date and cls.started_date.date() < check_date:
            has_start = cls.started_date is not None
            has_end = cls.ended_date is not None

            if has_start and has_end:
                # Check attendance
                _, _, has_records = self.get_attendance_counts(cls, check_date)
                if has_records:
                    return 'completed'
                else:
                    return 'completed_no_attendance'
            elif has_start and not has_end:
                _, _, has_records = self.get_attendance_counts(cls, check_date)
                if has_records:
                    return 'active_ended'
                else:
                    return 'active_ended_no_att'

        return 'not_started'

    def generate_excel_report(self, target_date):
        """Generate Excel report with daily class summary"""
        centers = self.get_all_centers_with_classes()

        rows = []

        for center in centers:
            # Get total students for this center
            total_students = Student.objects.filter(center=center, status=True).count()

            # Check if holiday
            if self.is_center_holiday(center.id, target_date):
                rows.append({
                    'Date': target_date.strftime('%Y-%m-%d'),
                    'Center ID': center.id,
                    'Center Name': center.center_name,
                    'District': center.district.name if center.district else '',
                    'Total Students': total_students,
                    'Class Completed': 0,
                    'Total Present': 0,
                    'Total Absent': 0,
                    'Not Started': 0,
                    'Status': 'Holiday'
                })
                continue

            # Get class on this date
            class_on_date = self.get_class_on_date(center, target_date)

            if not class_on_date:
                # No class started on this date
                if target_date == date.today():
                    status = 'Not Started'
                    not_started = 1
                    completed = 0
                else:
                    status = 'No Class'
                    not_started = 0
                    completed = 0

                rows.append({
                    'Date': target_date.strftime('%Y-%m-%d'),
                    'Center ID': center.id,
                    'Center Name': center.center_name,
                    'District': center.district.name if center.district else '',
                    'Total Students': total_students,
                    'Class Completed': completed,
                    'Total Present': 0,
                    'Total Absent': 0,
                    'Not Started': not_started,
                    'Status': status
                })
                continue

            # Class exists - get attendance counts
            present, absent, has_records = self.get_attendance_counts(class_on_date, target_date)

            # Determine if completed
            status_key = self.get_status_key(class_on_date, target_date)
            completed = 1 if status_key in ('completed', 'completed_no_attendance') else 0
            not_started = 1 if status_key == 'not_started' else 0

            rows.append({
                'Date': target_date.strftime('%Y-%m-%d'),
                'Center ID': center.id,
                'Center Name': center.center_name,
                'District': center.district.name if center.district else '',
                'Total Students': total_students,
                'Class Completed': completed,
                'Total Present': present,
                'Total Absent': absent,
                'Not Started': not_started,
                'Status': status_key.replace('_', ' ').title()
            })

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Create summary row
        if not df.empty:
            summary_row = {
                'Date': target_date.strftime('%Y-%m-%d'),
                'Center ID': '',
                'Center Name': 'TOTAL',
                'District': '',
                'Total Students': df['Total Students'].sum(),
                'Class Completed': df['Class Completed'].sum(),
                'Total Present': df['Total Present'].sum(),
                'Total Absent': df['Total Absent'].sum(),
                'Not Started': df['Not Started'].sum(),
                'Status': ''
            }
            df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)

        # Write to Excel buffer
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Daily Class Summary')

            # Get the worksheet to format
            worksheet = writer.sheets['Daily Class Summary']

            # Add header row with date at top
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter

            # Insert a row at the top for the date header
            worksheet.insert_rows(1)
            worksheet['A1'] = f'Daily Class Attendance Summary - {target_date.strftime("%Y-%m-%d")}'
            worksheet['A1'].font = Font(bold=True, size=14)
            worksheet.merge_cells('A1:J1')
            worksheet['A1'].alignment = Alignment(horizontal='center')

            # Style header row (now row 2)
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            header_alignment = Alignment(horizontal='center', wrap_text=True)
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            for col_num, column_title in enumerate(df.columns, 1):
                cell = worksheet.cell(row=2, column=col_num, value=column_title)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border

            # Style data rows
            for row_num in range(3, worksheet.max_row + 1):
                for col_num in range(1, len(df.columns) + 1):
                    cell = worksheet.cell(row=row_num, column=col_num)
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal='center')

                    # Highlight summary row
                    if row_num == worksheet.max_row:
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')

            # Auto-fit column widths
            for col_num, column_title in enumerate(df.columns, 1):
                column_letter = get_column_letter(col_num)
                max_length = max(
                    len(str(column_title)),
                    *[len(str(worksheet.cell(row=row, column=col_num).value)) for row in range(2, worksheet.max_row + 1) if worksheet.cell(row=row, column=col_num).value]
                )
                worksheet.column_dimensions[column_letter].width = min(max_length + 2, 30)

        buffer.seek(0)
        return buffer

    def send_email(self, target_date, excel_buffer, recipients):
        """Send email with Excel attachment"""
        subject = f'Daily Class Attendance Summary - {target_date.strftime("%Y-%m-%d")}'

        body = f"""
        <html>
        <body>
            <p>Dear Team,</p>
            <p>Please find attached the daily class attendance summary for <strong>{target_date.strftime("%Y-%m-%d")}</strong>.</p>
            <p>The report includes the following metrics for each center:</p>
            <ul>
                <li>Total Students</li>
                <li>Class Completed</li>
                <li>Total Present</li>
                <li>Total Absent</li>
                <li>Not Started</li>
            </ul>
            <p>A summary row with totals is included at the bottom.</p>
            <br>
            <p>Thanks & Regards<br>
            <strong>EkSeSreshtha System</strong></p>
        </body>
        </html>
        """

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.content_subtype = 'html'

        # Attach Excel file
        filename = f'Daily_Class_Summary_{target_date.strftime("%Y%m%d")}.xlsx'
        email.attach(filename, excel_buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        email.send()
        logger.info(f"Daily class summary email sent to {', '.join(recipients)} for {target_date}")