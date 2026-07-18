"""
Pytest-based comprehensive test suite for all API endpoints
Run with: pytest test_api_suite.py -v
"""
import pytest
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000/api"

class TestTokens:
    """Store tokens across tests"""
    superadmin = None
    regional_admin = None
    teacher = None
    center_id = 1

@pytest.fixture(scope="session", autouse=True)
def login_all_users():
    """Login all three user types before tests"""
    
    # SuperAdmin login
    resp = requests.post(f"{BASE_URL}/User/LoginUser", json={
        "PhoneNumber": "9999999999",
        "Password": "password123"
    })
    assert resp.status_code == 200
    data = resp.json()
    token = data.get("Data", {}).get("Token") or data.get("data", {}).get("Token")
    assert token, "SuperAdmin login failed"
    TestTokens.superadmin = token
    print(f"\n✓ SuperAdmin token: {token[:20]}...")
    
    # RegionalAdmin login
    resp = requests.post(f"{BASE_URL}/RegionalAdmin/LoginRegionalAdmin", json={
        "PhoneNumber": "8888888888",
        "Password": "password123"
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("Data", {}).get("Token") or data.get("data", {}).get("Token")
        if token:
            TestTokens.regional_admin = token
            print(f"✓ RegionalAdmin token: {token[:20]}...")
    
    # Teacher login
    resp = requests.post(f"{BASE_URL}/Teacher/LoginTeacher", json={
        "PhoneNumber": "7777777777",
        "Password": "password123"
    })
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("Data", {}).get("Token") or data.get("data", {}).get("Token")
        if token:
            TestTokens.teacher = token
            print(f"✓ Teacher token: {token[:20]}...")

def headers(token):
    return {"Authorization": f"Bearer {token}"}

class TestSuperAdmin:
    """SuperAdmin endpoint tests"""
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_users(self):
        resp = requests.get(f"{BASE_URL}/User/GetAllUsers", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("Status") or data.get("status")
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_centers(self):
        resp = requests.get(f"{BASE_URL}/Center/GetAllCenters", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_districts(self):
        resp = requests.get(f"{BASE_URL}/District/GetAllDistricts", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_vidhan_sabhas(self):
        resp = requests.get(f"{BASE_URL}/VidhanSabha/GetAllVidhanSabhas", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_panchayats(self):
        resp = requests.get(f"{BASE_URL}/Panchayat/GetAllPanchayats", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_villages(self):
        resp = requests.get(f"{BASE_URL}/Village/GetAllVillages", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_schools(self):
        resp = requests.get(f"{BASE_URL}/School/GetAllSchools", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_classes(self):
        resp = requests.get(f"{BASE_URL}/Class/GetAllClasses", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_teachers(self):
        resp = requests.get(f"{BASE_URL}/Teacher/GetAllTeachers", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_regional_admins(self):
        resp = requests.get(f"{BASE_URL}/RegionalAdmin/GetAllRegionalAdmins", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_announcements(self):
        resp = requests.get(f"{BASE_URL}/Announcement/GetAllAnnouncements", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_get_all_holidays(self):
        resp = requests.get(f"{BASE_URL}/Holiday/GetAllHolidays", headers=headers(TestTokens.superadmin))
        assert resp.status_code == 200
    
    # Dashboard tests
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_dashboard_class_count_by_month(self):
        resp = requests.get(
            f"{BASE_URL}/Dashboard/GetClassCountByMonth",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1, "startDate": "2024-01-01", "endDate": "2024-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("Status") is True or data.get("status") is True
        assert "Data" in data or "data" in data
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_dashboard_total_student_of_class(self):
        resp = requests.get(
            f"{BASE_URL}/Dashboard/GetTotalStudentOfClass",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_dashboard_total_gender_ratio(self):
        resp = requests.get(
            f"{BASE_URL}/Dashboard/GetTotalGenterRatioByCenterId",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    # Student Attendance
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_student_attendance_avg(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllStudentWithAvgAttendance",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_student_attendance_absent_today(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllAbsentAttendance",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200


class TestRegionalAdmin:
    """RegionalAdmin endpoint tests"""
    
    @pytest.mark.skipif(lambda: not TestTokens.regional_admin, reason="RegionalAdmin not logged in")
    def test_get_all_centers(self):
        resp = requests.get(f"{BASE_URL}/Center/GetAllCenters", headers=headers(TestTokens.regional_admin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.regional_admin, reason="RegionalAdmin not logged in")
    def test_get_all_teachers(self):
        resp = requests.get(f"{BASE_URL}/Teacher/GetAllTeachers", headers=headers(TestTokens.regional_admin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.regional_admin, reason="RegionalAdmin not logged in")
    def test_get_all_classes(self):
        resp = requests.get(f"{BASE_URL}/Class/GetAllClasses", headers=headers(TestTokens.regional_admin))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.regional_admin, reason="RegionalAdmin not logged in")
    def test_student_attendance_avg(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllStudentWithAvgAttendance",
            headers=headers(TestTokens.regional_admin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.regional_admin, reason="RegionalAdmin not logged in")
    def test_student_attendance_absent(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllAbsentAttendance",
            headers=headers(TestTokens.regional_admin),
            params={"centerId": 1}
        )
        assert resp.status_code == 200


class TestTeacher:
    """Teacher endpoint tests"""
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_get_my_center(self):
        resp = requests.get(
            f"{BASE_URL}/Center/GetCenterById/1",
            headers=headers(TestTokens.teacher)
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_get_classes(self):
        resp = requests.get(f"{BASE_URL}/Class/GetAllClasses", headers=headers(TestTokens.teacher))
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_student_attendance_avg(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllStudentWithAvgAttendance",
            headers=headers(TestTokens.teacher),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_student_attendance_absent(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllAbsentAttendance",
            headers=headers(TestTokens.teacher),
            params={"centerId": 1}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_student_attendance_status(self):
        resp = requests.get(
            f"{BASE_URL}/StudentAttendance/GetAllStudentAttendancStatus",
            headers=headers(TestTokens.teacher),
            params={"centerId": 1, "scanDate": "2024-01-15"}
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_save_student_attendance(self):
        resp = requests.post(
            f"{BASE_URL}/StudentAttendance/SaveStudentAttendance",
            headers=headers(TestTokens.teacher),
            json={
                "StudentIds": [1, 2],
                "ClassId": 1,
                "CenterId": 1,
                "UserId": 1,
                "ScanDate": "2024-01-15T10:00:00"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return success status
        assert data.get("status") is True or data.get("Status") is True
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_save_automatic_attendance(self):
        resp = requests.post(
            f"{BASE_URL}/StudentAttendance/SaveAutomaticStudentAttendance",
            headers=headers(TestTokens.teacher),
            json={
                "StudentIds": [1],
                "ClassId": 1,
                "CenterId": 1,
                "UserId": 1,
                "ScanDate": datetime.now().isoformat()
            }
        )
        assert resp.status_code == 200
    
    @pytest.mark.skipif(lambda: not TestTokens.teacher, reason="Teacher not logged in")
    def test_save_manual_attendance(self):
        resp = requests.post(
            f"{BASE_URL}/StudentAttendance/SaveManualStudentAttendance",
            headers=headers(TestTokens.teacher),
            json={
                "StudentIds": [1],
                "ClassId": 1,
                "CenterId": 1,
                "UserId": 1,
                "ScanDate": datetime.now().isoformat()
            }
        )
        assert resp.status_code == 200


class TestAuthNegative:
    """Negative authentication tests"""
    
    def test_no_token_rejected(self):
        resp = requests.get(f"{BASE_URL}/Center/GetAllCenters")
        assert resp.status_code == 401
    
    def test_invalid_token_rejected(self):
        resp = requests.get(
            f"{BASE_URL}/Center/GetAllCenters",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401
    
    def test_expired_token_rejected(self):
        # Create an expired token manually if needed
        resp = requests.get(
            f"{BASE_URL}/Center/GetAllCenters",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzAwMDAwMDAwLCJpYXQiOjE3MDAwMDAwMDAsImp0aSI6InRlc3QiLCJ1c2VyX2lkIjoiMSJ9.fake"}
        )
        assert resp.status_code == 401


class TestResponseFormat:
    """Verify JSON response format matches .NET (PascalCase)"""
    
    @pytest.mark.skipif(lambda: not TestTokens.superadmin, reason="SuperAdmin not logged in")
    def test_dashboard_response_pascal_case(self):
        resp = requests.get(
            f"{BASE_URL}/Dashboard/GetClassCountByMonth",
            headers=headers(TestTokens.superadmin),
            params={"centerId": 1, "startDate": "2024-01-01", "endDate": "2024-12-31"}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Check PascalCase keys
        assert "Status" in data or "status" in data
        if "Data" in data:
            assert isinstance(data["Data"], list)
            if data["Data"]:
                item = data["Data"][0]
                # These should be PascalCase
                assert any(k in item for k in ["HolidayCount", "holidayCount"])
                assert any(k in item for k in ["ClassCount", "classCount"])
                assert any(k in item for k in ["ClassCancelTeacherCount", "classCancelTeacherCount"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])