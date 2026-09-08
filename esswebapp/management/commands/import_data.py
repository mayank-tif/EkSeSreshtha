#!/usr/bin/env python3
"""
Django management command to import Rajeev Kumar ESS Center data.
Run: python manage.py import_data
"""
import os
import re
import requests
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from django.conf import settings
from django.utils import timezone

from APIS.models import (
    District, VidhanSabha, Panchayat, Village, Center,
    School, Teacher, RegionalAdmin, Student, User, Role,
    CenterAssignUser
)


# Constants for password hashing
SHA256_HEX_LENGTH = 64


def hash_password(password):
    """
    Hash a password using SHA256.
    If the password is already a SHA256 hex string, return it as-is.
    """
    if password in (None, ""):
        return password
    password = str(password)
    if len(password) == SHA256_HEX_LENGTH and all(ch in "0123456789abcdefABCDEF" for ch in password):
        return password.lower()
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = 'Import Rajeev Kumar ESS Center data with photo downloads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default='All_Coordinators_Issues_v8.xlsx',
            help='Path to Excel file (default: All_Coordinators_Issues_v8.xlsx)'
        )
        parser.add_argument(
            '--sheet-name',
            type=str,
            default='FinalData',
            help='Sheet name to import (default: FinalData)'
        )
        parser.add_argument(
            '--download-photos',
            action='store_true',
            help='Download student photos from Google Drive'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate data without saving'
        )
        parser.add_argument(
            '--skip-hierarchy',
            action='store_true',
            help='Skip hierarchy creation (District, VidhanSabha, etc.)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before import (USE WITH CAUTION)'
        )
        parser.add_argument(
            '--export-passwords',
            action='store_true',
            help='Export teacher passwords to CSV after import'
        )
        parser.add_argument(
            '--fix-fk',
            action='store_true',
            help='Fix foreign key constraints before import'
        )

    def handle(self, *args, **options):
        self.excel_file = options['excel_file']
        self.sheet_name = options['sheet_name']
        self.download_photos = options['download_photos']
        self.dry_run = options['dry_run']
        self.skip_hierarchy = options['skip_hierarchy']
        self.clear_data = options['clear']
        self.export_passwords = options['export_passwords']
        self.fix_fk = options['fix_fk']

        # Store plain passwords for export
        self.plain_passwords = {}
        # coordinator name -> RA User (filled by create_regional_admins)
        self.coord_ra_user = {}
        # created-item totals for the final summary
        self.created_counts = {}

        self.stdout.write(self.style.NOTICE('=' * 60))
        self.stdout.write(self.style.NOTICE('Importing Rajeev Kumar ESS Center Data'))
        self.stdout.write(self.style.NOTICE('=' * 60))

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        try:

            # Everything inside a single atomic transaction
            with transaction.atomic():
                self.stdout.write(self.style.NOTICE('Starting atomic transaction...'))
                self.import_data()
                self.stdout.write(self.style.NOTICE('Transaction completed successfully'))
            
            self.stdout.write(self.style.SUCCESS('\n[OK] Import completed successfully!'))
            
            # Download photos outside the main transaction
            self.download_student_photos()

            # Export teacher passwords if requested (outside transaction)
            self.export_teacher_passwords()
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n[FAIL] Import failed: {e}'))
            import traceback
            traceback.print_exc()
            raise CommandError(str(e))

    def import_data(self):
        import openpyxl

        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        self.clear_existing_data()
        self.stdout.write(self.style.SUCCESS('Existing data cleared'))

        self.stdout.write(f'\nLoading Excel: {self.excel_file}')
        # data_only=True so VLOOKUP formulas (e.g. RA phone column) yield cached values
        wb = openpyxl.load_workbook(self.excel_file, read_only=True, data_only=True)
        if self.sheet_name not in wb.sheetnames:
            raise CommandError(
                f'Sheet {self.sheet_name!r} not found. Available: {wb.sheetnames}'
            )
        ws = wb[self.sheet_name]

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        self.stdout.write(f'Found {len(rows)} data rows')

        self.parse_data(rows)

        self.create_distinct_hierarchy()

        # Validate coordinator/RA data BEFORE writing anything.
        # Any error raises -> the atomic transaction rolls everything back.
        self.validate_regional_admins()

        self.create_regional_admins()
        self.create_centers()
        self.create_schools()
        self.create_teachers()
        self.create_students()
        self.create_center_assignments()

        wb.close()

    def clear_existing_data(self):
        """Clear existing data with proper order respecting foreign keys"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            CenterAssignUser.objects.all().delete()
            Student.objects.all().delete()
            Teacher.objects.all().delete()
            RegionalAdmin.objects.all().delete()
            Center.objects.all().delete()
            Village.objects.all().delete()
            Panchayat.objects.all().delete()
            VidhanSabha.objects.all().delete()
            District.objects.all().delete()
            School.objects.all().delete()
            User.objects.filter(role__role_code='TEACHER').delete()
            User.objects.filter(role__role_code='REGIONAL_ADMIN').delete()
            
            with connection.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                
        except Exception as e:
            # Never let the cleanup query mask the original error
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            except Exception:
                pass
            raise

    def parse_data(self, rows):
        """Parse Excel rows into structured data"""
        self.district_names = set()
        self.constituency_names = set()
        self.panchayat_names = set()
        self.village_names = set()

        self.centers = {}
        self.schools = {}
        self.students = []

        # Regional Admin data parsed from the same sheet:
        # col A = coordinator name (canonical), col B = their phone number
        self.coordinators = {}

        for row in rows:
            # Pad short rows so indexing never fails
            row = list(row) + [None] * max(0, 37 - len(row))

            # Column mapping (0-indexed) for All_Coordinators_Issues_v8.xlsx (FinalData):
            # 0=Co-ordinator (Sheet) [RA name], 1=Mobile Number [RA phone],
            # 2=District, 3=Constituency, 4=Gram Panchayat, 5=Center Village,
            # 6=Center Name, 7=Co-ordinator Name (legacy spelling),
            # 8=Center Opening Date, 9=Teacher Name, 10=Gender, 11=DOB,
            # 12=Education, 13=Teacher Mobile, 14=WhatsApp, 15=Guardian Name,
            # 16=Guardian Phone, 17=Teacher Address, 18=Student Name, 19=Photo,
            # 20=Aadhar, 21=Student Village, 22=Class, 23=Student DOB,
            # 24=Gender, 25=Category, 26=BPL, 27=School, 28=Father Name,
            # 29=Father Mobile, 30=Father Occupation, 31=Mother Name,
            # 32=Mother Mobile, 33=Mother Occupation, 34=Old/New Student
            coordinator_name = str(row[0]).strip() if row[0] else ''
            ra_phone = self.clean_mobile(row[1])
            legacy_coordinator_name = str(row[7]).strip() if row[7] else ''

            district_name = str(row[2]).strip() if row[2] else ''
            constituency_name = str(row[3]).strip() if row[3] else ''
            panchayat_name = str(row[4]).strip() if row[4] else ''
            village_name = str(row[5]).strip() if row[5] else ''
            center_name = str(row[6]).strip() if row[6] else ''

            school_name = str(row[27]).strip() if row[27] else ''

            if coordinator_name:
                info = self.coordinators.setdefault(coordinator_name, {
                    'phone': '',
                    'areas': set(),
                    'legacy_names': set(),
                    'rows': 0,
                })
                info['rows'] += 1
                if ra_phone:
                    if info['phone'] and info['phone'] != ra_phone:
                        self.stdout.write(self.style.ERROR(
                            f"  Conflicting phone numbers for coordinator '{coordinator_name}': "
                            f"{info['phone']} vs {ra_phone}"
                        ))
                    info['phone'] = ra_phone
                if legacy_coordinator_name and legacy_coordinator_name != coordinator_name:
                    info['legacy_names'].add(legacy_coordinator_name)
                if district_name or constituency_name:
                    info['areas'].add((district_name, constituency_name))

            if district_name:
                self.district_names.add(district_name)
            if constituency_name:
                self.constituency_names.add(constituency_name)
            if panchayat_name:
                self.panchayat_names.add(panchayat_name)
            if village_name:
                self.village_names.add(village_name)

            teacher_name = str(row[9]).strip() if row[9] else ''
            teacher_gender = str(row[10]).strip() if row[10] else ''
            teacher_dob = self.format_date(row[11])
            teacher_education = str(row[12]).strip() if row[12] else ''
            teacher_mobile = self.clean_mobile(row[13])
            teacher_whatsapp = self.clean_mobile(row[14])
            teacher_guardian = str(row[15]).strip() if row[15] else ''
            teacher_guardian_phone = self.clean_mobile(row[16])
            teacher_address = str(row[17]).strip() if row[17] else ''

            student_name = str(row[18]).strip() if row[18] else ''
            student_photo_url = str(row[19]).strip() if row[19] else ''
            student_aadhar = str(row[20]).strip() if row[20] else ''
            student_village = str(row[21]).strip() if row[21] else ''
            student_class = str(row[22]).strip() if row[22] else ''
            student_dob = self.format_date(row[23])
            student_gender = str(row[24]).strip() if row[24] else ''
            student_category = str(row[25]).strip() if row[25] else ''
            student_bpl = str(row[26]).strip() if row[26] else ''
            student_father = str(row[28]).strip() if row[28] else ''
            student_father_mobile = self.clean_mobile(row[29])
            student_father_occ = str(row[30]).strip() if row[30] else ''
            student_mother = str(row[31]).strip() if row[31] else ''
            student_mother_mobile = self.clean_mobile(row[32])
            student_mother_occ = str(row[33]).strip() if row[33] else ''
            student_status = str(row[34]).strip() if row[34] else ''

            student_age = self.calculate_age(student_dob)

            if not student_village:
                student_village = village_name

            if center_name and center_name not in self.centers:
                self.centers[center_name] = {
                    'name': center_name,
                    'district': district_name,
                    'constituency': constituency_name,
                    'panchayat': panchayat_name,
                    'village': village_name,
                    'coordinator': coordinator_name,
                    'teacher': None,
                    'teacher_details': None
                }

            if center_name and teacher_name and teacher_mobile:
                if center_name not in self.centers:
                    self.centers[center_name] = {
                        'name': center_name,
                        'district': district_name,
                        'constituency': constituency_name,
                        'panchayat': panchayat_name,
                        'village': village_name,
                        'coordinator': coordinator_name,
                        'teacher': None,
                        'teacher_details': None
                    }
                
                if self.centers[center_name].get('teacher') is None:
                    self.centers[center_name]['teacher'] = teacher_mobile
                    self.centers[center_name]['teacher_details'] = {
                        'name': teacher_name,
                        'gender': teacher_gender,
                        'dob': teacher_dob,
                        'education': teacher_education,
                        'mobile': teacher_mobile,
                        'whatsapp': teacher_whatsapp,
                        'guardian': teacher_guardian,
                        'guardian_phone': teacher_guardian_phone,
                        'address': teacher_address,
                    }

            if school_name and school_name not in self.schools:
                self.schools[school_name] = school_name

            if student_name and center_name:
                self.students.append({
                    'name': student_name,
                    'photo_url': student_photo_url,
                    'aadhar': student_aadhar,
                    'age': student_age,
                    'gender': student_gender,
                    'dob': student_dob,
                    'class': student_class,
                    'category': student_category,
                    'bpl': student_bpl,
                    'father_name': student_father,
                    'father_mobile': student_father_mobile,
                    'father_occupation': student_father_occ,
                    'mother_name': student_mother,
                    'mother_mobile': student_mother_mobile,
                    'mother_occupation': student_mother_occ,
                    'status': student_status,
                    'center_name': center_name,
                    'school_name': school_name,
                    'village_name': student_village,
                    'panchayat_name': panchayat_name,
                })

        # Log distinct counts
        self.stdout.write(f'Distinct values found:')
        self.stdout.write(f'  Districts: {len(self.district_names)} - {sorted(self.district_names)}')
        self.stdout.write(f'  Constituencies: {len(self.constituency_names)} - {sorted(self.constituency_names)}')
        self.stdout.write(f'  Panchayats: {len(self.panchayat_names)} - {sorted(self.panchayat_names)}')
        self.stdout.write(f'  Villages: {len(self.village_names)} - {sorted(self.village_names)}')
        self.stdout.write(f'  Centers: {len(self.centers)}')
        self.stdout.write(f'  Schools: {len(self.schools)}')
        self.stdout.write(f'  Students: {len(self.students)}')
        self.stdout.write(f'  Regional Admins (coordinators): {len(self.coordinators)}')

    def create_distinct_hierarchy(self):
        """
        Create distinct District, VidhanSabha, Panchayat, Village entries
        based on the unique values from Excel
        """
        if self.skip_hierarchy:
            return

        self.district_map = {}
        self.vidhan_sabha_map = {}
        self.panchayat_map = {}
        self.village_map = {}

        for district_name in self.district_names:
            if not district_name:
                continue
            district, created = District.objects.get_or_create(
                name=district_name,
                defaults={
                    'district_guid_id': f'DIST-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.district_map)+1:03d}',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.district_map[district_name] = district
            if created:
                self.created_counts['districts'] = self.created_counts.get('districts', 0) + 1
                self.stdout.write(f'  Created District: {district_name} (ID: {district.id})')
            else:
                self.stdout.write(f'  Using existing District: {district_name} (ID: {district.id})')

        # Use the first district as default (Hamirpur)
        default_district = next(iter(self.district_map.values())) if self.district_map else None
        if not default_district:
            # Create default district if none exists
            default_district, _ = District.objects.get_or_create(
                name="Hamirpur",
                defaults={
                    'district_guid_id': f'DIST-{timezone.now().strftime("%Y%m%d%H%M%S")}-001',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.district_map["Hamirpur"] = default_district

        self.default_district = default_district

        # 2. Create all VidhanSabhas (Constituencies)
        for constituency_name in self.constituency_names:
            if not constituency_name:
                continue
            vs, created = VidhanSabha.objects.get_or_create(
                name=constituency_name,
                district=self.default_district,
                defaults={
                    'vidhan_sabha_guid_id': f'VS-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.vidhan_sabha_map)+1:03d}',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.vidhan_sabha_map[constituency_name] = vs
            if created:
                self.created_counts['vidhan_sabhas'] = self.created_counts.get('vidhan_sabhas', 0) + 1
                self.stdout.write(f'  Created VidhanSabha: {constituency_name} (ID: {vs.id})')
            else:
                self.stdout.write(f'  Using existing VidhanSabha: {constituency_name} (ID: {vs.id})')

        # Use the first vidhan_sabha as default
        default_vs = next(iter(self.vidhan_sabha_map.values())) if self.vidhan_sabha_map else None
        if not default_vs:
            default_vs, _ = VidhanSabha.objects.get_or_create(
                name="Hamirpur",
                district=self.default_district,
                defaults={
                    'vidhan_sabha_guid_id': f'VS-{timezone.now().strftime("%Y%m%d%H%M%S")}-001',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.vidhan_sabha_map["Hamirpur"] = default_vs

        self.default_vidhan_sabha = default_vs

        # 3. Create all Panchayats
        for panchayat_name in self.panchayat_names:
            if not panchayat_name:
                continue
            # Find the constituency for this panchayat (use first one or default)
            vs = next(iter(self.vidhan_sabha_map.values())) if self.vidhan_sabha_map else default_vs
            
            panchayat, created = Panchayat.objects.get_or_create(
                name=panchayat_name,
                district=default_district,
                vidhan_sabha=vs,
                defaults={
                    'panchayat_guid_id': f'PAN-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.panchayat_map)+1:03d}',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.panchayat_map[panchayat_name] = panchayat
            if created:
                self.created_counts['panchayats'] = self.created_counts.get('panchayats', 0) + 1
                self.stdout.write(f'  Created Panchayat: {panchayat_name} (ID: {panchayat.id})')
            else:
                self.stdout.write(f'  Using existing Panchayat: {panchayat_name} (ID: {panchayat.id})')

        # 4. Create all Villages
        for village_name in self.village_names:
            if not village_name:
                continue
            # Find panchayat for this village
            panchayat = self.panchayat_map.get(village_name)
            if not panchayat:
                # Try to find by name or create
                panchayat, _ = Panchayat.objects.get_or_create(
                    name=village_name,
                    district=default_district,
                    vidhan_sabha=default_vs,
                    defaults={
                        'panchayat_guid_id': f'PAN-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.panchayat_map)+1:03d}',
                        'status': True,
                        'created_on': timezone.now(),
                        'created_by': 1
                    }
                )
                self.panchayat_map[village_name] = panchayat
            
            village, created = Village.objects.get_or_create(
                name=village_name,
                district=default_district,
                vidhan_sabha=default_vs,
                panchayat=panchayat,
                defaults={
                    'village_guid_id': f'VIL-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.village_map)+1:03d}',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1
                }
            )
            self.village_map[village_name] = village
            if created:
                self.created_counts['villages'] = self.created_counts.get('villages', 0) + 1
                self.stdout.write(f'  Created Village: {village_name} (ID: {village.id})')
            else:
                self.stdout.write(f'  Using existing Village: {village_name} (ID: {village.id})')

        self.stdout.write(self.style.SUCCESS(
            f'Hierarchy summary: '
            f'{len(self.district_map)} districts, '
            f'{len(self.vidhan_sabha_map)} vidhan_sabhas, '
            f'{len(self.panchayat_map)} panchayats, '
            f'{len(self.village_map)} villages'
        ))

    def validate_regional_admins(self):
        """
        Sanity-check the Regional Admin data found in the FIRST sheet
        (column A = coordinator name, column B = phone) BEFORE anything
        is written:
          - every coordinator must have a valid 10-digit phone
          - a coordinator must not span multiple districts
          - one phone must not be shared by two coordinators
        Any error raises -> the whole atomic transaction rolls back.
        """
        errors = []
        warnings = []

        for name, info in sorted(self.coordinators.items()):
            phone = info['phone']
            if not phone or len(phone) != 10 or not phone.isdigit():
                errors.append(
                    f"Coordinator '{name}': missing/invalid phone number in "
                    f"'Mobile Number' column (column B)"
                )
            districts = {d for (d, c) in info['areas'] if d}
            if len(districts) > 1:
                errors.append(
                    f"Coordinator '{name}': spans multiple districts "
                    f"{sorted(districts)} - cannot assign a single district"
                )
            if not info['areas']:
                errors.append(
                    f"Coordinator '{name}': no district/constituency data found on its rows"
                )
            for legacy in sorted(info['legacy_names']):
                warnings.append(
                    f"Coordinator '{name}': legacy name variant '{legacy}' found in "
                    f"'Co-ordinator Name' column (ignored, '{name}' is canonical)"
                )

        # One phone must map to exactly one coordinator
        by_phone = {}
        for name, info in self.coordinators.items():
            if info['phone']:
                by_phone.setdefault(info['phone'], []).append(name)
        for phone, names in sorted(by_phone.items()):
            if len(names) > 1:
                errors.append(
                    f"Phone {phone} is shared by multiple coordinators: {names}"
                )

        if warnings:
            self.stdout.write(self.style.WARNING('\n=== Regional Admin warnings ==='))
            for w in warnings:
                self.stdout.write(self.style.WARNING(f'  [WARN] {w}'))

        if errors:
            self.stdout.write(self.style.ERROR('\n=== REGIONAL ADMIN MISMATCH REPORT ==='))
            for e in errors:
                self.stdout.write(self.style.ERROR(f'  [MISMATCH] {e}'))
            self.stdout.write(self.style.ERROR(
                '\nImport aborted - nothing was saved (transaction rolled back). '
                'Fix the Excel file and re-run.'
            ))
            raise CommandError(f'{len(errors)} regional admin mismatch(es) found')

        self.stdout.write(self.style.SUCCESS(
            f'  Regional admin validation passed: {len(self.coordinators)} coordinators checked'
        ))

    def create_regional_admins(self):
        """
        Create/update one Regional Admin per coordinator found in the first
        sheet (column A). The phone number comes from column B ('Mobile
        Number') - no random numbers. District and Vidhan Sabha are matched
        from the coordinator's own rows.
        """
        role = Role.objects.get(role_code='REGIONAL_ADMIN')
        today = timezone.now().strftime('%Y%m%d')
        created_count = 0
        updated_count = 0

        for seq, (name, info) in enumerate(sorted(self.coordinators.items()), start=1):
            phone = info['phone']
            areas = sorted(info['areas'])                       # [(district, constituency), ...]
            district_name = areas[0][0]
            vs_names = sorted({c for (_, c) in areas})

            district = self.district_map.get(district_name)
            if district is None:
                raise CommandError(
                    f"District '{district_name}' not found for coordinator '{name}'"
                )
            primary_vs = self.vidhan_sabha_map.get(vs_names[0])
            if primary_vs is None:
                raise CommandError(
                    f"Vidhan Sabha '{vs_names[0]}' not found for coordinator '{name}'"
                )

            # --- User (phone number straight from the sheet) ---
            user = User.objects.filter(phone_number=phone).first()
            created = user is None
            if created:
                first_name = name.split()[0] if name else 'Admin'
                plain_password = f'{first_name}@123'
                user = User.objects.create(
                    name=name,
                    role=role,
                    phone_number=phone,
                    whats_app=phone,
                    password=hash_password(plain_password),
                    status=True,
                    created_on=timezone.now(),
                    created_by=1,
                )
                self.plain_passwords[phone] = plain_password
                created_count += 1
            else:
                updated_count += 1
                if user.role_id is None:
                    user.role = role
                    user.save()

            # --- Unique enrollment roll id ---
            if not user.enrolment_roll_id:
                base_id = f'RA-{today}-{seq:03d}'
                roll_id = base_id
                suffix = 1
                while User.objects.filter(enrolment_roll_id=roll_id).exclude(pk=user.pk).exists():
                    roll_id = f'{base_id}-{suffix}'
                    suffix += 1
                user.enrolment_roll_id = roll_id
                user.save()

            # --- RegionalAdmin row (district + vidhan sabha matched) ---
            ra, ra_created = RegionalAdmin.objects.get_or_create(
                user=user,
                defaults={
                    'regional_admin_guid_id': f'regional-admin-{user.id}',
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1,
                }
            )
            ra.district = district
            ra.vidhan_sabha = primary_vs
            ra.contact = phone
            ra.status = True
            ra.save()

            self.coord_ra_user[name] = user
            if created:
                self.created_counts['regional_admins'] = self.created_counts.get('regional_admins', 0) + 1

            vs_note = ''
            if len(vs_names) > 1:
                vs_note = f' (covers {len(vs_names)} constituencies: {vs_names}; primary VS: {vs_names[0]})'
            self.stdout.write(
                f"  RA: {name} | phone {phone} | {district_name} / "
                f"{vs_names[0]}{' | NEW' if created else ' | updated'}{vs_note}"
            )

        self.stdout.write(self.style.SUCCESS(
            f'Regional admins: {created_count} created, {updated_count} updated '
            f'(total {len(self.coordinators)})'
        ))

    def create_centers(self):
        """Create Centers using distinct hierarchy"""
        center_count = 0
        for c_name, c_data in self.centers.items():
            # Get hierarchy objects
            panchayat_name = c_data.get('panchayat', '')
            village_name = c_data.get('village', '')
            
            panchayat = self.panchayat_map.get(panchayat_name)
            village = self.village_map.get(village_name)
            
            # If not found, try to get from database
            if not panchayat and panchayat_name:
                try:
                    panchayat = Panchayat.objects.get(name=panchayat_name)
                    self.panchayat_map[panchayat_name] = panchayat
                except Panchayat.DoesNotExist:
                    panchayat = Panchayat.objects.create(
                        name=panchayat_name,
                        district=self.default_district,
                        vidhan_sabha=self.default_vidhan_sabha,
                        panchayat_guid_id=f'PAN-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.panchayat_map)+1:03d}',
                        status=True,
                        created_on=timezone.now(),
                        created_by=1,
                    )
                    self.panchayat_map[panchayat_name] = panchayat
            
            if not village and village_name:
                try:
                    village = Village.objects.get(name=village_name)
                    self.village_map[village_name] = village
                except Village.DoesNotExist:
                    village = Village.objects.create(
                        name=village_name,
                        district=self.default_district,
                        vidhan_sabha=self.default_vidhan_sabha,
                        panchayat=panchayat,
                        village_guid_id=f'VIL-{timezone.now().strftime("%Y%m%d%H%M%S")}-{len(self.village_map)+1:03d}',
                        status=True,
                        created_on=timezone.now(),
                        created_by=1,
                    )
                    self.village_map[village_name] = village

            try:
                # The center's own coordinator acts as its Regional Admin
                coord_ra = self.coord_ra_user.get(c_data.get('coordinator'))
                center, created = Center.objects.get_or_create(
                    center_name=c_name,
                    defaults={
                        'center_guid_id': f'center-{c_name.lower().replace(" ", "-")}-{center_count+1:03d}',
                        'district': self.default_district,
                        'vidhan_sabha': self.default_vidhan_sabha,
                        'panchayat': panchayat,
                        'village': village,
                        'status': True,
                        'class_status': True,
                        'location_status': 'PENDING',
                        'assigned_teachers': 0,
                        'assigned_regional_admin': coord_ra.id if coord_ra else None,
                        'created_on': timezone.now(),
                        'created_by': 1,
                    }
                )
                self.centers[c_name]['obj'] = center
                if created:
                    center_count += 1
                    self.created_counts['centers'] = self.created_counts.get('centers', 0) + 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  [OK] Center created: {c_name} (ID: {center.id}, RA: {coord_ra.name if coord_ra else None})'
                    ))
                else:
                    self.stdout.write(f'  [--] Center exists: {c_name} (ID: {center.id})')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating center {c_name}: {e}'))
                raise

        self.stdout.write(f'Created/Updated {len(self.centers)} centers ({center_count} new)')

    def create_schools(self):
        """Create Schools"""
        school_count = 0
        for s_name in self.schools:
            school, created = School.objects.get_or_create(
                school_name=s_name,
                defaults={
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1,
                }
            )
            self.schools[s_name] = school
            if created:
                school_count += 1
                self.created_counts['schools'] = self.created_counts.get('schools', 0) + 1
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] School created: {s_name} (ID: {school.id})'
                ))
            else:
                self.stdout.write(f'  [--] School exists: {s_name} (ID: {school.id})')

        self.stdout.write(f'Created/Updated {len(self.schools)} schools ({school_count} new)')

    def create_teachers(self):
        """Create Teachers"""
        teacher_role = Role.objects.get(role_code='TEACHER')
        teacher_count = 0

        for c_name, c_data in self.centers.items():
            teacher_details = c_data.get('teacher_details')
            if not teacher_details:
                continue

            center = c_data['obj']
            village_name = c_data.get('village', '')
            panchayat_name = c_data.get('panchayat', '')
            
            village = self.village_map.get(village_name)
            panchayat = self.panchayat_map.get(panchayat_name)

            t = teacher_details
            
            # Generate plain password: first name + @123
            first_name = t['name'].split()[0] if t['name'] else 'Teacher'
            plain_password = f"{first_name}@123"
            hashed_password = hash_password(plain_password)
            
            # Store plain password for export
            self.plain_passwords[t['mobile']] = plain_password

            # Create User
            # Ensure a unique enrolment_roll_id (Users.EnrolmentRollId has a unique constraint)
            roll_id = self.generate_enrollment_rollid(t['name'], t['dob'], t['gender'], t['mobile'])
            base_roll_id = roll_id
            suffix = 1
            while User.objects.filter(enrolment_roll_id=roll_id).exclude(phone_number=t['mobile']).exists():
                roll_id = f'{base_roll_id}-{suffix}'
                suffix += 1

            user, created = User.objects.get_or_create(
                phone_number=t['mobile'],
                role=teacher_role,
                defaults={
                    'enrolment_roll_id': roll_id,
                    'name': t['name'],
                    'whats_app': t['whatsapp'] or t['mobile'],
                    'password': hashed_password,
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1,
                }
            )

            if created:
                teacher_count += 1
                self.created_counts['teachers'] = self.created_counts.get('teachers', 0) + 1
            else:
                if user.password != hashed_password:
                    user.password = hashed_password
                    user.save()

            # Create Teacher
            teacher, created = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'teacher_guid_id': f'teacher-{user.id}',
                    'district': self.default_district,
                    'vidhan_sabha': self.default_vidhan_sabha,
                    'panchayat': panchayat,
                    'village': village,
                    'center': center,
                    'age': self.calculate_age(t['dob']),
                    'gender': t['gender'],
                    'date_of_birth': t['dob'],
                    'contact': t['mobile'],
                    'full_address': t['address'],
                    'education': t['education'],
                    'guardian_name': t['guardian'],
                    'guardian_number': t['guardian_phone'],
                    'assigned_teacher_status': True,
                    'enrollment_date': timezone.now(),
                    'status': True,
                    'created_on': timezone.now(),
                    'created_by': 1,
                }
            )

            center.assigned_teachers = user.id
            center.save()

            c_data['teacher_user'] = user
            c_data['teacher_obj'] = teacher
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"  [OK] Teacher created: {t['name']} ({t['mobile']}) | roll: {user.enrolment_roll_id} | center: {c_name} (TeacherID: {teacher.id})"
                ))
            else:
                self.stdout.write(
                    f"  [--] Teacher exists: {t['name']} ({t['mobile']}) | center: {c_name}"
                )

        self.stdout.write(f'Created/Updated teachers for {teacher_count} new centers')

    def create_students(self):
        """Create Students"""
        student_count = 0
        for i, s in enumerate(self.students):
            center = self.centers.get(s['center_name'])
            if not center or not center.get('obj'):
                continue

            school = self.schools.get(s['school_name'])
            village = self.village_map.get(s['village_name'])
            panchayat = self.panchayat_map.get(s.get('panchayat_name', ''))

            photo_path = None
            if s['photo_url']:
                file_id = self.extract_drive_id(s['photo_url'])
                if file_id:
                    safe_name = re.sub(r'[^\w\s-]', '', s['name']).strip().replace(' ', '_')
                    safe_center = re.sub(r'[^\w\s-]', '', s['center_name']).strip().replace(' ', '_')
                    photo_path = f"profile_pic/{safe_center}_{safe_name}.jpg"

            enrollment_id = f"ENR-{timezone.now().strftime('%Y%m%d')}-{str(i+1).zfill(6)}"

            student, created = Student.objects.get_or_create(
                enrollment_id=enrollment_id,
                defaults={
                    'full_name': s['name'],
                    'age': s['age'],
                    'gender': s['gender'],
                    'status': True,
                    'whats_app': s['father_mobile'],
                    'contact': s['father_mobile'],
                    'counter': 0,
                    'grade': s['class'],
                    'active_class_status': True,
                    'last_class': s['class'],
                    'father_name': s['father_name'],
                    'full_address': s['village_name'],
                    'date_of_birth': s['dob'],
                    'profile_image': photo_path,
                    'profile_image_url': s['photo_url'],
                    'phone_number': s['father_mobile'],
                    'aadhar_number': s['aadhar'],
                    'manual_attendance': 0,
                    'mother_name': s['mother_name'],
                    'joining_date': timezone.now(),
                    'father_occupation': s['father_occupation'],
                    'mother_mobile_number': s['mother_mobile'],
                    'mother_occupation': s['mother_occupation'],
                    'bpl': s['bpl'].lower() == 'yes' if s['bpl'] else False,
                    'category': s['category'],
                    'father_mobile_number': s['father_mobile'],
                    'roll_number': i + 1,
                    'district': self.default_district,
                    'vidhan_sabha': self.default_vidhan_sabha,
                    'panchayat': panchayat,
                    'village': village,
                    'center': center['obj'],
                    'school': school,
                    'created_by': 1,
                    'created_on': timezone.now(),
                }
            )

            if not created:
                student.full_name = s['name']
                student.profile_image = photo_path
                student.profile_image_url = s['photo_url']
                student.district = self.default_district
                student.vidhan_sabha = self.default_vidhan_sabha
                student.panchayat = panchayat
                student.village = village
                student.center = center['obj']
                student.school = school
                student.save()
                self.stdout.write(
                    f"  [--] Student exists/updated: {s['name']} ({enrollment_id}) | center: {s['center_name']}"
                )
            else:
                student_count += 1
                self.created_counts['students'] = self.created_counts.get('students', 0) + 1
                self.stdout.write(self.style.SUCCESS(
                    f"  [OK] Student created: {s['name']} ({enrollment_id}) | center: {s['center_name']} (StudentID: {student.id})"
                ))

        self.stdout.write(f'Created/Updated {len(self.students)} students ({student_count} new)')

    def create_center_assignments(self):
        """Create CenterAssignUser entries"""
        from APIS.models import CenterAssignUser

        assignment_count = 0

        for c_name, c_data in self.centers.items():
            if c_data.get('teacher_user'):
                center = c_data['obj']
                _, created = CenterAssignUser.objects.get_or_create(
                    users_id=c_data['teacher_user'].id,
                    center=center,
                    type=3,
                    defaults={
                        'date': timezone.now(),
                        'status': True,
                        'created_by': 1,
                        'created_on': timezone.now(),
                    }
                )
                if created:
                    assignment_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  [OK] Teacher assigned: {c_data['teacher_user'].name} -> {c_name}"
                    ))

        # Regional admin assignment: each center gets ITS OWN coordinator's RA user
        for c_name, c_data in self.centers.items():
            center = c_data['obj']
            ra_user = self.coord_ra_user.get(c_data.get('coordinator'))
            if not ra_user:
                self.stdout.write(self.style.WARNING(
                    f'  No regional admin found for center {c_name!r} '
                    f"(coordinator {c_data.get('coordinator')!r} not in column A)"
                ))
                continue
            _, created = CenterAssignUser.objects.get_or_create(
                users_id=ra_user.id,
                center=center,
                type=2,
                defaults={
                    'date': timezone.now(),
                    'status': True,
                    'created_by': 1,
                    'created_on': timezone.now(),
                }
            )
            if created:
                assignment_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  [OK] Regional admin assigned: {ra_user.name} -> {c_name}'
                ))

        self.stdout.write(f'Created {assignment_count} CenterAssignUser entries')
        self.created_counts['center_assignments'] = assignment_count
        self.print_import_summary()

    def print_import_summary(self):
        """Print final totals of everything created by this import."""
        c = self.created_counts
        self.stdout.write('\n' + '=' * 40)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY (items created)'))
        self.stdout.write('=' * 40)
        rows = [
            ('Districts', 'districts'),
            ('Vidhan Sabhas', 'vidhan_sabhas'),
            ('Panchayats', 'panchayats'),
            ('Villages', 'villages'),
            ('Regional Admins', 'regional_admins'),
            ('Centers', 'centers'),
            ('Schools', 'schools'),
            ('Teachers', 'teachers'),
            ('Students', 'students'),
            ('Center Assignments', 'center_assignments'),
        ]
        for label, key in rows:
            self.stdout.write(f'  {label}: {c.get(key, 0)}')
        self.stdout.write('=' * 40)

    def download_student_photos(self):
        """Download photos from Google Drive"""
        self.stdout.write('\nDownloading student photos...')

        media_root = Path(settings.MEDIA_ROOT)
        photo_dir = media_root / 'profile_pic'
        photo_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        failed = 0

        for s in self.students:
            if not s['photo_url']:
                continue

            file_id = self.extract_drive_id(s['photo_url'])
            if not file_id:
                failed += 1
                continue

            safe_name = re.sub(r'[^\w\s-]', '', s['name']).strip().replace(' ', '_')
            safe_center = re.sub(r'[^\w\s-]', '', s['center_name']).strip().replace(' ', '_')
            filename = f"{safe_center}_{safe_name}.jpg"
            output_path = photo_dir / filename

            if output_path.exists():
                continue

            if self.download_from_drive(file_id, output_path):
                downloaded += 1
            else:
                failed += 1

            if (downloaded + failed) % 20 == 0:
                self.stdout.write(f'  Downloaded: {downloaded}, Failed: {failed}')

        self.stdout.write(f'Downloaded: {downloaded}, Failed: {failed}')

    def download_from_drive(self, file_id, output_path):
        """Download file from Google Drive"""
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'

        session = requests.Session()
        try:
            response = session.get(download_url, stream=True, timeout=30)

            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_url = f'{download_url}&confirm={value}'
                    response = session.get(confirm_url, stream=True, timeout=30)
                    break

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    return False

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                return output_path.stat().st_size > 0
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Download failed: {e}'))
            return False

        return False

    def extract_drive_id(self, url):
        """Extract Google Drive file ID"""
        if not url:
            return None
        patterns = [
            r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/uc\?export=download&id=([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
            r'drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)',
            r'drive\.usercontent\.google\.com/download\?id=([a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        if re.match(r'^[a-zA-Z0-9_-]{25,}$', url.strip()):
            return url.strip()
        return None

    def generate_enrollment_rollid(self, name, dob, gender, mobile):
        """Generate enrollment roll ID"""
        first_two = name.strip()[:2].upper() if name.strip() else 'XX'
        dob_clean = dob.replace('/', '-') if dob else '0000-00-00'
        g = gender.strip().lower() if gender else ''
        gender_char = 'M' if g.startswith('m') else 'F' if g.startswith('f') else 'U'
        mobile_clean = mobile[-10:] if mobile else '0000000000'
        return f"{first_two}-{dob_clean}-{gender_char}-{mobile_clean}"

    def calculate_age(self, dob_str):
        """Calculate age from date of birth"""
        if not dob_str:
            return 0
        try:
            from datetime import datetime
            for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d']:
                try:
                    dob = datetime.strptime(dob_str, fmt)
                    today = timezone.now().date()
                    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.year))
                except ValueError:
                    continue
        except Exception:
            pass
        return 0

    def clean_mobile(self, value):
        """Normalize a phone/mobile cell to a digits-only string."""
        if value in (None, ''):
            return ''
        s = str(value).strip()
        if s.endswith('.0'):
            s = s[:-2]
        digits = re.sub(r'\D', '', s)
        return digits[-10:] if len(digits) > 10 else digits

    def format_date(self, value):
        """Normalize a date cell (datetime object or string) to 'YYYY-MM-DD'."""
        if value in (None, ''):
            return ''
        if isinstance(value, (datetime, date)):
            return value.strftime('%Y-%m-%d')
        s = str(value).strip()
        if not s:
            return ''
        for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%y', '%d/%m/%y']:
            try:
                return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        # Excel serial-number date fallback
        try:
            serial = float(s)
            if 20000 < serial < 80000:
                return (date(1899, 12, 30) + timedelta(days=int(serial))).strftime('%Y-%m-%d')
        except ValueError:
            pass
        return s

    def export_teacher_passwords(self):
        """
        Export teacher passwords to CSV.
        This method is called after import completes.
        """
        import csv
        from django.conf import settings
        
        # Output path
        output_path = Path(settings.BASE_DIR) / 'teacher_passwords.csv'
        
        self.stdout.write(f'\nExporting teacher passwords to: {output_path}')
        
        # Get all teachers
        teachers = Teacher.objects.select_related('user', 'center').filter(status=True)
        exported_count = 0
        
        # Create the CSV file
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'User ID', 
                'Name', 
                'Mobile', 
                'Plain Password', 
                'Center', 
                'EnrollmentRollId',
                'Role',
                'Center ID'
            ])
            
            # Write data
            for teacher in teachers:
                user = teacher.user
                mobile = user.phone_number
                
                # Get plain password from stored dict
                if mobile in self.plain_passwords:
                    plain_password = self.plain_passwords[mobile]
                else:
                    # Fallback: generate based on name
                    first_name = user.name.split()[0] if user.name else 'Teacher'
                    plain_password = f"{first_name}@123"
                    self.plain_passwords[mobile] = plain_password
                
                writer.writerow([
                    user.id,
                    user.name,
                    mobile,
                    plain_password,
                    teacher.center.center_name if teacher.center else 'N/A',
                    user.enrolment_roll_id,
                    'Teacher',
                    teacher.center.id if teacher.center else 'N/A'
                ])
                exported_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Teacher passwords exported to: {output_path}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'   Exported {exported_count} teachers'
        ))
        
        # Also print a summary
        self.stdout.write('\n📋 Login Credentials Summary:')
        self.stdout.write('  - Teachers: Use Phone Number as username')
        self.stdout.write('  - Password format: [First Name]@123 (e.g., John@123)')
        self.stdout.write(f'  - CSV file: {output_path}')