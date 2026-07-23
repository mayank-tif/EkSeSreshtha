#!/usr/bin/env python3
"""Test script to show actual API responses"""
import requests
import json

BASE = "http://127.0.0.1:8000/api"
DEVICE_ID = "test123"
APP_USER = "ESS_api_user"
APP_PASS = "8mHT6Iv4SKjrIaYVpB"

print("=" * 60)
print("TESTING API RESPONSES")
print("=" * 60)

# Step 1: Generate app token
print("\n1. Generate App Token (/generate-app-token/)")
app_resp = requests.post(
    f"{BASE}/generate-app-token/",
    headers={"Username": APP_USER, "Password": APP_PASS, "Content-Type": "application/json"},
    json={"deviceid": DEVICE_ID}
)
print(f"   Status: {app_resp.status_code}")
print(f"   Response: {json.dumps(app_resp.json(), indent=2)}")
app_token = app_resp.json().get("access_token")

# Step 2: Login SuperAdmin
print("\n2. SuperAdmin Login (/User/LoginUser)")
login_resp = requests.post(
    f"{BASE}/User/LoginUser",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"mobileNumber": "9999999999", "password": "password123", "deviceid": DEVICE_ID}
)
print(f"   Status: {login_resp.status_code}")
login_data = login_resp.json()
print(f"   Response: {json.dumps(login_data, indent=2)[:800]}...")
user_token = login_data.get("data", {}).get("Token") or login_data.get("data", {}).get("token")
print(f"   User token: {user_token[:50]}...")

# Step 3: Test Center endpoint (POST with deviceid in body)
print("\n3. Get All Centers (/Center/GetAllCenters)")
centers_resp = requests.post(
    f"{BASE}/Center/GetAllCenters",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    json={"deviceid": DEVICE_ID}
)
print(f"   Status: {centers_resp.status_code}")
print(f"   Response: {json.dumps(centers_resp.json(), indent=2)[:800]}...")

# Step 4: Test Dashboard
print("\n4. Dashboard: Class Count by Month (/Dashboard/GetClassCountByMonth)")
dash_resp = requests.post(
    f"{BASE}/Dashboard/GetClassCountByMonth",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    json={"centerId": 1, "startDate": "2024-01-01", "endDate": "2024-12-31", "deviceid": DEVICE_ID}
)
print(f"   Status: {dash_resp.status_code}")
print(f"   Response: {json.dumps(dash_resp.json(), indent=2)}")

# Step 5: Test Student Attendance
print("\n5. Student Attendance: Avg Attendance (/StudentAttendance/GetAllStudentWithAvgAttendance)")
att_resp = requests.post(
    f"{BASE}/StudentAttendance/GetAllStudentWithAvgAttendance",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    json={"centerId": 1, "deviceid": DEVICE_ID}
)
print(f"   Status: {att_resp.status_code}")
print(f"   Response: {json.dumps(att_resp.json(), indent=2)[:800]}...")

# Step 6: Teacher Login
print("\n6. Teacher Login (/Teacher/LoginTeacher)")
teacher_login = requests.post(
    f"{BASE}/Teacher/LoginTeacher",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test Teacher", "password": "password123", "deviceid": DEVICE_ID}
)
print(f"   Status: {teacher_login.status_code}")
teacher_data = teacher_login.json()
print(f"   Response: {json.dumps(teacher_data, indent=2)[:800]}...")

teacher_token = teacher_data.get("data", {}).get("Token") or teacher_data.get("data", {}).get("token")
if teacher_token:
    print(f"   Teacher token: {teacher_token[:50]}...")
    
    # Test teacher endpoint
    print("\n7. Teacher: Get Center By Id (/Center/GetCenterById/1)")
    t_center = requests.post(
        f"{BASE}/Center/GetCenterById/1",
        headers={"Authorization": f"Bearer {teacher_token}", "Content-Type": "application/json"},
        json={"deviceid": DEVICE_ID}
    )
    print(f"   Status: {t_center.status_code}")
    print(f"   Response: {json.dumps(t_center.json(), indent=2)[:800]}...")

# Step 8: RegionalAdmin Login
print("\n8. RegionalAdmin Login (/RegionalAdmin/LoginRegionalAdmin)")
ra_login = requests.post(
    f"{BASE}/RegionalAdmin/LoginRegionalAdmin",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test RA", "password": "password123", "deviceid": DEVICE_ID}
)
print(f"   Status: {ra_login.status_code}")
ra_data = ra_login.json()
print(f"   Response: {json.dumps(ra_data, indent=2)[:800]}...")

ra_token = ra_data.get("data", {}).get("Token") or ra_data.get("data", {}).get("token")
if ra_token:
    print(f"   RA token: {ra_token[:50]}...")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)