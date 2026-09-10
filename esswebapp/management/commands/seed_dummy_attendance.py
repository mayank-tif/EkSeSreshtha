#!/usr/bin/env python3
"""
Django management command: create/remove dummy data for testing the
Center Attendance API.

Create dummy data (center, teacher, students, attendance for today):
    python manage.py seed_dummy_attendance

Specific date:
    python manage.py seed_dummy_attendance --date 2026-09-08

Remove all dummy data:
    python manage.py seed_dummy_attendance --clear-dummy

Everything created by this command is prefixed with "DUMMY" so it can be
identified and removed independently of real data.
"""
import uuid
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from APIS.models import (
    District, VidhanSabha, Panchayat, Village, Center, School,
    Teacher, Student, User, Role, StudentAttendance, ClassModel,
)


class Command(BaseCommand):
    help = 'Seed/remove dummy data for testing the Center Attendance API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date', type=str, default=None,
            help='Attendance date to seed (YYYY-MM-DD). Default: today'
        )
        parser.add_argument(
            '--clear-dummy', action='store_true',
            help='Delete all DUMMY test data instead of seeding'
        )

    def handle(self, *args, **options):
        if options['clear_dummy']:
            self.clear_dummy()
            return

        date_str = options['date']
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('Invalid --date format, use YYYY-MM-DD')
        else:
            target_date = timezone.now().date()

        self.stdout.write(f'Seeding dummy data for attendance date: {target_date}')
        self.seed(target_date)

    # ------------------------------------------------------------------
    def seed(self, target_date):
        # ---- hierarchy ----
        district, _ = District.objects.get_or_create(
            name='DUMMY Test District',
            defaults={
                'district_guid_id': f'DIST-DUMMY-{uuid.uuid4().hex[:8]}',
                'status': True,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        vidhan_sabha, _ = VidhanSabha.objects.get_or_create(
            name='DUMMY Test VS',
            district=district,
            defaults={
                'vidhan_sabha_guid_id': f'VS-DUMMY-{uuid.uuid4().hex[:8]}',
                'status': True,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        panchayat, _ = Panchayat.objects.get_or_create(
            name='DUMMY Test Panchayat',
            district=district,
            vidhan_sabha=vidhan_sabha,
            defaults={
                'panchayat_guid_id': f'PAN-DUMMY-{uuid.uuid4().hex[:8]}',
                'status': True,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        village, _ = Village.objects.get_or_create(
            name='DUMMY Test Village',
            district=district,
            vidhan_sabha=vidhan_sabha,
            panchayat=panchayat,
            defaults={
                'village_guid_id': f'VIL-DUMMY-{uuid.uuid4().hex[:8]}',
                'status': True,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        school, _ = School.objects.get_or_create(
            school_name='DUMMY Test School',
            defaults={'status': True, 'created_on': timezone.now(), 'created_by': 1}
        )

        # ---- center ----
        center, _ = Center.objects.get_or_create(
            center_name='DUMMY Test Center',
            defaults={
                'center_guid_id': f'CENTER-DUMMY-{uuid.uuid4().hex[:8]}',
                'district': district,
                'vidhan_sabha': vidhan_sabha,
                'panchayat': panchayat,
                'village': village,
                'status': True,
                'class_status': True,
                'location_status': 'VERIFIED',
                'latitude': 31.68,
                'longitude': 76.52,
                'created_date': timezone.now(),
                'created_by': 1,
            }
        )

        # ---- teacher (User + Teacher) ----
        role, _ = Role.objects.get_or_create(role_code='TEACHER')
        teacher_user, user_created = User.objects.get_or_create(
            phone_number='9999990001',
            defaults={
                'enrolment_roll_id': 'DUMMY-T-001',
                'name': 'DUMMY Teacher',
                'whats_app': '9999990001',
                'password': 'dummy-not-a-real-login',
                'status': True,
                'role': role,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        if user_created:
            self.stdout.write(f'  Created teacher user: {teacher_user.name} (ID: {teacher_user.id})')

        teacher, _ = Teacher.objects.get_or_create(
            user=teacher_user,
            defaults={
                'teacher_guid_id': f'teacher-{teacher_user.id}',
                'district': district,
                'vidhan_sabha': vidhan_sabha,
                'panchayat': panchayat,
                'village': village,
                'center': center,
                'age': 30,
                'gender': 'Female',
                'date_of_birth': '1996-01-01',
                'contact': '9999990001',
                'full_address': 'DUMMY Test Village',
                'education': 'B.A.',
                'guardian_name': 'DUMMY Guardian',
                'guardian_number': '9999990002',
                'assigned_teacher_status': True,
                'enrollment_date': timezone.now(),
                'status': True,
                'created_on': timezone.now(),
                'created_by': 1,
            }
        )
        center.assigned_teachers = teacher_user.id
        center.save()

        # ---- class ----
        class_obj, _ = ClassModel.objects.get_or_create(
            class_enrolment_id='DUMMY-CLS-001',
            defaults={
                'name': 'DUMMY Test Class',
                'status': 1,
                'active_status': True,
                'sub_status': 1,
                'session_closed': False,
                'total_students': 5,
                'started_date': timezone.now(),
                'users_id': teacher_user.id,
                'center': center,
            }
        )
        # repair older runs where center was not set (class must belong to the center,
        # otherwise no-class detection in attendance views can't find the session)
        if class_obj.center_id != center.id:
            class_obj.center = center
            class_obj.save(update_fields=['center_id'])

        # ---- students ----
        specs = [
            ('DUMMY Student 1', True),   # Active
            ('DUMMY Student 2', True),   # Active
            ('DUMMY Student 3', True),   # Active
            ('DUMMY Student 4', True),   # Active
            ('DUMMY Student 5', False),  # INACTIVE - to demo student_status
        ]
        students = []
        for i, (name, status) in enumerate(specs, start=1):
            student, created = Student.objects.get_or_create(
                enrollment_id=f'DUMMY-ENR-{i:05d}',
                defaults={
                    'full_name': name,
                    'age': 10,
                    'gender': 'Male' if i % 2 else 'Female',
                    'status': status,
                    'grade': '5th',
                    'active_class_status': True,
                    'last_class': '5th',
                    'father_name': f'DUMMY Father {i}',
                    'full_address': 'DUMMY Test Village',
                    'date_of_birth': f'2016-01-0{i}',
                    'phone_number': f'999999001{i}',
                    'father_mobile_number': f'999999001{i}',
                    'mother_mobile_number': f'999999002{i}',
                    'aadhar_number': f'9999000{i}0000',
                    'category': 'General',
                    'bpl': False,
                    'manual_attendance': 0,
                    'counter': 0,
                    'roll_number': 900 + i,
                    'joining_date': timezone.now(),
                    'district': district,
                    'vidhan_sabha': vidhan_sabha,
                    'panchayat': panchayat,
                    'village': village,
                    'center': center,
                    'school': school,
                    'created_by': 1,
                    'created_on': timezone.now(),
                }
            )
            if created:
                self.stdout.write(f'  Created student: {name} (ID: {student.id}, status: {status})')
            students.append(student)

        # ---- attendance for target date ----
        # Idempotent: wipe this dummy center's attendance rows for the date, then re-create
        deleted, _ = StudentAttendance.objects.filter(
            center=center,
            scan_date__date=target_date,
        ).delete()
        if deleted:
            self.stdout.write(f'  Removed {deleted} old dummy attendance row(s) for {target_date}')

        scan_base = timezone.now().replace(
            year=target_date.year, month=target_date.month, day=target_date.day,
            hour=10, minute=0, second=0, microsecond=0,
        )
        plan = [
            (students[0], True, 'AUTO'),    # Present, QR
            (students[1], True, 'AUTO'),    # Present, QR
            (students[2], True, 'MANUAL'),  # Present, Manual
            (students[3], False, 'MANUAL'), # Absent marker
            (students[4], True, 'AUTO'),    # Present but student is Inactive
        ]
        for student, present, att_type in plan:
            StudentAttendance.objects.create(
                scan_date=scan_base,
                type=present,
                status=True,
                attendance_type=att_type,
                class_obj=class_obj,
                student=student,
                center=center,
                user_id=teacher_user.id,
                device_info='DUMMY-SEEDER',
                manual_reason=None if present else 'Dummy absent test case',
                created_by=1,
                created_on=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Dummy data ready for {target_date}'
        ))
        self.stdout.write(f'  center_id : {center.id}  (DUMMY Test Center)')
        self.stdout.write(f'  teacher   : {teacher_user.name} (User ID: {teacher_user.id})')
        self.stdout.write(f'  students  : {len(students)} (4 Present incl. 1 Inactive, 1 Absent)')

        self.stdout.write('\nTest the API (from allowed IP or localhost):')
        self.stdout.write(
            '  1) POST /api/generate-center-attendance-token/\n'
            '     headers: Username: <FI_API_USERNAME from .env>, '
            'Password: <FI_API_PASSWORD from .env>\n'
            f'     body: {{"deviceid": "dummy-device"}}'
        )
        self.stdout.write(
            '  2) POST /api/center-attendance/\n'
            '     headers: Authorization: Bearer <access_token>\n'
            f'     body: {{"center_id": {center.id}, "attendance_date": "{target_date}"}}'
        )

    # ------------------------------------------------------------------
    def clear_dummy(self):
        """Delete everything this command created (DUMMY-prefixed)."""
        from django.db import connection

        with connection.cursor():
            pass

        att = StudentAttendance.objects.filter(
            student__full_name__startswith='DUMMY Student'
        )
        count = att.count()
        att.delete()
        Student.objects.filter(full_name__startswith='DUMMY Student').delete()
        ClassModel.objects.filter(class_enrolment_id='DUMMY-CLS-001').delete()
        teacher_user = User.objects.filter(phone_number='9999990001').first()
        if teacher_user:
            Teacher.objects.filter(user=teacher_user).delete()
            teacher_user.delete()
        Center.objects.filter(center_name='DUMMY Test Center').delete()
        School.objects.filter(school_name='DUMMY Test School').delete()
        Village.objects.filter(name='DUMMY Test Village').delete()
        Panchayat.objects.filter(name='DUMMY Test Panchayat').delete()
        VidhanSabha.objects.filter(name='DUMMY Test VS').delete()
        District.objects.filter(name='DUMMY Test District').delete()
        self.stdout.write(self.style.SUCCESS(
            f'[OK] Dummy data removed ({count} attendance rows deleted)'
        ))
