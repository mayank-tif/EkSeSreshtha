from django.urls import path
from .views import *

urlpatterns = [
    path("generate-app-token/", GenerateAppTokenView.as_view(), name="generate-app-token"),
    
    path('Announcement/SaveAnnouncement', AnnouncementSaveannouncementPostView.as_view(), name='announcement-saveannouncement-post'),
    path('Announcement/GetAnnouncement', AnnouncementGetannouncementGetView.as_view(), name='announcement-getannouncement-get'),
    
    path('Center/SaveCenter', CenterSavecenterPostView.as_view(), name='center-savecenter-post'),
    path('Center/VerifyLocation', CenterVerifyLocationPostView.as_view(), name='center-verifylocation-post'),
    path('Center/GetCenteryId', CenterGetcenteryidGetView.as_view(), name='center-getcenteryid-get'),
    path('Center/GetAllCenters', CenterGetAllCentersView.as_view(), name='center-getallcenters-get'),
    path('Center/GetAllCentersByStatus', CenterGetAllCentersByStatusView.as_view(), name='center-getallcentersbystatus-get'),
    path('Center/GetCenterByTeacherId', CenterGetcenterbyteacheridGetView.as_view(), name='center-getcenterbyteacherid-get'),
    path('Center/GetAllCenterAttendance', CenterGetallcenterattendanceGetView.as_view(), name='center-getallcenterattendance-get'),
    path('Center/UpdateCenterActiveOrDeactive', CenterUpdatecenteractiveordeactiveGetView.as_view(), name='center-updatecenteractiveordeactive-get'),
    path('Center/GetTotalAttendanceCountOfCenter', CenterGettotalattendancecountofcenterGetView.as_view(), name='center-gettotalattendancecountofcenter-get'),
    
    path('Common/CheckUserMobileNumber', CommonCheckusermobilenumberPostView.as_view(), name='common-checkusermobilenumber-post'),
    
    path('Class/SaveClass', ClassSaveclassPostView.as_view(), name='class-saveclass-post'),
    path('Class/CancelClass', ClassCancelclassPostView.as_view(), name='class-cancelclass-post'),
    path('Class/UpdateEndClassTime', ClassUpdateEndClassTimePostView.as_view(), name='class-updateendclasstime-post'),
    path('Class/UpdateClassSubStatus', ClassUpdateclasssubstatusPostView.as_view(), name='class-updateclasssubstatus-post'),
    path('Class/CancelClassByTeacher', ClassCancelclassbyteacherPostView.as_view(), name='class-cancelclassbyteacher-post'),
    path('Class/DeleteClassByTeacherId', ClassDeleteclassbyteacheridPostView.as_view(), name='class-deleteclassbyteacherid-post'),
    path('Class/GetClassCurrentStatus', ClassGetclasscurrentstatusGetView.as_view(), name='class-getclasscurrentstatus-get'),
    path('Class/GetLiveClassDetail', ClassGetliveclassdetailGetView.as_view(), name='class-getliveclassdetail-get'),
    
    path('Dashboard/GetClassCountByMonth', DashboardGetclasscountbymonthGetView.as_view(), name='dashboard-getclasscountbymonth-get'),
    path('Dashboard/GetTotalGenterRatioByCenterId', DashboardGettotalgenderratiobycenteridGetView.as_view(), name='dashboard-gettotalgenterratiobycenterid-get'),
    path('Dashboard/GetTotalGenderRatioByCenterId', DashboardGettotalgenderratiobycenteridGetView.as_view(), name='dashboard-gettotalgenderratiobycenterid-get'),
    path('Dashboard/GetTotalStudentOfClass', DashboardGettotalstudentofclassGetView.as_view(), name='dashboard-gettotalstudentofclass-get'),
    path('Dashboard/GetCenterDetailByMonth', DashboardGetcenterdetailbymonthGetView.as_view(), name='dashboard-getcenterdetailbymonth-get'),
    path('Dashboard/GetTotalBpl', DashboardGettotalbplGetView.as_view(), name='dashboard-gettotalbpl-get'),
    path('Dashboard/GetTotalStudentCategoryOfClass', DashboardGettotalstudentcategoryofclassGetView.as_view(), name='dashboard-gettotalstudentcategoryofclass-get'),
    path('Dashboard/GetUserByFilter', DashboardGetuserbyfilterGetView.as_view(), name='dashboard-getuserbyfilter-get'),
    path('Dashboard/GetTotalBplByFilter', DashboardGettotalbplbyfilterGetView.as_view(), name='dashboard-gettotalbplbyfilter-get'),
    path('Dashboard/GetTotalGenderRatioByFilter', DashboardGettotalgenderratiobyfilterGetView.as_view(), name='dashboard-gettotalgenderratiobyfilter-get'),
    path('Dashboard/GetTotalStudentCategoryOfClassByFilter', DashboardGettotalstudentcategoryofclassbyfilterGetView.as_view(), name='dashboard-gettotalstudentcategoryofclassbyfilter-get'),
    path('Dashboard/GetTotalStudenGradeOfClassByFilter', DashboardGettotalstudengradeofclassbyfilterGetView.as_view(), name='dashboard-gettotalstudengradeofclassbyfilter-get'),
    path('Dashboard/GetDistrictOfCenterByFilter', DashboardGetdistrictofcenterbyfilterGetView.as_view(), name='dashboard-getdistrictofcenterbyfilter-get'),
    path('Dashboard/GetStudentAttendanceByPercentage', DashboardGetstudentattendancebypercentageGetView.as_view(), name='dashboard-getstudentattendancebypercentage-get'),
    
    path('District/GetAllDistrict', DistrictGetalldistrictGetView.as_view(), name='district-getalldistrict-get'),
    path('District/SaveDistrict', DistrictSavedistrictPostView.as_view(), name='district-savedistrict-post'),
    
    path('File/SendNotification', FileSendnotificationPostView.as_view(), name='file-sendnotification-post'),
    path('File/UploadProfileImage', FileUploadprofileimagePostView.as_view(), name='file-uploadprofileimage-post'),
    
    path('Holidays/SaveHolidays', HolidaysSaveholidaysPostView.as_view(), name='holidays-saveholidays-post'),
    path('Holidays/GetAllHolidaysByTeacherId', HolidaysGetallholidaysbyteacheridGetView.as_view(), name='holidays-getallholidaysbyteacherid-get'),
    path('Holidays/GetAllHolidaysByCenterId', HolidaysGetallholidaysbycenteridGetView.as_view(), name='holidays-getallholidaysbycenterid-get'),
    path('Holidays/GetAllHolidaysByYear', HolidaysGetallholidaysbyyearGetView.as_view(), name='holidays-getallholidaysbyyear-get'),
    path('Holidays/GetAllHolidays', HolidaysGetallholidaysGetView.as_view(), name='holidays-getallholidays-get'),
    path('Holidays/DeleteHolidayById', HolidaysDeleteholidaybyidPostView.as_view(), name='holidays-deleteholidaybyid-post'),
    
    path('Panchayat/GetAllPanchayat', PanchayatGetallpanchayatGetView.as_view(), name='panchayat-getallpanchayat-get'),
    path('Panchayat/SavePanchayat', PanchayatSavepanchayatPostView.as_view(), name='panchayat-savepanchayat-post'),
    path('Panchayat/GetPanchayatByDistrictAndVidhanSabhaId', PanchayatGetpanchayatbydistrictandvidhansabhaidGetView.as_view(), name='panchayat-getpanchayatbydistrictandvidhansabhaid-get'),
    path('Panchayat/CheckPanchayatName', PanchayatCheckpanchayatnamePostView.as_view(), name='panchayat-checkpanchayatname-post'),
    
    path('School/SaveSchool', SchoolSaveschoolPostView.as_view(), name='school-saveschool-post'),
    path('School/GetAllSchools', SchoolGetallschoolsGetView.as_view(), name='school-getallschools-get'),
    
    path('Student/SaveStudent', StudentSavestudentPostView.as_view(), name='student-savestudent-post'),
    path('Student/GetStudentById', StudentGetstudentbyidGetView.as_view(), name='student-getstudentbyid-get'),
    path('Student/UpdateStudentActiveOrInactive', StudentUpdatestudentactiveorinactivePostView.as_view(), name='student-updatestudentactiveorinactive-post'),
    path('Student/GetTotalStudentPresent', StudentGettotalstudentpresentGetView.as_view(), name='student-gettotalstudentpresent-get'),
    path('Student/GetAllStudents', StudentGetallstudentsGetView.as_view(), name='student-getallstudents-get'),
    
    path('StudentAttendance/SaveStudentAttendance', StudentattendanceSavestudentattendancePostView.as_view(), name='studentattendance-savestudentattendance-post'),
    path('StudentAttendance/SaveAutomaticStudentAttendance', StudentattendanceSaveautomaticstudentattendancePostView.as_view(), name='studentattendance-saveautomaticstudentattendance-post'),
    path('StudentAttendance/SaveManualStudentAttendance', StudentattendanceSavemanualstudentattendancePostView.as_view(), name='studentattendance-savemanualstudentattendance-post'),
    path('StudentAttendance/GetAllStudentWihAvgAttendance', StudentattendanceGetallstudentwihavgattendanceGetView.as_view(), name='studentattendance-getallstudentwihavgattendance-get'),
    path('StudentAttendance/GetAllAbsentAttendance', StudentattendanceGetallabsentattendanceGetView.as_view(), name='studentattendance-getallabsentattendance-get'),
    path('StudentAttendance/GetAllStudentAttendancStatus', StudentattendanceGetallstudentattendancstatusGetView.as_view(), name='studentattendance-getallstudentattendancstatus-get'),
    path('StudentAttendance/GetAllStudentAttendancByMonth', StudentattendanceGetallstudentattendancbymonthGetView.as_view(), name='studentattendance-getallstudentattendancbymonth-get'),
    
    path("User/LoginUser", UserLoginView.as_view(), name="login"),
    path('User/SaveSuperAdmin', UserSaveSuperAdminView.as_view(), name='user-save-superadmin'),
    path('User/UpdateDeviceId', UserUpdateDeviceIdView.as_view(), name='user-update-deviceid'),
    path('User/SaveUser', UserSaveUserView.as_view(), name='user-save-user'),
    path('User/UpdateSuperAdminUser', UserUpdateSuperAdminUserView.as_view(), name='user-update-superadmin'),
    path('User/GetUserById', UserGetUserByIdView.as_view(), name='user-get-user-by-id'),
    path('User/GetUserDetailByPhoneNumber', UserGetUserDetailByPhoneNumberView.as_view(), name='user-get-user-detail-by-phone'),
    path('User/UpdatePassword', UserUpdatePasswordView.as_view(), name='user-update-password'),
    path('User/GetAllTeachers', UserGetAllTeachersView.as_view(), name='user-get-all-teachers'),
    path('User/GetAllUnAssignedTeacher', UserGetAllUnAssignedTeacherView.as_view(), name='user-get-all-unassigned-teacher'),
    path('User/GetAllRegionalAdmins', UserGetAllRegionalAdminsView.as_view(), name='user-get-all-regional-admins'),
    path('User/SearchData', UserSearchDataView.as_view(), name='user-search-data'),
    
    path('Teacher/LoginTeacher', TeacherLoginteacherPostView.as_view(), name='teacher-loginteacher-post'),
    path('Teacher/SaveTeacher', TeacherSaveteacherPostView.as_view(), name='teacher-saveteacher-post'),
    
    path('RegionalAdmin/GetAllRegionalAdmin', RegionaladminGetallregionaladminGetView.as_view(), name='regionaladmin-getallregionaladmin-get'),
    path('RegionalAdmin/LoginRegionalAdmin', RegionaladminLoginregionaladminPostView.as_view(), name='regionaladmin-loginregionaladmin-post'),
    path('RegionalAdmin/SaveRegionalAdmin', RegionaladminSaveregionaladminPostView.as_view(), name='regionaladmin-saveregionaladmin-post'),
    
    path('VidhanSabha/GetAllVidhanSabha', VidhansabhaGetallvidhansabhaGetView.as_view(), name='vidhansabha-getallvidhansabha-get'),
    path('VidhanSabha/SaveVidhanSabha', VidhansabhaSavevidhansabhaPostView.as_view(), name='vidhansabha-savevidhansabha-post'),
    path('VidhanSabha/GetVidhanSabhaByDistrictId', VidhansabhaGetvidhansabhabydistrictidGetView.as_view(), name='vidhansabha-getvidhansabhabydistrictid-get'),
    path('VidhanSabha/CheckVidhanSabhaName', VidhansabhaCheckvidhansabhanamePostView.as_view(), name='vidhansabha-checkvidhansabhaname-post'),
    
    path('Village/GetAllVillage', VillageGetallvillageGetView.as_view(), name='village-getallvillage-get'),
    path('Village/SaveVillage', VillageSavevillagePostView.as_view(), name='village-savevillage-post'),
    path('Village/GetVillageByDistrictVidhanSabhaAndPanchId', VillageGetvillagebydistrictvidhansabhaandpanchidGetView.as_view(), name='village-getvillagebydistrictvidhansabhaandpanchid-get'),
    path('Village/CheckVillageName', VillageCheckvillagenamePostView.as_view(), name='village-checkvillagename-post'),
]
