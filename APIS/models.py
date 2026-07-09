from django.db import models


class AuditModel(models.Model):
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        abstract = True


class Center(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    center_guid_id = models.CharField(db_column="CenterGuidId", max_length=50, null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)
    village_id = models.IntegerField(db_column="VillageId", null=True, blank=True)
    center_name = models.CharField(db_column="CenterName", max_length=50, null=True, blank=True)
    created_date = models.DateTimeField(db_column="CreatedDate", null=True, blank=True)
    started_date = models.DateTimeField(db_column="StartedDate", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    class_status = models.BooleanField(db_column="ClassStatus", null=True, blank=True)
    assigned_teachers = models.IntegerField(db_column="AssignedTeachers", null=True, blank=True)
    assigned_regional_admin = models.IntegerField(db_column="AssignedRegionalAdmin", null=True, blank=True)

    class Meta:
        db_table = "Center"

    def __str__(self):
        return self.center_name or str(self.id)


class ClassModel(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    class_enrolment_id = models.CharField(db_column="ClassEnrolmentId", max_length=50, null=True, blank=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.IntegerField(db_column="Status", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    total_students = models.IntegerField(db_column="TotalStudents", null=True, blank=True)
    avilable_students = models.IntegerField(db_column="AvilableStudents", null=True, blank=True)
    started_date = models.DateTimeField(db_column="StartedDate", null=True, blank=True)
    end_date = models.DateTimeField(db_column="EndDate", null=True, blank=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)
    cancel_by = models.IntegerField(db_column="CancelBy", null=True, blank=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    cancel_date = models.DateTimeField(db_column="CancelDate", null=True, blank=True)
    sub_status = models.IntegerField(db_column="SubStatus")

    class Meta:
        db_table = "Class"
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    def __str__(self):
        return self.name or str(self.id)


class ClassDetail(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    class_guid_id = models.UUIDField(db_column="ClassGuidId")
    student_id = models.IntegerField(db_column="StudentId", null=True, blank=True)
    sccan_time_spam = models.BinaryField(db_column="SccanTimeSpam", null=True, blank=True)
    teacher_id = models.IntegerField(db_column="TeacherId", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)

    class Meta:
        db_table = "ClassDetail"


class District(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    district_guid_id = models.UUIDField(db_column="DistrictGuidId")
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)

    class Meta:
        db_table = "District"

    def __str__(self):
        return self.name or str(self.id)


class HolidayCenter(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    holiday_id = models.IntegerField(db_column="HolidayId", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)

    class Meta:
        db_table = "HolidayCenter"


class Holidays(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    description = models.CharField(db_column="Description", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    start_date = models.DateTimeField(db_column="StartDate", null=True, blank=True)
    end_date = models.DateTimeField(db_column="EndDate", null=True, blank=True)

    class Meta:
        db_table = "Holidays"

    def __str__(self):
        return self.name or str(self.id)


class Panchayat(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    panchayat_guid_id = models.UUIDField(db_column="PanchayatGuidId")
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)

    class Meta:
        db_table = "Panchayat"

    def __str__(self):
        return self.name or str(self.id)


class RegionalAdmin(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    regional_admin_guid_id = models.UUIDField(db_column="RegionalAdminGuidId")
    full_name = models.CharField(db_column="FullName", max_length=50, null=True, blank=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    role_id = models.IntegerField(db_column="RoleId", null=True, blank=True)
    picture = models.CharField(db_column="Picture", max_length=50, null=True, blank=True)
    last_login_time = models.CharField(db_column="LastLoginTime", max_length=50, null=True, blank=True)
    password = models.CharField(db_column="Password", max_length=255, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    type = models.IntegerField(db_column="Type", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)
    village_id = models.IntegerField(db_column="VillageId", null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    token = models.TextField(db_column="Token", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)

    class Meta:
        db_table = "RegionalAdmin"

    def __str__(self):
        return self.full_name or str(self.id)


class Student(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    enrollment_id = models.CharField(db_column="EnrollmentId", max_length=50, null=True, blank=True)
    full_name = models.CharField(db_column="FullName", max_length=50, null=True, blank=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    village_id = models.IntegerField(db_column="VillageId", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    counter = models.IntegerField(db_column="Counter", null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True)
    grade = models.CharField(db_column="Grade", max_length=50, null=True, blank=True)
    active_class_status = models.BooleanField(db_column="ActiveClassStatus", null=True, blank=True)
    last_class = models.CharField(db_column="LastClass", max_length=50, null=True, blank=True)
    father_name = models.CharField(db_column="FatherName", max_length=50, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    remarks = models.CharField(db_column="Remarks", max_length=50, null=True, blank=True)
    profile_image = models.CharField(db_column="ProfileImage", max_length=50, null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True)
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    manual_attendance = models.IntegerField(db_column="ManualAttendance", null=True, blank=True)
    mother_name = models.CharField(db_column="MotherName", max_length=50, null=True, blank=True)
    joining_date = models.DateTimeField(db_column="JoiningDate", null=True, blank=True)
    father_occupation = models.CharField(db_column="FatherOccupation", max_length=50, null=True, blank=True)
    mother_mobile_number = models.CharField(db_column="MotherMobileNumber", max_length=50, null=True, blank=True)
    mother_occupation = models.CharField(db_column="MotherOccupation", max_length=50, null=True, blank=True)
    bpl = models.BooleanField(db_column="Bpl", null=True, blank=True)
    category = models.CharField(db_column="Category", max_length=50, null=True, blank=True)
    school_id = models.IntegerField(db_column="SchoolId", null=True, blank=True)
    father_mobile_number = models.CharField(db_column="FatherMobileNumber", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "Student"

    def __str__(self):
        return self.full_name or str(self.id)


class Teacher(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    teacher_guid_id = models.UUIDField(db_column="TeacherGuidId")
    full_name = models.CharField(db_column="FullName", max_length=50, null=True, blank=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    count = models.IntegerField(db_column="Count", null=True, blank=True)
    picture = models.CharField(db_column="Picture", max_length=50, null=True, blank=True)
    last_login_time = models.CharField(db_column="LastLoginTime", max_length=50, null=True, blank=True)
    password = models.CharField(db_column="Password", max_length=255, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId")
    district_id = models.IntegerField(db_column="DistrictId")
    panchayat_id = models.IntegerField(db_column="PanchayatId")
    center_id = models.IntegerField(db_column="CenterId")
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    village_id = models.IntegerField(db_column="VillageId")

    class Meta:
        db_table = "Teacher"

    def __str__(self):
        return self.full_name or str(self.id)


class TeacherActivityLog(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    teacher_acivity_guid_id = models.UUIDField(db_column="TeacherAcivityGuidId")
    login_time = models.CharField(db_column="LoginTime", max_length=50, null=True, blank=True)
    logout_time = models.CharField(db_column="LogoutTime", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "TeacherActivityLog"


class VidhanSabha(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    vidhan_sabha_guid_id = models.UUIDField(db_column="VidhanSabhaGuidId")
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)

    class Meta:
        db_table = "VidhanSabha"

    def __str__(self):
        return self.name or str(self.id)


class Village(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    village_guid_id = models.UUIDField(db_column="VillageGuidId")
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)

    class Meta:
        db_table = "Village"

    def __str__(self):
        return self.name or str(self.id)


class Announcement(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    title = models.CharField(db_column="Title", max_length=50, null=True, blank=True)
    description = models.TextField(db_column="Description", null=True, blank=True)
    image = models.TextField(db_column="Image", null=True, blank=True)

    class Meta:
        db_table = "Announcement"

    def __str__(self):
        return self.title or str(self.id)


class CenterAssignUser(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    type = models.IntegerField(db_column="Type", null=True, blank=True)
    date = models.DateTimeField(db_column="Date", null=True, blank=True)

    class Meta:
        db_table = "CenterAssignUser"


class CenterLog(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "CenterLog"


class ClassCancelByTeacher(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)
    starting_date = models.DateTimeField(db_column="StartingDate", null=True, blank=True)
    ending_date = models.DateTimeField(db_column="EndingDate", null=True, blank=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "ClassCancelByTeacher"


class Concern(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    type = models.CharField(db_column="Type", max_length=50, null=True, blank=True)
    description = models.CharField(db_column="Description", max_length=50, null=True, blank=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)

    class Meta:
        db_table = "Concern"


class RegionalAdminPanchayat(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    panchayat_name = models.CharField(db_column="PanchayatName", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "RegionalAdminPanchayat"


class School(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    school_name = models.CharField(db_column="SchoolName", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "School"

    def __str__(self):
        return self.school_name or str(self.id)


class SchoolName(AuditModel):
    id = models.IntegerField(db_column="Id", primary_key=True)
    school_name = models.CharField(db_column="SchoolName", max_length=50)

    class Meta:
        db_table = "SchoolName"

    def __str__(self):
        return self.school_name


class StudentAttendance(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    class_id = models.IntegerField(db_column="ClassId", null=True, blank=True)
    student_id = models.IntegerField(db_column="StudentId", null=True, blank=True)
    scan_date = models.DateTimeField(db_column="ScanDate", null=True, blank=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    type = models.BooleanField(db_column="Type", null=True, blank=True)
    center_id = models.IntegerField(db_column="CenterId", null=True, blank=True)

    class Meta:
        db_table = "StudentAttendance"


class Test(AuditModel):
    id = models.AutoField(db_column="id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    address = models.CharField(db_column="Address", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "test"

    def __str__(self):
        return self.name or str(self.id)


class TestTable(AuditModel):
    id = models.AutoField(db_column="id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    address = models.CharField(db_column="Address", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "TestTable"

    def __str__(self):
        return self.name or str(self.id)


class UserActivityLog(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    ip_address = models.CharField(db_column="IpAddress", max_length=50, null=True, blank=True)
    user_name = models.CharField(db_column="UserName", max_length=50, null=True, blank=True)
    activity_date = models.DateTimeField(db_column="ActivityDate", null=True, blank=True)
    data = models.TextField(db_column="Data", null=True, blank=True)
    url = models.CharField(db_column="Url", max_length=50, null=True, blank=True)

    class Meta:
        db_table = "UserActivityLog"


class User(AuditModel):
    id = models.AutoField(db_column="Id", primary_key=True)
    enrolment_roll_id = models.CharField(db_column="EnrolmentRollId", max_length=50, null=True, blank=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    token = models.TextField(db_column="Token", null=True, blank=True)
    type = models.IntegerField(db_column="Type", null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True)
    password = models.TextField(db_column="Password", null=True, blank=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True)
    role_id = models.IntegerField(db_column="RoleId", null=True, blank=True)
    picture = models.TextField(db_column="Picture", null=True, blank=True)
    last_login_time = models.CharField(db_column="LastLoginTime", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    district_id = models.IntegerField(db_column="DistrictId", null=True, blank=True)
    vidhan_sabha_id = models.IntegerField(db_column="VidhanSabhaId", null=True, blank=True)
    panchayat_id = models.IntegerField(db_column="PanchayatId", null=True, blank=True)
    village_id = models.IntegerField(db_column="VillageId", null=True, blank=True)
    assigned_teacher_status = models.BooleanField(db_column="AssignedTeacherStatus", null=True, blank=True)
    assigned_regional_admin_status = models.BooleanField(db_column="AssignedRegionalAdminStatus", null=True, blank=True)
    enrollment_date = models.DateTimeField(db_column="EnrollmentDate", null=True, blank=True)
    guardian_name = models.CharField(db_column="GuardianName", max_length=50, null=True, blank=True)
    guardian_number = models.CharField(db_column="GuardianNumber", max_length=50, null=True, blank=True)
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    device_id = models.TextField(db_column="DeviceId", null=True, blank=True)

    class Meta:
        db_table = "Users"

    def __str__(self):
        return self.name or str(self.id)


class VersiionControl(AuditModel):
    id = models.IntegerField(db_column="Id", primary_key=True)
    app_id = models.IntegerField(db_column="AppId", null=True, blank=True)
    version = models.FloatField(db_column="Version", null=True, blank=True)
    message = models.CharField(db_column="Message", max_length=50, null=True, blank=True)
    status = models.IntegerField(db_column="Status", null=True, blank=True)

    class Meta:
        db_table = "VersiionControl"
