"""
Comprehensive API Testing Suite for All User Roles
Tests SuperAdmin, RegionalAdmin, and Teacher endpoints automatically
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'EkSeSreshtha.settings')
import django
django.setup()

from APIS.models import User, Role, SuperAdmin, RegionalAdmin, Teacher, Center, ClassModel, Student
from rest_framework_simplejwt.tokens import AccessToken


BASE_URL = "http://127.0.0.1:8000"
API_BASE = f"{BASE_URL}/api"


class APITester:
    """Automated API testing for all user roles"""
    
    def __init__(self):
        self.tokens = {}
        self.users = {}
        self.results = []
    
    def login_user(self, phone, password, role_name):
        """Login and get JWT token"""
        url = f"{API_BASE}/User/LoginUser"
        data = {"PhoneNumber": phone, "Password": password}
        resp = requests.post(url, json=data)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("Status") or result.get("status"):
                token = result.get("Data", {}).get("Token") or result.get("data", {}).get("Token")
                if token:
                    self.tokens[role_name] = token
                    self.users[role_name] = result.get("Data", {}).get("User") or result.get("data", {}).get("User")
                    print(f"✅ {role_name} logged in: {token[:20]}...")
                    return token
        print(f"❌ {role_name} login failed: {resp.text[:200]}")
        return None
    
    def login_teacher(self, phone, password):
        """Login teacher"""
        url = f"{API_BASE}/Teacher/LoginTeacher"
        data = {"PhoneNumber": phone, "Password": password}
        resp = requests.post(url, json=data)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("Status") or result.get("status"):
                token = result.get("Data", {}).get("Token") or result.get("data", {}).get("Token")
                if token:
                    self.tokens["Teacher"] = token
                    self.users["Teacher"] = result.get("Data", {}).get("User") or result.get("data", {}).get("User")
                    print(f"✅ Teacher logged in: {token[:20]}...")
                    return token
        print(f"❌ Teacher login failed: {resp.text[:200]}")
        return None
    
    def login_regional_admin(self, phone, password):
        """Login regional admin"""
        url = f"{API_BASE}/RegionalAdmin/LoginRegionalAdmin"
        data = {"PhoneNumber": phone, "Password": password}
        resp = requests.post(url, json=data)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("Status") or result.get("status"):
                token = result.get("Data", {}).get("Token") or result.get("data", {}).get("Token")
                if token:
                    self.tokens["RegionalAdmin"] = token
                    self.users["RegionalAdmin"] = result.get("Data", {}).get("User") or result.get("data", {}).get("User")
                    print(f"✅ RegionalAdmin logged in: {token[:20]}...")
                    return token
        print(f"❌ RegionalAdmin login failed: {resp.text[:200]}")
        return None
    
    def get_headers(self, role):
        """Get auth headers for role"""
        return {"Authorization": f"Bearer {self.tokens.get(role)}"} if self.tokens.get(role) else {}
    
    def test_endpoint(self, method, url, role, expected_status=200, data=None, description=""):
        """Test an endpoint and record result"""
        headers = self.get_headers(role)
        if not headers:
            self.results.append({"test": description, "role": role, "passed": False, "error": "No token"})
            return None
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=data)
            else:
                resp = requests.request(method, url, headers=headers, json=data)
            
            passed = resp.status_code == expected_status
            result = {
                "test": description,
                "role": role,
                "method": method,
                "url": url,
                "expected": expected_status,
                "actual": resp.status_code,
                "passed": passed,
                "response": resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text[:200]
            }
            self.results.append(result)
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} {role} {method} {url} -> {resp.status_code}")
            return resp
            
        except Exception as e:
            self.results.append({"test": description, "role": role, "passed": False, "error": str(e)})
            print(f"❌ ERROR {role} {method} {url}: {e}")
            return None
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("\n" + "="*60)
        print("STARTING COMPREHENSIVE API TESTS")
        print("="*60 + "\n")
        
        # ========================================
        # 1. LOGIN TESTS
        # ========================================
        print("--- LOGIN TESTS ---")
        
        # Get test users from DB
        sa_user = User.objects.filter(role_id=1, status=True).first()
        ra_user = User.objects.filter(role_id=2, status=True).first()
        teacher_user = User.objects.filter(role_id=3, status=True).first()
        
        if sa_user:
            self.login_user(sa_user.phone_number, "password123", "SuperAdmin")
        if ra_user:
            self.login_regional_admin(ra_user.phone_number, "password123")
        if teacher_user:
            self.login_teacher(teacher_user.phone_number, "password123")
        
        # ========================================
        # 2. SUPERADMIN TESTS
        # ========================================
        if "SuperAdmin" in self.tokens:
            print("\n--- SUPERADMIN TESTS ---")
            sa = "SuperAdmin"
            
            # User Management
            self.test_endpoint("GET", f"{API_BASE}/User/GetAllUsers", sa, description="Get All Users")
            self.test_endpoint("GET", f"{API_BASE}/User/GetUserById/1", sa, description="Get User by ID")
            
            # Center Management
            self.test_endpoint("GET", f"{API_BASE}/Center/GetAllCenters", sa, description="Get All Centers")
            center = Center.objects.filter(status=True).first()
            if center:
                self.test_endpoint("GET", f"{API_BASE}/Center/GetCenterById/{center.id}", sa, description="Get Center by ID")
            
            # District/VidhanSabha/Panchayat/Village
            self.test_endpoint("GET", f"{API_BASE}/District/GetAllDistricts", sa, description="Get All Districts")
            self.test_endpoint("GET", f"{API_BASE}/VidhanSabha/GetAllVidhanSabhas", sa, description="Get All Vidhan Sabhas")
            self.test_endpoint("GET", f"{API_BASE}/Panchayat/GetAllPanchayats", sa, description="Get All Panchayats")
            self.test_endpoint("GET", f"{API_BASE}/Village/GetAllVillages", sa, description="Get All Villages")
            
            # School
            self.test_endpoint("GET", f"{API_BASE}/School/GetAllSchools", sa, description="Get All Schools")
            
            # Class
            self.test_endpoint("GET", f"{API_BASE}/Class/GetAllClasses", sa, description="Get All Classes")
            
            # Teacher
            self.test_endpoint("GET", f"{API_BASE}/Teacher/GetAllTeachers", sa, description="Get All Teachers")
            
            # Regional Admin
            self.test_endpoint("GET", f"{API_BASE}/RegionalAdmin/GetAllRegionalAdmins", sa, description="Get All Regional Admins")
            
            # Announcement
            self.test_endpoint("GET", f"{API_BASE}/Announcement/GetAllAnnouncements", sa, description="Get All Announcements")
            
            # Holidays
            self.test_endpoint("GET", f"{API_BASE}/Holiday/GetAllHolidays", sa, description="Get All Holidays")
            
            # Dashboard
            if center:
                self.test_endpoint("GET", f"{API_BASE}/Dashboard/GetClassCountByMonth?centerId={center.id}&startDate=2024-01-01&endDate=2024-12-31", sa, description="Dashboard: Class Count by Month")
                self.test_endpoint("GET", f"{API_BASE}/Dashboard/GetTotalStudentOfClass?centerId={center.id}", sa, description="Dashboard: Total Student of Class")
            
            # Student Attendance
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllStudentWithAvgAttendance?centerId=1", sa, description="Student Attendance: Avg Attendance")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllAbsentAttendance?centerId=1", sa, description="Student Attendance: Absent Today")
        
        # ========================================
        # 3. REGIONAL ADMIN TESTS
        # ========================================
        if "RegionalAdmin" in self.tokens:
            print("\n--- REGIONAL ADMIN TESTS ---")
            ra = "RegionalAdmin"
            
            self.test_endpoint("GET", f"{API_BASE}/Center/GetAllCenters", ra, description="Get All Centers (RA)")
            self.test_endpoint("GET", f"{API_BASE}/Teacher/GetAllTeachers", ra, description="Get All Teachers (RA)")
            self.test_endpoint("GET", f"{API_BASE}/Class/GetAllClasses", ra, description="Get All Classes (RA)")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllStudentWithAvgAttendance?centerId=1", ra, description="Avg Attendance (RA)")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllAbsentAttendance?centerId=1", ra, description="Absent Today (RA)")
        
        # ========================================
        # 4. TEACHER TESTS
        # ========================================
        if "Teacher" in self.tokens:
            print("\n--- TEACHER TESTS ---")
            teacher = "Teacher"
            
            # Get teacher's center
            t_user = self.users.get("Teacher", {})
            t_center_id = t_user.get("CenterId") or Center.objects.filter(status=True).first().id if Center.objects.filter(status=True).exists() else 1
            
            self.test_endpoint("GET", f"{API_BASE}/Center/GetCenterById/{t_center_id}", teacher, description="Get My Center")
            self.test_endpoint("GET", f"{API_BASE}/Class/GetAllClasses", teacher, description="Get Classes")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllStudentWithAvgAttendance?centerId={t_center_id}", teacher, description="Avg Attendance (Teacher)")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllAbsentAttendance?centerId={t_center_id}", teacher, description="Absent Today (Teacher)")
            self.test_endpoint("GET", f"{API_BASE}/StudentAttendance/GetAllStudentAttendancStatus?centerId={t_center_id}&scanDate=2024-01-15", teacher, description="Attendance Status for Date (Teacher)")
            
            # Test attendance save (if students exist)
            students = Student.objects.filter(center_id=t_center_id, status=True)[:2]
            if students.exists():
                class_obj = ClassModel.objects.filter(center_id=t_center_id, status=1).first()
                if class_obj:
                    data = {
                        "StudentIds": [s.id for s in students],
                        "ClassId": class_obj.id,
                        "CenterId": t_center_id,
                        "UserId": t_user.get("Id"),
                        "ScanDate": datetime.now().isoformat()
                    }
                    self.test_endpoint("POST", f"{API_BASE}/StudentAttendance/SaveStudentAttendance", teacher, data=data, description="Save Student Attendance")
        
        # ========================================
        # 5. NEGATIVE TESTS
        # ========================================
        print("\n--- NEGATIVE TESTS ---")
        # Test without token
        resp = requests.get(f"{API_BASE}/Center/GetAllCenters")
        self.results.append({
            "test": "No Auth - Get All Centers",
            "role": "Anonymous",
            "passed": resp.status_code == 401,
            "actual": resp.status_code
        })
        print(f"{'✅ PASS' if resp.status_code == 401 else '❌ FAIL'} Anonymous access blocked: {resp.status_code}")
        
        # ========================================
        # SUMMARY
        # ========================================
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("passed"))
        failed = total - passed
        
        print("\n" + "="*60)
        print(f"TEST SUMMARY: {passed}/{total} passed ({failed} failed)")
        print("="*60)
        
        for r in self.results:
            if not r.get("passed"):
                print(f"  ❌ {r.get('role', 'N/A')} - {r.get('test', 'N/A')}: {r.get('error', f'Status {r.get(\"actual\")} != {r.get(\"expected\")}')}")
        
        if failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
        
        # Save detailed results
        with open("test_results.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print("\n📄 Detailed results saved to test_results.json")


def create_test_users():
    """Create test users if they don't exist"""
    print("Creating test users...")
    
    # Get or create roles
    sa_role, _ = Role.objects.get_or_create(id=1, defaults={"role_name": "SuperAdmin", "status": True})
    ra_role, _ = Role.objects.get_or_create(id=2, defaults={"role_name": "RegionalAdmin", "status": True})
    teacher_role, _ = Role.objects.get_or_create(id=3, defaults={"role_name": "Teacher", "status": True})
    
    # Create SuperAdmin
    sa_user, created = User.objects.get_or_create(
        phone_number="9999999999",
        defaults={
            "name": "Test SuperAdmin",
            "email": "superadmin@test.com",
            "password": "password123",  # In production, hash this!
            "role": sa_role,
            "status": True,
            "created_on": datetime.now(),
        }
    )
    if created:
        SuperAdmin.objects.create(user=sa_user, status=True)
        print(f"✅ Created SuperAdmin: {sa_user.phone_number}")
    
    # Create RegionalAdmin
    ra_user, created = User.objects.get_or_create(
        phone_number="8888888888",
        defaults={
            "name": "Test RegionalAdmin",
            "email": "regionaladmin@test.com",
            "password": "password123",
            "role": ra_role,
            "status": True,
            "created_on": datetime.now(),
        }
    )
    if created:
        # Need a district/vidhan_sabha for RegionalAdmin
        from APIS.models import District, VidhanSabha
        district = District.objects.filter(status=True).first()
        vs = VidhanSabha.objects.filter(status=True).first()
        if district and vs:
            RegionalAdmin.objects.create(
                user=ra_user,
                district=district,
                vidhan_sabha=vs,
                status=True
            )
            print(f"✅ Created RegionalAdmin: {ra_user.phone_number}")
    
    # Create Teacher
    t_user, created = User.objects.get_or_create(
        phone_number="7777777777",
        defaults={
            "name": "Test Teacher",
            "email": "teacher@test.com",
            "password": "password123",
            "role": teacher_role,
            "status": True,
            "created_on": datetime.now(),
        }
    )
    if created:
        center = Center.objects.filter(status=True).first()
        if center:
            Teacher.objects.create(user=t_user, center=center, status=True)
            print(f"✅ Created Teacher: {t_user.phone_number}")
    
    print("Test users ready!\n")


if __name__ == "__main__":
    create_test_users()
    
    tester = APITester()
    tester.run_all_tests()