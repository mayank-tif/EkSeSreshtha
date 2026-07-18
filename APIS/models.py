from django.db import models



class District(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    district_guid_id = models.CharField(db_column="DistrictGuidId", max_length=36, unique=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "District"
        indexes = [
            models.Index(fields=['status'], name='idx_district_status'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class VidhanSabha(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    vidhan_sabha_guid_id = models.CharField(db_column="VidhanSabhaGuidId", unique=True, max_length=36)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    district = models.ForeignKey(
        District, 
        db_column="DistrictId", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='vidhan_sabhas'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "VidhanSabha"
        indexes = [
            models.Index(fields=['district'], name='idx_vidhansabha_district'),
            models.Index(fields=['status'], name='idx_vidhansabha_status'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class Panchayat(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    panchayat_guid_id = models.CharField(db_column="PanchayatGuidId", unique=True, max_length=36)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='panchayats'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='panchayats'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Panchayat"
        indexes = [
            models.Index(fields=['district'], name='idx_panchayat_district'),
            models.Index(fields=['vidhan_sabha'], name='idx_panchayat_vidhansabha'),
            models.Index(fields=['status'], name='idx_panchayat_status'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class Village(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    village_guid_id = models.CharField(db_column="VillageGuidId",max_length=36, unique=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='villages'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='villages'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='villages'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Village"
        indexes = [
            models.Index(fields=['district'], name='idx_village_district'),
            models.Index(fields=['panchayat'], name='idx_village_panchayat'),
            models.Index(fields=['vidhan_sabha'], name='idx_village_vidhansabha'),
            models.Index(fields=['status'], name='idx_village_status'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class School(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    school_name = models.CharField(db_column="SchoolName", max_length=50, null=True, blank=True)
    status= models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "School"
        constraints = [
            models.UniqueConstraint(fields=['school_name'], name='uc_school_name'),
        ]

    def __str__(self):
        return self.school_name or str(self.id)


class SchoolName(models.Model):
    id = models.IntegerField(db_column="Id", primary_key=True)
    school_name = models.CharField(db_column="SchoolName", max_length=50, unique=True)
    status= models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "SchoolName"

    def __str__(self):
        return self.school_name


class Center(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    center_guid_id = models.CharField(db_column="CenterGuidId", max_length=50, null=True, blank=True, unique=True)
    center_name = models.CharField(db_column="CenterName", max_length=50, null=True, blank=True, unique=True)
    created_date = models.DateTimeField(db_column="CreatedDate", null=True, blank=True)
    started_date = models.DateTimeField(db_column="StartedDate", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    class_status = models.BooleanField(db_column="ClassStatus", null=True, blank=True)
    assigned_teachers = models.IntegerField(db_column="AssignedTeachers", null=True, blank=True)
    assigned_regional_admin = models.IntegerField(db_column="AssignedRegionalAdmin", null=True, blank=True)
    
    # Foreign Keys
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centers'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centers'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centers'
    )
    village = models.ForeignKey(
        Village,
        db_column="VillageId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='centers'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Center"
        constraints = [
            models.UniqueConstraint(fields=['center_name'], name='uc_center_name'),
            models.UniqueConstraint(fields=['center_guid_id'], name='uc_center_guid'),
        ]
        indexes = [
            models.Index(fields=['district'], name='idx_center_district'),
            models.Index(fields=['panchayat'], name='idx_center_panchayat'),
            models.Index(fields=['vidhan_sabha'], name='idx_center_vidhansabha'),
            models.Index(fields=['village'], name='idx_center_village'),
            models.Index(fields=['status'], name='idx_center_status'),
            models.Index(fields=['class_status'], name='idx_center_class_status'),
        ]

    def __str__(self):
        return self.center_name or str(self.id)
    
    
class Role(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    role_name = models.CharField(db_column="RoleName", max_length=50, unique=True)
    role_code = models.CharField(db_column="RoleCode", max_length=20, unique=True)  # SUPER_ADMIN, REGIONAL_ADMIN, TEACHER
    description = models.CharField(db_column="Description", max_length=100, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)

    class Meta:
        db_table = "Role"


class User(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    enrolment_roll_id = models.CharField(db_column="EnrolmentRollId", max_length=50, null=True, blank=True, unique=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True, unique=True)
    password = models.TextField(db_column="Password", null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True, unique=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    picture = models.ImageField(db_column="Picture", upload_to='profile_pic/', null=True, blank=True)
    last_login_time = models.CharField(db_column="LastLoginTime", max_length=50, null=True, blank=True)
    device_id = models.TextField(db_column="DeviceId", null=True, blank=True)
    token = models.TextField(db_column="Token", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    
    # Foreign Keys
    role = models.ForeignKey(
        Role,
        db_column="RoleId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    class Meta:
        db_table = "Users"
        constraints = [
            models.UniqueConstraint(fields=['email'], name='uc_user_email'),
            models.UniqueConstraint(fields=['phone_number'], name='uc_user_phone'),
            models.UniqueConstraint(fields=['enrolment_roll_id'], name='uc_user_enrolment'),
        ]
        indexes = [
            models.Index(fields=['status'], name='idx_user_status'),
            models.Index(fields=['role'], name='idx_user_role'),
        ]

    def __str__(self):
        return self.name or str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.status

    @property
    def is_anonymous(self):
        return False


class SuperAdmin(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    super_admin_guid_id = models.CharField(db_column="SuperAdminGuidId", max_length=36, unique=True)
    
    user = models.OneToOneField(
        User,
        db_column="UserId",
        on_delete=models.CASCADE,
        related_name='super_admin'
    )
    
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)

    class Meta:
        db_table = "SuperAdmin"

    def __str__(self):
        return f"SuperAdmin: {self.user.name if self.user else ''}"
        
        

class ClassModel(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    class_enrolment_id = models.CharField(db_column="ClassEnrolmentId", max_length=50, null=True, blank=True, unique=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    status = models.IntegerField(db_column="Status", null=True, blank=True)
    total_students = models.IntegerField(db_column="TotalStudents", null=True, blank=True)
    avilable_students = models.IntegerField(db_column="AvilableStudents", null=True, blank=True)
    started_date = models.DateTimeField(db_column="StartedDate", null=True, blank=True)
    end_date = models.DateTimeField(db_column="EndDate", null=True, blank=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)
    cancel_by = models.IntegerField(db_column="CancelBy", null=True, blank=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    cancel_date = models.DateTimeField(db_column="CancelDate", null=True, blank=True)
    sub_status = models.IntegerField(db_column="SubStatus")
    active_status = models.BooleanField(db_column="active_status", null=True, blank=True, default=True)
    
    # Foreign Keys
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='classes'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Class"
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        constraints = [
            models.UniqueConstraint(fields=['class_enrolment_id'], name='uc_class_enrolment'),
        ]
        indexes = [
            models.Index(fields=['center'], name='idx_class_center'),
            models.Index(fields=['status'], name='idx_class_status'),
            models.Index(fields=['users_id'], name='idx_class_users'),
            models.Index(fields=['sub_status'], name='idx_class_sub_status'),
            models.Index(fields=['started_date'], name='idx_class_started_date'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class ClassDetail(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    class_guid_id = models.CharField(db_column="ClassGuidId", max_length=36, unique=True)
    sccan_time_spam = models.BinaryField(db_column="SccanTimeSpam", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    
    # Foreign Keys
    student = models.ForeignKey(
        'Student',
        db_column="StudentId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_details'
    )
    teacher = models.ForeignKey(
        'Teacher',
        db_column="TeacherId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_details'
    )
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_details'
    )
    class_obj = models.ForeignKey(
        ClassModel,
        db_column="ClassId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_details'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "ClassDetail"
        constraints = [
            models.UniqueConstraint(fields=['class_guid_id'], name='uc_classdetail_guid'),
        ]
        indexes = [
            models.Index(fields=['class_guid_id'], name='idx_classdetail_guid'),
            models.Index(fields=['student'], name='idx_classdetail_student'),
            models.Index(fields=['teacher'], name='idx_classdetail_teacher'),
            models.Index(fields=['center'], name='idx_classdetail_center'),
            models.Index(fields=['class_obj'], name='idx_classdetail_class'),
        ]


class RegionalAdmin(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    regional_admin_guid_id = models.CharField(db_column="RegionalAdminGuidId", max_length=36, unique=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    guardian_name = models.CharField(db_column="GuardianName", max_length=50, null=True, blank=True)
    guardian_number = models.CharField(db_column="GuardianNumber", max_length=50, null=True, blank=True)
    assigned_teacher_status = models.BooleanField(db_column="AssignedTeacherStatus", null=True, blank=True)
    assigned_regional_admin_status = models.BooleanField(db_column="AssignedRegionalAdminStatus", null=True, blank=True)
    enrollment_date = models.DateTimeField(db_column="EnrollmentDate", null=True, blank=True)
    
    user = models.OneToOneField(
        User,
        db_column="UserId",
        on_delete=models.CASCADE,
        related_name='regional_admin'
    )
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regional_admins'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regional_admins'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regional_admins'
    )
    village = models.ForeignKey(
        Village,
        db_column="VillageId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regional_admins'
    )
    
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)

    class Meta:
        db_table = "RegionalAdmin"
        indexes = [
            models.Index(fields=['user'], name='idx_regionaladmin_user'),
            models.Index(fields=['district'], name='idx_regionaladmin_district'),
            models.Index(fields=['status'], name='idx_regionaladmin_status'),
        ]

    def __str__(self):
        return f"RegionalAdmin: {self.user.name if self.user else ''}"


class Teacher(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    teacher_guid_id = models.CharField(db_column="TeacherGuidId", max_length=36, unique=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    guardian_name = models.CharField(db_column="GuardianName", max_length=50, null=True, blank=True)
    guardian_number = models.CharField(db_column="GuardianNumber", max_length=50, null=True, blank=True)
    count = models.IntegerField(db_column="Count", null=True, blank=True)
    assigned_teacher_status = models.BooleanField(db_column="AssignedTeacherStatus", null=True, blank=True)
    assigned_regional_admin_status = models.BooleanField(db_column="AssignedRegionalAdminStatus", null=True, blank=True)
    enrollment_date = models.DateTimeField(db_column="EnrollmentDate", null=True, blank=True)
    
    user = models.OneToOneField(
        User,
        db_column="UserId",
        on_delete=models.CASCADE,
        related_name='teacher'
    )
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers'
    )
    village = models.ForeignKey(
        Village,
        db_column="VillageId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers'
    )
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teachers'
    )
    
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)

    class Meta:
        db_table = "Teacher"
        indexes = [
            models.Index(fields=['user'], name='idx_teacher_user'),
            models.Index(fields=['center'], name='idx_teacher_center'),
            models.Index(fields=['status'], name='idx_teacher_status'),
        ]

    def __str__(self):
        return f"Teacher: {self.user.name if self.user else ''}"



class Student(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    enrollment_id = models.CharField(db_column="EnrollmentId", max_length=50, null=True, blank=True, unique=True)
    full_name = models.CharField(db_column="FullName", max_length=50, null=True, blank=True)
    age = models.IntegerField(db_column="Age", null=True, blank=True)
    gender = models.CharField(db_column="Gender", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    whats_app = models.CharField(db_column="WhatsApp", max_length=50, null=True, blank=True)
    contact = models.CharField(db_column="Contact", max_length=50, null=True, blank=True)
    counter = models.IntegerField(db_column="Counter", null=True, blank=True)
    email = models.EmailField(db_column="Email", max_length=50, null=True, blank=True, unique=True)
    grade = models.CharField(db_column="Grade", max_length=50, null=True, blank=True)
    active_class_status = models.BooleanField(db_column="ActiveClassStatus", null=True, blank=True)
    last_class = models.CharField(db_column="LastClass", max_length=50, null=True, blank=True)
    father_name = models.CharField(db_column="FatherName", max_length=50, null=True, blank=True)
    full_address = models.CharField(db_column="FullAddress", max_length=50, null=True, blank=True)
    date_of_birth = models.CharField(db_column="DateOfBirth", max_length=50, null=True, blank=True)
    remarks = models.CharField(db_column="Remarks", max_length=50, null=True, blank=True)
    profile_image = models.CharField(db_column="ProfileImage", max_length=50, null=True, blank=True)
    phone_number = models.CharField(db_column="PhoneNumber", max_length=50, null=True, blank=True, unique=True)
    education = models.CharField(db_column="Education", max_length=50, null=True, blank=True)
    manual_attendance = models.IntegerField(db_column="ManualAttendance", null=True, blank=True)
    mother_name = models.CharField(db_column="MotherName", max_length=50, null=True, blank=True)
    joining_date = models.DateTimeField(db_column="JoiningDate", null=True, blank=True)
    father_occupation = models.CharField(db_column="FatherOccupation", max_length=50, null=True, blank=True)
    mother_mobile_number = models.CharField(db_column="MotherMobileNumber", max_length=50, null=True, blank=True)
    mother_occupation = models.CharField(db_column="MotherOccupation", max_length=50, null=True, blank=True)
    bpl = models.BooleanField(db_column="Bpl", null=True, blank=True)
    category = models.CharField(db_column="Category", max_length=50, null=True, blank=True)
    father_mobile_number = models.CharField(db_column="FatherMobileNumber", max_length=50, null=True, blank=True)
    
    # Foreign Keys
    district = models.ForeignKey(
        District,
        db_column="DistrictId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    vidhan_sabha = models.ForeignKey(
        VidhanSabha,
        db_column="VidhanSabhaId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    village = models.ForeignKey(
        Village,
        db_column="VillageId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    school = models.ForeignKey(
        School,
        db_column="SchoolId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Student"
        constraints = [
            models.UniqueConstraint(fields=['enrollment_id'], name='uc_student_enrollment'),
            models.UniqueConstraint(fields=['email'], name='uc_student_email'),
            models.UniqueConstraint(fields=['phone_number'], name='uc_student_phone'),
        ]
        indexes = [
            models.Index(fields=['district'], name='idx_student_district'),
            models.Index(fields=['panchayat'], name='idx_student_panchayat'),
            models.Index(fields=['vidhan_sabha'], name='idx_student_vidhansabha'),
            models.Index(fields=['village'], name='idx_student_village'),
            models.Index(fields=['center'], name='idx_student_center'),
            models.Index(fields=['status'], name='idx_student_status'),
            models.Index(fields=['active_class_status'], name='idx_student_active_class'),
        ]

    def __str__(self):
        return self.full_name or str(self.id)


class Holidays(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    description = models.CharField(db_column="Description", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    start_date = models.DateTimeField(db_column="StartDate", null=True, blank=True)
    end_date = models.DateTimeField(db_column="EndDate", null=True, blank=True)
    
    # Foreign Keys
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='holidays'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Holidays"
        indexes = [
            models.Index(fields=['center'], name='idx_holidays_center'),
            models.Index(fields=['status'], name='idx_holidays_status'),
            models.Index(fields=['start_date', 'end_date'], name='idx_holidays_dates'),
        ]

    def __str__(self):
        return self.name or str(self.id)


class HolidayCenter(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    holiday = models.ForeignKey(
        Holidays,
        db_column="HolidayId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='holiday_centers'
    )
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='holiday_centers'
    )
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "HolidayCenter"
        indexes = [
            models.Index(fields=['holiday'], name='idx_holidaycenter_holiday'),
            models.Index(fields=['center'], name='idx_holidaycenter_center'),
        ]


class TeacherActivityLog(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    teacher_acivity_guid_id = models.CharField(db_column="TeacherAcivityGuidId", max_length=36, unique=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    login_time = models.CharField(db_column="LoginTime", max_length=50, null=True, blank=True)
    logout_time = models.CharField(db_column="LogoutTime", max_length=50, null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "TeacherActivityLog"
        constraints = [
            models.UniqueConstraint(fields=['teacher_acivity_guid_id'], name='uc_teacheractivity_guid'),
        ]
        indexes = [
            models.Index(fields=['teacher_acivity_guid_id'], name='idx_teacheractivity_guid'),
        ]


class Announcement(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    title = models.CharField(db_column="Title", max_length=50, null=True, blank=True)
    description = models.TextField(db_column="Description", null=True, blank=True)
    image = models.TextField(db_column="Image", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Announcement"
        ordering = ['-created_on']

    def __str__(self):
        return self.title or str(self.id)


class CenterAssignUser(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    type = models.IntegerField(db_column="Type", null=True, blank=True)
    date = models.DateTimeField(db_column="Date", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    
    # Foreign Keys
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='center_assign_users'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "CenterAssignUser"
        indexes = [
            models.Index(fields=['users_id'], name='idx_centerassignuser_users'),
            models.Index(fields=['center'], name='idx_centerassignuser_center'),
            models.Index(fields=['type'], name='idx_centerassignuser_type'),
        ]


class CenterLog(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    
    # Foreign Keys
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='center_logs'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "CenterLog"
        indexes = [
            models.Index(fields=['center'], name='idx_centerlog_center'),
            models.Index(fields=['user_id'], name='idx_centerlog_user'),
        ]


class ClassCancelByTeacher(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    starting_date = models.DateTimeField(db_column="StartingDate", null=True, blank=True)
    ending_date = models.DateTimeField(db_column="EndingDate", null=True, blank=True)
    reason = models.CharField(db_column="Reason", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    
    # Foreign Keys
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_cancel_by_teachers'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "ClassCancelByTeacher"
        indexes = [
            models.Index(fields=['center'], name='idx_classcancel_center'),
            models.Index(fields=['user_id'], name='idx_classcancel_user'),
            models.Index(fields=['starting_date'], name='idx_classcancel_start_date'),
        ]


class Concern(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    type = models.CharField(db_column="Type", max_length=50, null=True, blank=True)
    description = models.CharField(db_column="Description", max_length=50, null=True, blank=True)
    users_id = models.IntegerField(db_column="UsersId", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "Concern"
        indexes = [
            models.Index(fields=['users_id'], name='idx_concern_users'),
            models.Index(fields=['type'], name='idx_concern_type'),
        ]


class RegionalAdminPanchayat(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    panchayat_name = models.CharField(db_column="PanchayatName", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    
    # Foreign Keys
    regional_admin = models.ForeignKey(
        RegionalAdmin,
        db_column="RegionalAdminId",  # Column name in database
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='regional_admin_panchayats'
    )
    panchayat = models.ForeignKey(
        Panchayat,
        db_column="PanchayatId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='regional_admin_panchayats'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "RegionalAdminPanchayat"
        indexes = [
            models.Index(fields=['regional_admin'], name='idx_regadmpnhyt_regaladm'),
            models.Index(fields=['panchayat'], name='idx_regadmpnhyt_panchayat'),
        ]

class StudentAttendance(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    scan_date = models.DateTimeField(db_column="ScanDate", null=True, blank=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    type = models.BooleanField(db_column="Type", null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    # Foreign Keys
    class_obj = models.ForeignKey(
        ClassModel,
        db_column="ClassId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances'
    )
    student = models.ForeignKey(
        Student,
        db_column="StudentId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances'
    )
    center = models.ForeignKey(
        Center,
        db_column="CenterId",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendances'
    )
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "StudentAttendance"
        indexes = [
            models.Index(fields=['class_obj'], name='idx_attendance_class'),
            models.Index(fields=['student'], name='idx_attendance_student'),
            models.Index(fields=['center'], name='idx_attendance_center'),
            models.Index(fields=['scan_date'], name='idx_attendance_scan_date'),
            models.Index(fields=['user_id'], name='idx_attendance_user'),
        ]


class UserActivityLog(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    ip_address = models.CharField(db_column="IpAddress", max_length=50, null=True, blank=True)
    user_name = models.CharField(db_column="UserName", max_length=50, null=True, blank=True)
    activity_date = models.DateTimeField(db_column="ActivityDate", null=True, blank=True)
    data = models.TextField(db_column="Data", null=True, blank=True)
    url = models.CharField(db_column="Url", max_length=50, null=True, blank=True)
    status = models.BooleanField(db_column="Status", null=True, blank=True, default=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "UserActivityLog"
        indexes = [
            models.Index(fields=['user_id'], name='idx_useractivity_user'),
            models.Index(fields=['activity_date'], name='idx_useractivity_date'),
        ]


class VersionControl(models.Model):
    id = models.IntegerField(db_column="Id", primary_key=True)
    app_id = models.IntegerField(db_column="AppId", null=True, blank=True)
    version = models.FloatField(db_column="Version", null=True, blank=True)
    message = models.CharField(db_column="Message", max_length=50, null=True, blank=True)
    status = models.IntegerField(db_column="Status", null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "VersionControl"
        indexes = [
            models.Index(fields=['app_id'], name='idx_versioncontrol_app'),
            models.Index(fields=['status'], name='idx_versioncontrol_status'),
        ]


class Test(models.Model):
    id = models.AutoField(db_column="id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    address = models.CharField(db_column="Address", max_length=50, null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "test"

    def __str__(self):
        return self.name or str(self.id)


class TestTable(models.Model):
    id = models.AutoField(db_column="id", primary_key=True)
    name = models.CharField(db_column="Name", max_length=50, null=True, blank=True)
    address = models.CharField(db_column="Address", max_length=50, null=True, blank=True)
    created_by = models.IntegerField(db_column="CreatedBy", null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    updated_by = models.IntegerField(db_column="UpdatedBy", null=True, blank=True)
    updated_on = models.DateTimeField(db_column="UpdatedOn", null=True, blank=True)

    class Meta:
        db_table = "TestTable"

    def __str__(self):
        return self.name or str(self.id)
    
    

class ActivityLog(models.Model):
    id = models.AutoField(db_column="Id", primary_key=True)
    user_id = models.IntegerField(db_column="UserId", null=True, blank=True)
    action = models.CharField(db_column="Action", max_length=50, null=True, blank=True)  # CREATE, UPDATE, DELETE
    module = models.CharField(db_column="Module", max_length=50, null=True, blank=True)  # User, Center, Student, etc.
    record_id = models.IntegerField(db_column="RecordId", null=True, blank=True)
    data = models.TextField(db_column="Data", null=True, blank=True)  # JSON data of changes
    ip_address = models.CharField(db_column="IpAddress", max_length=50, null=True, blank=True)
    created_on = models.DateTimeField(db_column="CreatedOn", null=True, blank=True)
    
    class Meta:
        db_table = "ActivityLog"
        indexes = [
            models.Index(fields=['user_id'], name='idx_activitylog_user'),
            models.Index(fields=['module'], name='idx_activitylog_module'),
            models.Index(fields=['created_on'], name='idx_activitylog_created_on'),
        ]