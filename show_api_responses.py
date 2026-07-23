#!/usr/bin/env python3
"""Test script to show actual API responses"""
import requests
import json

BASE = "http://127.0.0.1:8000/api"
DEVICE_ID = "test123"
APP_USER = "ESS_api_user"
APP_PASS = "8mHT6Iv4SKjrIaYVpB"

def print_response(name, resp):
    print(f"\n{'='*60}")
    print(f"{name} - Status: {resp.status_code}")
    print(f"{'='*60}")
    try:
        print(json.dumps(resp.json(), indent=2)[:2000])
    except:
        print(resp.text[:500])
    print()

# 1. Get app token
print("\n1. Generating App Token...")
app_resp = requests.post(
    f"{BASE}/generate-app-token/",
    headers={"Username": APP_USER, "Password": APP_PASS, "Content-Type": "application/json"},
    json={"deviceid": DEVICE_ID}
)
print_response("Generate App Token", app_resp)
app_token = app_resp.json().get("access_token")

# 2. SuperAdmin Login
print("\n2. SuperAdmin Login (/User/LoginUser)...")
sa_login = requests.post(
    f"{BASE}/User/LoginUser",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"mobileNumber": "9999999999", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("SuperAdmin Login", sa_login)
sa_token = sa_login.json().get("data", {}).get("token")

# 3. Get All Centers (GET with query params)
print("\n3. Get All Centers (/Center/GetAllCenters)...")
centers = requests.get(
    f"{BASE}/Center/GetAllCenters",
    headers={"Authorization": f"Bearer {sa_token}"},
    params={"deviceid": DEVICE_ID}
)
print_response("Get All Centers", centers)

# 4. Dashboard: Class Count by Month (GET with query params)
print("\n4. Dashboard: Class Count by Month (/Dashboard/GetClassCountByMonth)...")
dash = requests.get(
    f"{BASE}/Dashboard/GetClassCountByMonth",
    headers={"Authorization": f"Bearer {sa_token}"},
    params={"centerId": 1, "startDate": "2024-01-01", "endDate": "2024-12-31", "deviceid": DEVICE_ID}
)
print_response("Dashboard Class Count", dash)

# 5. Dashboard: Total Student of Class
print("\n5. Dashboard: Total Student of Class (/Dashboard/GetTotalStudentOfClass)...")
dash2 = requests.get(
    f"{BASE}/Dashboard/GetTotalStudentOfClass",
    headers={"Authorization": f"Bearer {sa_token}"},
    params={"centerId": 1, "deviceid": DEVICE_ID}
)
print_response("Dashboard Total Students", dash2)

# 6. Student Attendance: GetAllStudentWihAvgAttendance (note typo: Wih)
print("\n6. Student Attendance: Avg Attendance (/StudentAttendance/GetAllStudentWihAvgAttendance)...")
att = requests.get(
    f"{BASE}/StudentAttendance/GetAllStudentWihAvgAttendance",
    headers={"Authorization": f"Bearer {sa_token}"},
    params={"centerId": 1, "deviceid": DEVICE_ID}
)
print_response("Student Avg Attendance", att)

# 7. Student Attendance: GetAllAbsentAttendance
print("\n7. Student Attendance: Absent Today (/StudentAttendance/GetAllAbsentAttendance)...")
absent = requests.get(
    f"{BASE}/StudentAttendance/GetAllAbsentAttendance",
    headers={"Authorization": f"Bearer {sa_token}"},
    params={"centerId": 1, "deviceid": DEVICE_ID}
)
print_response("Student Absent Today", absent)

# 8. Teacher Login (uses name, not mobileNumber)
print("\n8. Teacher Login (/Teacher/LoginTeacher)...")
t_login = requests.post(
    f"{BASE}/Teacher/LoginTeacher",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test Teacher", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("Teacher Login", t_login)
t_token = t_login.json().get("data", {}).get("token")

# 9. RegionalAdmin Login (uses name, not mobileNumber)
print("\n9. RegionalAdmin Login (/RegionalAdmin/LoginRegionalAdmin)...")
ra_login = requests.post(
    f"{BASE}/RegionalAdmin/LoginRegionalAdmin",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test RA", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("RegionalAdmin Login", ra_login)
ra_token = ra_login.json().get("data", {}).get("token")

# 10. Teacher endpoint test
if t_token:
    print("\n10. Teacher: Get Center By Id (/Center/GetCenterById/1)...")
    t_center = requests.get(
        f"{BASE}/Center/GetCenterById/1",
        headers={"Authorization": f"Bearer {t_token}"},
        params={"deviceid": DEVICE_ID}
    )
    print_response("Teacher Get Center", t_center)

print("\n" + "="*60)
print("ALL TESTS COMPLETED")
print("="*60)