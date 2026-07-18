#!/bin/bash
# Quick curl-based API testing script
# Usage: ./quick_test.sh

BASE="http://127.0.0.1:8000/api"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=== Quick API Test Suite ==="
echo

# 1. Login SuperAdmin
echo "1. SuperAdmin Login..."
SA_TOKEN=$(curl -s -X POST "$BASE/User/LoginUser" \
  -H "Content-Type: application/json" \
  -d '{"PhoneNumber":"9999999999","Password":"password123"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Data',{}).get('Token') or d.get('data',{}).get('Token',''))")

if [ -n "$SA_TOKEN" ] && [ "$SA_TOKEN" != "" ]; then
    echo -e "${GREEN}✓ SuperAdmin token: ${SA_TOKEN:0:20}...${NC}"
else
    echo -e "${RED}✗ SuperAdmin login failed${NC}"
    exit 1
fi

# 2. Login RegionalAdmin
echo "2. RegionalAdmin Login..."
RA_TOKEN=$(curl -s -X POST "$BASE/RegionalAdmin/LoginRegionalAdmin" \
  -H "Content-Type: application/json" \
  -d '{"PhoneNumber":"8888888888","Password":"password123"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Data',{}).get('Token') or d.get('data',{}).get('Token',''))")

if [ -n "$RA_TOKEN" ] && [ "$RA_TOKEN" != "" ]; then
    echo -e "${GREEN}✓ RegionalAdmin token: ${RA_TOKEN:0:20}...${NC}"
else
    echo -e "${RED}✗ RegionalAdmin login failed${NC}"
fi

# 3. Login Teacher
echo "3. Teacher Login..."
T_TOKEN=$(curl -s -X POST "$BASE/Teacher/LoginTeacher" \
  -H "Content-Type: application/json" \
  -d '{"PhoneNumber":"7777777777","Password":"password123"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Data',{}).get('Token') or d.get('data',{}).get('Token',''))")

if [ -n "$T_TOKEN" ] && [ "$T_TOKEN" != "" ]; then
    echo -e "${GREEN}✓ Teacher token: ${T_TOKEN:0:20}...${NC}"
else
    echo -e "${RED}✗ Teacher login failed${NC}"
fi

echo
echo "=== Testing SuperAdmin Endpoints ==="

# Test endpoints with SuperAdmin
test_endpoint() {
    local name=$1
    local url=$2
    local token=$3
    local method=${4:-GET}
    local data=$5
    
    if [ "$method" = "POST" ]; then
        resp=$(curl -s -w "\n%{http_code}" -X POST "$url" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        resp=$(curl -s -w "\n%{http_code}" -X GET "$url" \
            -H "Authorization: Bearer $token")
    fi
    
    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓${NC} $name ($http_code)"
    else
        echo -e "${RED}✗${NC} $name ($http_code) - $body"
    fi
}

# SuperAdmin tests
test_endpoint "Get All Users" "$BASE/User/GetAllUsers" "$SA_TOKEN"
test_endpoint "Get All Centers" "$BASE/Center/GetAllCenters" "$SA_TOKEN"
test_endpoint "Get All Districts" "$BASE/District/GetAllDistricts" "$SA_TOKEN"
test_endpoint "Get All Vidhan Sabhas" "$BASE/VidhanSabha/GetAllVidhanSabhas" "$SA_TOKEN"
test_endpoint "Get All Panchayats" "$BASE/Panchayat/GetAllPanchayats" "$SA_TOKEN"
test_endpoint "Get All Villages" "$BASE/Village/GetAllVillages" "$SA_TOKEN"
test_endpoint "Get All Schools" "$BASE/School/GetAllSchools" "$SA_TOKEN"
test_endpoint "Get All Classes" "$BASE/Class/GetAllClasses" "$SA_TOKEN"
test_endpoint "Get All Teachers" "$BASE/Teacher/GetAllTeachers" "$SA_TOKEN"
test_endpoint "Get All Regional Admins" "$BASE/RegionalAdmin/GetAllRegionalAdmins" "$SA_TOKEN"
test_endpoint "Get All Announcements" "$BASE/Announcement/GetAllAnnouncements" "$SA_TOKEN"
test_endpoint "Get All Holidays" "$BASE/Holiday/GetAllHolidays" "$SA_TOKEN"

# Dashboard tests
test_endpoint "Dashboard: Class Count by Month" "$BASE/Dashboard/GetClassCountByMonth?centerId=1&startDate=2024-01-01&endDate=2024-12-31" "$SA_TOKEN"
test_endpoint "Dashboard: Total Student of Class" "$BASE/Dashboard/GetTotalStudentOfClass?centerId=1" "$SA_TOKEN"
test_endpoint "Dashboard: Total Gender Ratio" "$BASE/Dashboard/GetTotalGenterRatioByCenterId?centerId=1" "$SA_TOKEN"

# Student Attendance tests
test_endpoint "Student Attendance: Avg Attendance" "$BASE/StudentAttendance/GetAllStudentWithAvgAttendance?centerId=1" "$SA_TOKEN"
test_endpoint "Student Attendance: Absent Today" "$BASE/StudentAttendance/GetAllAbsentAttendance?centerId=1" "$SA_TOKEN"

echo
echo "=== Testing RegionalAdmin Endpoints ==="
test_endpoint "RA: Get All Centers" "$BASE/Center/GetAllCenters" "$RA_TOKEN"
test_endpoint "RA: Get All Teachers" "$BASE/Teacher/GetAllTeachers" "$RA_TOKEN"
test_endpoint "RA: Get All Classes" "$BASE/Class/GetAllClasses" "$RA_TOKEN"
test_endpoint "RA: Avg Attendance" "$BASE/StudentAttendance/GetAllStudentWithAvgAttendance?centerId=1" "$RA_TOKEN"
test_endpoint "RA: Absent Today" "$BASE/StudentAttendance/GetAllAbsentAttendance?centerId=1" "$RA_TOKEN"

echo
echo "=== Testing Teacher Endpoints ==="
test_endpoint "Teacher: Get My Center" "$BASE/Center/GetCenterById/1" "$T_TOKEN"
test_endpoint "Teacher: Get Classes" "$BASE/Class/GetAllClasses" "$T_TOKEN"
test_endpoint "Teacher: Avg Attendance" "$BASE/StudentAttendance/GetAllStudentWithAvgAttendance?centerId=1" "$T_TOKEN"
test_endpoint "Teacher: Absent Today" "$BASE/StudentAttendance/GetAllAbsentAttendance?centerId=1" "$T_TOKEN"
test_endpoint "Teacher: Attendance Status" "$BASE/StudentAttendance/GetAllStudentAttendancStatus?centerId=1&scanDate=2024-01-15" "$T_TOKEN"

# Test attendance save
echo "Teacher: Save Attendance..."
resp=$(curl -s -w "\n%{http_code}" -X POST "$BASE/StudentAttendance/SaveStudentAttendance" \
  -H "Authorization: Bearer $T_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"StudentIds":[1,2],"ClassId":1,"CenterId":1,"UserId":1,"ScanDate":"2024-01-15T10:00:00"}')
http_code=$(echo "$resp" | tail -1)
if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓${NC} Teacher: Save Attendance ($http_code)"
else
    echo -e "${RED}✗${NC} Teacher: Save Attendance ($http_code)"
fi

echo
echo "=== Negative Test (No Auth) ==="
resp=$(curl -s -w "\n%{http_code}" -X GET "$BASE/Center/GetAllCenters")
http_code=$(echo "$resp" | tail -1)
if [ "$http_code" = "401" ]; then
    echo -e "${GREEN}✓${NC} Anonymous access blocked (401)"
else
    echo -e "${RED}✗${NC} Anonymous access allowed ($http_code)"
fi

echo
echo "=== Test Complete ==="