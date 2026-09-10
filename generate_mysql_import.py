#!/usr/bin/env python3
"""
Generate a raw MySQL .sql script from All_Coordinators_Issues_v8.xlsx so the
data can be inserted directly with the mysql client - no Django ORM needed:

    mysql -u <user> -p eksesreshtha < import_from_excel.sql

What it generates (in order, all idempotent with INSERT ... SELECT ... WHERE NOT EXISTS):
  1. Role (TEACHER / REGIONAL_ADMIN)
  2. District, VidhanSabha, Panchayat, Village   (correct hierarchy placement)
  3. School
  4. RegionalAdmin Users (from column A/B, real phone numbers)
  5. RegionalAdmin rows (district + vidhan_sabha matched)
  6. Centers (with their own district/VS/panchayat/village)
  7. Teacher Users + Teacher rows
  8. Students
  9. CenterAssignUser (teacher type=3, regional admin type=2)

Notes:
  - District/VidhanSabha/Panchayat/Village have unique GUID columns, so a
    deterministic GUID (hash of the area names) makes re-runs safe.
  - Users.PhoneNumber is UNIQUE -> teacher/RA users are matched on phone.
  - Center.CenterName is UNIQUE -> matched on name.
  - Student EnrollmentId is UNIQUE -> deterministic per row order.
  - Same-name panchayats/villages in different districts/VS are handled via
    their (name, district[, panchayat]) area keys.
  - Passwords are SHA256(Firstname@123#) - same scheme as the Django import.
"""
import hashlib
import os
import sys
from datetime import datetime

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'EkSeSreshtha.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import openpyxl
from collections import defaultdict

EXCEL_FILE = 'All_Coordinators_Issues_v11.xlsx'
SHEET = '1. Full Data'
OUT_FILE = 'import_from_excel.sql'
CREATED_BY = 1


def esc(s):
    """Escape a string for a MySQL single-quoted literal."""
    if s is None:
        return ''
    return (str(s).replace('\\', '\\\\').replace("'", "''"))


def sq(s):
    """Quoted SQL string literal (or NULL for empty)."""
    return sqn(s)


def sqn(s):
    """Quoted SQL string literal (or NULL for empty) - no brace."""
    if s is None or str(s).strip() == '':
        return 'NULL'
    return f"'{esc(s)}'"


def normalize_dob(raw):
    """Return 'YYYY-MM-DD' string or None. Rejects implausible years.
    2-digit years use the standard window (00-29 -> 2000s, 30-99 -> 1900s);
    garbage like 0202/0208/0215 (100-1899) becomes NULL.
    """
    if raw is None:
        return None
    if hasattr(raw, 'strftime'):
        y, m, d = raw.year, raw.month, raw.day
    else:
        s = str(raw).strip()
        if not s:
            return None
        parsed = None
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d',
                    '%m/%d/%Y', '%m/%d/%y', '%d-%m-%y', '%d/%m/%y',
                    '%d.%m.%Y', '%d.%m.%y'):
            try:
                parsed = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
        y, m, d = parsed.year, parsed.month, parsed.day
    # 2-digit year window
    if 0 <= y < 100:
        y = 2000 + y if y <= 29 else 1900 + y
    # implausible year -> no DOB
    current = datetime.now().year
    if y < 1900 or y > current:
        return None
    return f'{y:04d}-{m:02d}-{d:02d}'


def sha256_hex(plain):
    return hashlib.sha256(plain.encode('utf-8')).hexdigest()


def guid(*parts):
    """Deterministic GUID from area names (max 36 chars like Django's)."""
    raw = '|'.join(str(p) for p in parts).lower()
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:32]


def cond(table, where):
    """Idempotent insert: INSERT ... SELECT ... WHERE NOT EXISTS."""
    return where


def main():
    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True, data_only=True)
    ws = wb[SHEET]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    districts = set()
    cons_district = {}                       # constituency -> district
    panchayat_area = defaultdict(set)        # name -> {(district, constituency)}
    village_area = defaultdict(set)          # name -> {(district, cons, panchayat)}
    student_village_area = defaultdict(set)
    centers = {}                             # name -> area dict
    schools = set()
    coordinators = {}                        # name -> phone
    teachers = {}                            # mobile -> teacher dict
    students = []

    for r in rows:
        r = list(r) + [None] * 37
        coord = str(r[0]).strip() if r[0] else ''
        phone = str(r[1]).strip() if r[1] is not None else ''
        dist = str(r[2]).strip() if r[2] else ''
        cons = str(r[3]).strip() if r[3] else ''
        pan = str(r[4]).strip() if r[4] else ''
        vil = str(r[5]).strip() if r[5] else ''
        cen = str(r[6]).strip() if r[6] else ''

        t_name = str(r[9]).strip() if r[9] else ''
        t_gender = str(r[10]).strip() if r[10] else ''
        t_dob = normalize_dob(r[11])
        t_edu = str(r[12]).strip() if r[12] else ''
        t_mobile = str(r[13]).strip() if r[13] else ''
        if t_mobile.endswith('.0'):
            t_mobile = t_mobile[:-2]
        t_addr = str(r[17]).strip() if r[17] else ''

        s_name = str(r[18]).strip() if r[18] else ''
        s_photo = str(r[19]).strip() if r[19] else ''
        s_aadhar = str(r[20]).strip() if r[20] else ''
        s_vil = str(r[21]).strip() if r[21] else ''
        s_class = str(r[22]).strip() if r[22] else ''
        s_dob = normalize_dob(r[23])
        s_gender = str(r[24]).strip() if r[24] else ''
        s_cat = str(r[25]).strip() if r[25] else ''
        s_bpl = str(r[26]).strip() if r[26] else ''
        s_sch = str(r[27]).strip() if r[27] else ''
        s_father = str(r[28]).strip() if r[28] else ''
        s_fmob = str(r[29]).strip() if r[29] else ''
        if s_fmob.endswith('.0'):
            s_fmob = s_fmob[:-2]
        s_focc = str(r[30]).strip() if r[30] else ''
        s_mother = str(r[31]).strip() if r[31] else ''
        s_mmob = str(r[32]).strip() if r[32] else ''
        if s_mmob.endswith('.0'):
            s_mmob = s_mmob[:-2]
        s_mocc = str(r[33]).strip() if r[33] else ''
        s_status = str(r[34]).strip() if r[34] else ''

        if coord:
            coordinators.setdefault(coord, phone)
        if dist:
            districts.add(dist)
        if dist and cons:
            cons_district.setdefault(cons, dist)
            if pan:
                panchayat_area[pan].add((dist, cons))
            if vil:
                village_area[vil].add((dist, cons, pan))
        if s_sch:
            schools.add(s_sch)
        if cen and cen not in centers:
            centers[cen] = {
                'district': dist, 'constituency': cons,
                'panchayat': pan, 'village': vil, 'coordinator': coord,
            }
        # ONE teacher per center - the first one found wins (like the Django import)
        if cen and t_name and t_mobile and centers[cen].get('teacher_mobile') is None:
            centers[cen]['teacher_mobile'] = t_mobile
            if t_mobile not in teachers:
                teachers[t_mobile] = {
                    'name': t_name, 'gender': t_gender, 'dob': t_dob,
                    'education': t_edu, 'mobile': t_mobile, 'address': t_addr,
                    'center': cen, 'district': dist, 'constituency': cons,
                    'panchayat': pan, 'village': vil,
                }
        if s_name and cen:
            students.append({
                'name': s_name, 'photo': s_photo, 'aadhar': s_aadhar,
                'dob': s_dob, 'gender': s_gender, 'class': s_class,
                'category': s_cat, 'bpl': s_bpl, 'father': s_father,
                'father_mobile': s_fmob, 'father_occ': s_focc,
                'mother': s_mother, 'mother_mobile': s_mmob, 'mother_occ': s_mocc,
                'status': s_status,
                'center': cen, 'school': s_sch,
                # student belongs to the CENTER's village/panchayat/area
                'village': vil, 'panchayat': pan, 'district': dist, 'constituency': cons,
            })

    # merge student villages into village_area
    # (removed - villages come from the Center Village column only)

    out = []
    w = out.append
    w('-- ============================================================')
    w('-- Direct MySQL import generated from ' + EXCEL_FILE)
    w('-- Run:  mysql -u <user> -p <db_name> < import_from_excel.sql')
    w('-- Idempotent: re-running inserts nothing new.')
    w('-- ============================================================')
    w('SET NAMES utf8mb4;')
    w('SET SQL_SAFE_UPDATES = 0;')
    w('')
    w('-- ============================================================')
    w('-- PURGE: removes previously imported data (the earlier import put')
    w('-- every VidhanSabha/Panchayat under the wrong district). Users with')
    w('-- TEACHER/REGIONAL_ADMIN roles are removed; admin/superuser kept.')
    w('-- NOTE: this also clears StudentAttendance rows (test data).')
    w('-- ============================================================')
    w('SET FOREIGN_KEY_CHECKS = 0;')
    w('DELETE FROM CenterAssignUser;')
    w('DELETE FROM StudentAttendance;')
    w('DELETE FROM RegionalAdminPanchayat;')
    w('DELETE FROM Student;')
    w('DELETE FROM Teacher;')
    w('DELETE FROM RegionalAdmin;')
    w('DELETE FROM Center;')
    w('DELETE FROM School;')
    w('DELETE FROM Village;')
    w('DELETE FROM Panchayat;')
    w('DELETE FROM VidhanSabha;')
    w('DELETE FROM District;')
    w("DELETE FROM Users WHERE RoleId IN (SELECT Id FROM Role WHERE RoleCode IN ('TEACHER', 'REGIONAL_ADMIN'));")
    w('SET FOREIGN_KEY_CHECKS = 1;')
    w('')
    w('SET FOREIGN_KEY_CHECKS = 0;')
    w('START TRANSACTION;')
    w('')

    # helper snippets (SQL expressions) -------------------------------
    DIST_ID = lambda d: (f"(SELECT Id FROM District d WHERE d.Name = {sqn(d)} LIMIT 1)")
    VS_ID = lambda c: (f"(SELECT Id FROM VidhanSabha v WHERE v.Name = {sqn(c)} LIMIT 1)")
    PAN_ID = lambda p, d: (
        f"(SELECT Id FROM Panchayat p WHERE p.Name = {sqn(p)} "
        f"AND p.DistrictId = {DIST_ID(d)} LIMIT 1)"
    )
    VIL_ID = lambda v, d, p: (
        f"(SELECT Id FROM Village vi WHERE vi.Name = {sqn(v)} "
        f"AND vi.DistrictId = {DIST_ID(d)} "
        f"AND vi.PanchayatId = {PAN_ID(p, d)} LIMIT 1)"
    )
    USER_ID = lambda m: (f"(SELECT Id FROM Users u WHERE u.PhoneNumber = {sqn(m)} LIMIT 1)")
    CENTER_ID = lambda c: (f"(SELECT Id FROM Center ce WHERE ce.CenterName = {sqn(c)} LIMIT 1)")
    ROLE_ID = lambda c: (f"(SELECT Id FROM Role r WHERE r.RoleCode = {sqn(c)} LIMIT 1)")
    SCH_ID = lambda s: (f"(SELECT Id FROM School s WHERE s.SchoolName = {sqn(s)} LIMIT 1)")

    # ---- 1. Districts ----
    w('-- 1) Districts')
    for d in sorted(districts):
        w(
            f"INSERT INTO District (DistrictGuidId, Name, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(guid('DIST', d))}, {sqn(d)}, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM District WHERE Name = {sqn(d)});"
        )
    w('')

    # ---- 2. VidhanSabhas (own district!) ----
    w('-- 2) VidhanSabhas (each in its own district)')
    for c in sorted(cons_district):
        d = cons_district[c]
        w(
            f"INSERT INTO VidhanSabha (VidhanSabhaGuidId, Name, DistrictId, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(guid('VS', d, c))}, {sqn(c)}, {DIST_ID(d)}, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM VidhanSabha WHERE Name = {sqn(c)} AND DistrictId = {DIST_ID(d)});"
        )
    w('')

    # ---- 3. Panchayats ----
    w('-- 3) Panchayats (each in its real district + constituency)')
    for p in sorted(panchayat_area):
        for (d, c) in sorted(panchayat_area[p]):
            w(
                f"INSERT INTO Panchayat (PanchayatGuidId, Name, DistrictId, VidhanSabhaId, Status, CreatedBy, CreatedOn) "
                f"SELECT {sqn(guid('PAN', d, c, p))}, {sqn(p)}, {DIST_ID(d)}, {VS_ID(c)}, 1, {CREATED_BY}, NOW() FROM DUAL "
                f"WHERE NOT EXISTS (SELECT 1 FROM Panchayat WHERE Name = {sqn(p)} AND DistrictId = {DIST_ID(d)});"
            )
    w('')

    # ---- 4. Villages ----
    w('-- 4) Villages (each in its real district + constituency + panchayat)')
    for v in sorted(village_area):
        for (d, c, p) in sorted(village_area[v]):
            w(
                f"INSERT INTO Village (VillageGuidId, Name, DistrictId, VidhanSabhaId, PanchayatId, Status, CreatedBy, CreatedOn) "
                f"SELECT {sqn(guid('VIL', d, c, p, v))}, {sqn(v)}, {DIST_ID(d)}, {VS_ID(c)}, {PAN_ID(p, d)}, 1, {CREATED_BY}, NOW() FROM DUAL "
                f"WHERE NOT EXISTS (SELECT 1 FROM Village WHERE Name = {sqn(v)} AND DistrictId = {DIST_ID(d)} AND PanchayatId = {PAN_ID(p, d)});"
            )
    w('')

    # ---- 5. Schools ----
    w('-- 5) Schools')
    for s in sorted(schools):
        w(
            f"INSERT INTO School (SchoolName, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(s)}, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM School WHERE SchoolName = {sqn(s)});"
        )
    w('')

    # ---- 6. Regional Admin users ----
    w('-- 6) Regional Admin Users (phone from column B)')
    for i, (name, phone) in enumerate(sorted(coordinators.items()), start=1):
        first = name.split()[0] if name else 'Admin'
        pwd = sha256_hex(f'{first.capitalize()}@123#')
        w(
            f"INSERT INTO Users (EnrolmentRollId, Name, RoleId, PhoneNumber, WhatsApp, Password, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(f'RA-DIRECT-{i:03d}')}, {sqn(name)}, {ROLE_ID('REGIONAL_ADMIN')}, {sqn(phone)}, {sqn(phone)}, {sqn(pwd)}, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM Users WHERE PhoneNumber = {sqn(phone)});"
        )
    w('')

    # ---- 7. RegionalAdmin rows ----
    w('-- 7) RegionalAdmin rows (district + vidhan sabha matched via column A areas)')
    # derive each coordinator's area from centers
    coord_area = {}
    for c_name, c in centers.items():
        coord_area.setdefault(c['coordinator'], (c['district'], c['constituency']))
    for name, phone in sorted(coordinators.items()):
        d, c = coord_area.get(name, (None, None))
        if not d:
            continue
        w(
            f"INSERT INTO RegionalAdmin (RegionalAdminGuidId, UserId, DistrictId, VidhanSabhaId, Contact, AssignedRegionalAdminStatus, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(guid('RA', name))}, {USER_ID(phone)}, {DIST_ID(d)}, {VS_ID(c)}, {sqn(phone)}, 1, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM RegionalAdmin WHERE UserId = {USER_ID(phone)});"
        )
    w('')

    # ---- 8. Centers ----
    w('-- 8) Centers (own district/VS/panchayat/village)')
    for i, (c_name, c) in enumerate(sorted(centers.items()), start=1):
        d, cns = c['district'], c['constituency']
        p, v = c['panchayat'], c['village']
        ra_user = coordinators.get(c['coordinator'])
        w(
            f"INSERT INTO Center (CenterGuidId, CenterName, DistrictId, VidhanSabhaId, PanchayatId, VillageId, Status, ClassStatus, LocationStatus, AssignedTeachers, AssignedRegionalAdmin, CreatedBy, CreatedOn) "
            f"SELECT {sqn(guid('CEN', c_name))}, {sqn(c_name)}, {DIST_ID(d)}, {VS_ID(cns)}, {PAN_ID(p, d)}, {VIL_ID(v, d, p)}, 1, 1, 'PENDING', 0, {USER_ID(ra_user)}, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM Center WHERE CenterName = {sqn(c_name)});"
        )
    w('')

    # ---- 9. Teacher users + Teacher rows ----
    w('-- 9) Teacher Users + Teacher rows')
    for i, (mob, t) in enumerate(sorted(teachers.items()), start=1):
        first = t['name'].split()[0] if t['name'] else 'Teacher'
        pwd = sha256_hex(f'{first.capitalize()}@123#')
        roll = f"{t['name'][:2].upper()}-{t['dob'] or '0000-00-00'}-{('M' if 'm' in (t['gender'] or 'x').lower()[:1] else 'F')}-{mob[-10:]}"
        d, cns = t['district'], t['constituency']
        p, v = t['panchayat'], t['village']
        w(
            f"INSERT INTO Users (EnrolmentRollId, Name, RoleId, PhoneNumber, WhatsApp, Password, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(roll)}, {sqn(t['name'])}, {ROLE_ID('TEACHER')}, {sqn(mob)}, {sqn(mob)}, {sqn(pwd)}, 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM Users WHERE PhoneNumber = {sqn(mob)});"
        )
        w(
            f"INSERT INTO Teacher (TeacherGuidId, UserId, DistrictId, VidhanSabhaId, PanchayatId, VillageId, CenterId, Age, Gender, DateOfBirth, Contact, FullAddress, Education, AssignedTeacherStatus, EnrollmentDate, Status, CreatedBy, CreatedOn) "
            f"SELECT {sqn(guid('TEA', t['name'], mob))}, {USER_ID(mob)}, {DIST_ID(d)}, {VS_ID(cns)}, {PAN_ID(p, d)}, {VIL_ID(v, d, p)}, {CENTER_ID(t['center'])}, "
            f"TIMESTAMPDIFF(YEAR, {sqn(t['dob'])}, CURDATE()), {sqn(t['gender'])}, {sqn(t['dob'])}, {sqn(mob)}, {sqn(t['address'])}, {sqn(t['education'])}, 1, NOW(), 1, {CREATED_BY}, NOW() FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM Teacher WHERE UserId = {USER_ID(mob)});"
        )
        # center.assigned_teachers = teacher user id
        w(
            f"UPDATE Center ce SET ce.AssignedTeachers = {USER_ID(mob)} "
            f"WHERE ce.CenterName = {sqn(t['center'])} AND (ce.AssignedTeachers IS NULL OR ce.AssignedTeachers = 0);"
        )
    w('')

    # ---- 10. Students ----
    w('-- 10) Students')
    now = 'NOW()'
    for i, s in enumerate(students, start=1):
        enr = f"ENR-DIRECT-{i:06d}"
        d, cns = s['district'], s['constituency']
        p, v = s['panchayat'], s['village']
        photo = s['photo']
        photo_path = 'NULL'
        photo_url = 'NULL'
        if photo:
            file_id = photo
            for pat in ('open?id=', 'uc?export=download&id=', '/file/d/', 'uc?id=', 'download?id='):
                if pat in photo:
                    file_id = photo.split(pat)[1].split('&')[0]
                    break
            safe_name = ''.join(ch if ch.isalnum() or ch in ' -' else '' for ch in s['name']).strip().replace(' ', '_')
            safe_center = ''.join(ch if ch.isalnum() or ch in ' -' else '' for ch in s['center']).strip().replace(' ', '_')
            photo_path = sqn(f"profile_pic/{safe_center}_{safe_name}.jpg")
            photo_url = sqn(photo)
        w(
            f"INSERT INTO Student (EnrollmentId, FullName, Age, Gender, Status, WhatsApp, Contact, Counter, Grade, ActiveClassStatus, LastClass, "
            f"FatherName, FullAddress, DateOfBirth, ProfileImage, ProfileImageUrl, PhoneNumber, AadharNumber, ManualAttendance, MotherName, JoiningDate, "
            f"FatherOccupation, MotherMobileNumber, MotherOccupation, Bpl, Category, FatherMobileNumber, roll_number, "
            f"DistrictId, VidhanSabhaId, PanchayatId, VillageId, CenterId, SchoolId, CreatedBy, CreatedOn) "
            f"SELECT {sqn(enr)}, {sqn(s['name'])}, TIMESTAMPDIFF(YEAR, {sqn(s['dob'])}, CURDATE()), {sqn(s['gender'])}, 1, {sqn(s['father_mobile'])}, {sqn(s['father_mobile'])}, 0, {sqn(s['class'])}, 1, {sqn(s['class'])}, "
            f"{sqn(s['father'])}, {sqn(s['village'])}, {sqn(s['dob'])}, {photo_path}, {photo_url}, {sqn(s['father_mobile'])}, {sqn(s['aadhar'])}, 0, {sqn(s['mother'])}, {now}, "
            f"{sqn(s['father_occ'])}, {sqn(s['mother_mobile'])}, {sqn(s['mother_occ'])}, {1 if s['bpl'].lower() == 'yes' else 0}, {sqn(s['category'])}, {sqn(s['father_mobile'])}, {i}, "
            f"{DIST_ID(d)}, {VS_ID(cns)}, {PAN_ID(p, d)}, {VIL_ID(v, d, p)}, {CENTER_ID(s['center'])}, {SCH_ID(s['school'])}, {CREATED_BY}, {now} FROM DUAL "
            f"WHERE NOT EXISTS (SELECT 1 FROM Student WHERE EnrollmentId = {sqn(enr)});"
        )
    w('')

    # ---- 11. CenterAssignUser ----
    w('-- 11) CenterAssignUser (teacher=3, regional admin=2)')
    for c_name, c in sorted(centers.items()):
        t = next((t for t in teachers.values() if t['center'] == c_name), None)
        if t:
            w(
                f"INSERT INTO CenterAssignUser (UsersId, Type, Date, Status, CenterId, CreatedBy, CreatedOn) "
                f"SELECT {USER_ID(t['mobile'])}, 3, NOW(), 1, {CENTER_ID(c_name)}, {CREATED_BY}, NOW() FROM DUAL "
                f"WHERE NOT EXISTS (SELECT 1 FROM CenterAssignUser WHERE UsersId = {USER_ID(t['mobile'])} AND CenterId = {CENTER_ID(c_name)} AND Type = 3);"
            )
        ra_user = coordinators.get(c['coordinator'])
        if ra_user:
            w(
                f"INSERT INTO CenterAssignUser (UsersId, Type, Date, Status, CenterId, CreatedBy, CreatedOn) "
                f"SELECT {USER_ID(ra_user)}, 2, NOW(), 1, {CENTER_ID(c_name)}, {CREATED_BY}, NOW() FROM DUAL "
                f"WHERE NOT EXISTS (SELECT 1 FROM CenterAssignUser WHERE UsersId = {USER_ID(ra_user)} AND CenterId = {CENTER_ID(c_name)} AND Type = 2);"
            )
    w('')

    w('COMMIT;')
    w('SET FOREIGN_KEY_CHECKS = 1;')
    w('SET SQL_SAFE_UPDATES = 1;')
    w('')

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f'Generated {OUT_FILE} ({len(out)} statements)')
    print(f'  districts={len(districts)} vidhan_sabhas={len(cons_district)} panchayats={len(panchayat_area)} '
          f'villages={len(village_area)} schools={len(schools)} centers={len(centers)} '
          f'ras={len(coordinators)} teachers={len(teachers)} students={len(students)}')


if __name__ == '__main__':
    main()
