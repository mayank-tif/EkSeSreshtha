#!/usr/bin/env python3
"""Complete API test with auth flow"""
import requests
import json

BASE = "http://127.0.0.1:8000/api"
API_USER = "ESS_api_user"
API_PASS = "8mHT6Iv4SKjrIaYVpB"
DEVICE_ID = "test123"

def print_response(name, resp):
    print(f"\n{'='*60}")
    print(f"{name} - Status: {resp.status_code}")
    print(f"{'='*60}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except:
        print(resp.text)

# 1. Get app token
print("1. Getting app token...")
app_resp = requests.post(
    f"{BASE}/generate-app-token/",
    headers={"Username": API_USER, "Password": API_PASS, "Content-Type": "application/json"},
    json={"deviceid": DEVICE_ID}
)
print_response("App Token", app_resp)
app_token = app_resp.json().get("access_token")
print(f"\nApp token: {app_token[:50]}...")

# 2. Login SuperAdmin
print("\n2. Logging in SuperAdmin...")
login_resp = requests.post(
    f"{BASE}/User/LoginUser",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"mobileNumber": "9999999999", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("SuperAdmin Login", login_resp)
user_token = login_resp.json().get("data", {}).get("token") or login_resp.json().get("data", {}).get("Token")
print(f"\nUser token: {user_token[:50]}...")

# 3. Test protected endpoint (GET with query param)
print("\n3. Testing GetAllCenters (GET)...")
centers_resp = requests.get(
    f"{BASE}/Center/GetAllCenters",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    params={"deviceid": DEVICE_ID}  # deviceid as query param for GET
)
print_response("GetAllCenters", centers_resp)

# 4. Test StudentAttendance GET endpoint
print("\n4. Testing GetAllStudentWithAvgAttendance...")
att_resp = requests.get(
    f"{BASE}/StudentAttendance/GetAllStudentWithAvgAttendance",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    params={"centerId": 1, "deviceid": DEVICE_ID}
)
print_response("GetAllStudentWithAvgAttendance", att_resp)

# 5. Test Dashboard
print("\n5. Testing Dashboard GetClassCountByMonth...")
dash_resp = requests.get(
    f"{BASE}/Dashboard/GetClassCountByMonth",
    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
    params={"centerId": 1, "startDate": "2024-01-01", "endDate": "2024-12-31", "deviceid": DEVICE_ID}
)
print_response("Dashboard GetClassCountByMonth", dash_resp)

# 6. Test Teacher Login
print("\n6. Logging in Teacher...")
t_login_resp = requests.post(
    f"{BASE}/Teacher/LoginTeacher",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test Teacher", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("Teacher Login", t_login_resp)
t_token = t_login_resp.json().get("data", {}).get("token") or t_login_resp.json().get("data", {}).get("Token")
print(f"\nTeacher token: {t_token[:50]}..." if t_token else "No token")

# 7. Test RegionalAdmin Login
print("\n7. Logging in RegionalAdmin...")
ra_login_resp = requests.post(
    f"{BASE}/RegionalAdmin/LoginRegionalAdmin",
    headers={"Authorization": f"Bearer {app_token}", "Content-Type": "application/json"},
    json={"name": "Test RA", "password": "password123", "deviceid": DEVICE_ID}
)
print_response("RegionalAdmin Login", ra_login_resp)
ra_token = ra_login_resp.json().get("data", {}).get("token") or ra_login_resp.json().get("data", {}).get("Token")
print(f"\nRegionalAdmin token: {ra_token[:50]}..." if ra_token else "No token")

# 8. Test Teacher endpoint with teacher token
if t_token:
    print("\n8. Teacher accessing GetAllCenters...")
    t_centers = requests.get(
        f"{BASE}/Center/GetAllCenters",
        headers={"Authorization": f"Bearer {t_token}", "Content-Type": "application/json"},
        params={"deviceid": DEVICE_ID}
    )
    print_response("Teacher GetAllCenters", t_centers)

print("\n\n✅ All tests completed!")