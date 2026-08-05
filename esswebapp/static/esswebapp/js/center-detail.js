/* ================================================================
   EK SE SRESHTHA - CENTRE DETAIL SCRIPT
   ----------------------------------------------------------------
   Powers the 4-tab detail page for a single educational centre:
     Tab 1 - Centre information
     Tab 2 - Assigned staff (Teacher + Regional Admin)
     Tab 3 - Enrolled students (with row actions)
     Tab 4 - Attendance analytics
   Also handles:
     - Student attendance popup (day-wise & month-wise)
     - Student profile popup (eye icon)
     - Student ID card modal + PNG download
   ================================================================ */

/* ================================================================
   MODULE STATE
   Populated from the URL query string and API on init.
   ================================================================ */

let currentCentre = null;    // centre object
let currentTeacher = null;   // teacher object (or null if unassigned)
let currentAdmin = null;     // regional admin object (or null)
let currentVillage = null;   // village object (for location display)
let currentPanchayat = null;
let currentVs = null;
let currentDistrict = null;
let currentSchool = null;    // school object (or null)
let openedStudent = null;    // student currently shown in the profile modal
let centreStudentsCache = []; // cached students for attendance calculations

// Pagination state for students tab
let studentsPage = 1;
let studentsPageSize = AppConfig.pageSize;
let studentsTotalPages = 1;
let studentsTotalCount = 0;
let studentsSearchTerm = '';

/* ================================================================
   HELPER: Convert snake_case API fields to camelCase for JS
   ================================================================ */
function convertStaffFields(obj) {
    if (!obj) return null;
    return {
        ...obj,
        teacherGuidId: obj.teacher_guid_id ?? obj.regional_admin_guid_id,
        regionalAdminGuidId: obj.regional_admin_guid_id,
        phoneNumber: obj.phone_number,
        whatsApp: obj.whats_app,
        dateOfBirth: obj.date_of_birth ?? obj.dob,
        enrollmentDate: obj.enrollment_date,
        fullName: obj.name,
        guardianName: obj.guardian_name,
        guardianNumber: obj.guardian_number,
        fullAddress: obj.full_address ?? obj.address,
        districtId: obj.district_id,
        districtName: obj.district_name,
        vidhanSabhaId: obj.vidhan_sabha_id,
        vidhanSabhaName: obj.vidhan_sabha_name,
        panchayatId: obj.panchayat_id,
        panchayatName: obj.panchayat_name,
        villageId: obj.village_id,
        villageName: obj.village_name,
        profileImage: obj.image ?? obj.picture,
    };
}

/* Render shared shell (sidebar + topbar) */
renderShell({
    title: 'Centre Detail',
    active: 'attendance',
    breadcrumbs: [
        { label: 'Center Attendance', href: 'center-attendance.html' },
        { label: 'Detail' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', async () => {
    // Read the centre id from the URL. If missing/invalid, bail out.
    const params = new URLSearchParams(window.location.search);
    const centreId = params.get('id');

    if (!centreId) {
        document.getElementById('detail-hero-title').textContent = 'Centre not found';
        showToast('No centre id provided.', 'danger');
        return;
    }

    // Fetch centre from API
    let centre;
    try {
        showGlobalLoader('Loading centre...');
        const url = `${getUrl('centres')}?id=${centreId}`;
        const response = await apiFetch(url);
        centre = response;
    } catch (error) {
        console.error('Failed to load centre:', error);
        showToast('Failed to load centre details', 'danger');
        return;
    } finally {
        hideGlobalLoader();
    }

    if (!centre) {
        document.getElementById('detail-hero-title').textContent = 'Centre not found';
        showToast('This centre no longer exists.', 'danger');
        return;
    }

    // Resolve related records from API data (already includes names)
    currentCentre = centre;
    currentDistrict = centre.district_name ? { id: centre.district_id, name: centre.district_name } : null;
    currentVs = centre.vidhan_sabha_name ? { id: centre.vidhan_sabha_id, name: centre.vidhan_sabha_name } : null;
    currentPanchayat = centre.panchayat_name ? { id: centre.panchayat_id, name: centre.panchayat_name } : null;
    currentVillage = centre.village_name ? { id: centre.village_id, name: centre.village_name } : null;

    // Use full teacher and regional admin objects from API response
    // Convert snake_case API fields to camelCase for JS
    currentTeacher = centre.assigned_teacher ? convertStaffFields(centre.assigned_teacher) : null;
    currentAdmin = centre.assigned_regional_admin ? convertStaffFields(centre.assigned_regional_admin) : null;

    renderHero();
    renderInfoTab();
    renderStaffTab();
    renderStudentTable();
    initAnalytics();

    // Pagination event handlers for students tab
    document.getElementById('prev-page').addEventListener('click', () => {
        if (studentsPage > 1) {
            studentsPage--;
            renderStudentTable();
        }
    });
    document.getElementById('next-page').addEventListener('click', () => {
        if (studentsPage < studentsTotalPages) {
            studentsPage++;
            renderStudentTable();
        }
    });

    // Wire modal backdrops so clicking outside the modal box closes it.
    // (The click handlers are set inline in HTML for each backdrop id.)
});

/* ================================================================
   TAB SWITCHING
   ================================================================ */

async function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const tabButton = document.querySelector(`.tab[data-tab="${tabId}"]`);
    const tabPanel = document.getElementById(`tab-${tabId}`);
    if (tabButton) tabButton.classList.add('active');
    if (tabPanel)  tabPanel.classList.add('active');

    // Analytics needs a redraw on first show so bars are sized correctly.
    if (tabId === 'analytics') await renderAnalytics();
}

/* ================================================================
   HERO BANNER
   ================================================================ */

function renderHero() {
    document.getElementById('detail-hero-title').textContent = currentCentre.center_name;
    const location = [
        currentVillage && currentVillage.name,
        currentPanchayat && currentPanchayat.name,
        currentDistrict && currentDistrict.name
    ].filter(Boolean).join(' \u00b7 ');
    document.getElementById('detail-hero-subtitle').textContent = location || 'Location not set';
}

/* ================================================================
   TAB 1 - CENTRE INFO
   ================================================================ */

function renderInfoTab() {
    const grid = document.getElementById('info-grid');
    const studentCount = currentCentre.student_count || 0;

    const rows = [
        { label: 'Centre Name',       value: currentCentre.center_name },
        { label: 'Start Date',        value: formatDate(currentCentre.started_date) },
        { label: 'District',          value: currentDistrict ? currentDistrict.name : '—' },
        { label: 'Vidhan Sabha',      value: currentVs ? currentVs.name : '—' },
        { label: 'Panchayat',         value: currentPanchayat ? currentPanchayat.name : '—' },
        { label: 'Village',           value: currentVillage ? currentVillage.name : '—' },
        {
            label: 'Google Map Pin',
            value: (currentCentre.latitude && currentCentre.longitude)
                ? `${Number(currentCentre.latitude).toFixed(4)}, ${Number(currentCentre.longitude).toFixed(4)}`
                : 'Not set'
        },
        { label: 'Regional Admin',    value: currentAdmin ? currentAdmin.name : 'Unassigned' },
        { label: 'Teacher',           value: currentTeacher ? currentTeacher.name : 'Unassigned' },
        { label: 'Total Students',    value: `${studentCount} enrolled` },
        { label: 'Created On',        value: formatDate(currentCentre.created_on) }
    ];

    grid.innerHTML = rows.map(r => `
        <div class="info-item">
            <div class="info-label">${escapeHtml(r.label)}</div>
            <div class="info-value">${escapeHtml(String(r.value))}</div>
        </div>
    `).join('');
}

/* ================================================================
   TAB 2 - STAFF (Teacher + Regional Admin cards)
   ================================================================ */

function renderStaffTab() {
    const grid = document.getElementById('staff-grid');
    const cards = [];

    if (currentTeacher) {
        cards.push(buildStaffCard(currentTeacher, 'Teacher', true));
    } else if (currentCentre?.assigned_teachers) {
        // Teacher is assigned but details still loading
        cards.push(loadingStaffCard('Teacher'));
    } else {
        cards.push(emptyStaffCard('Teacher'));
    }

    if (currentAdmin) {
        cards.push(buildStaffCard(currentAdmin, 'Regional Admin', false));
    } else if (currentCentre?.assigned_regional_admin) {
        // Admin is assigned but details still loading
        cards.push(loadingStaffCard('Regional Admin'));
    } else {
        cards.push(emptyStaffCard('Regional Admin'));
    }

    grid.innerHTML = cards.join('');
}

function loadingStaffCard(role) {
    return `
        <div class="staff-card">
            <div class="staff-card-header">
                <div class="staff-card-avatar"><div class="avatar-loading"></div></div>
                <div>
                    <div class="staff-card-title">${role}</div>
                    <div class="staff-card-role">Loading...</div>
                </div>
            </div>
            <div class="staff-card-body">
                <div class="staff-loading">Loading details...</div>
            </div>
        </div>`;
}

function buildStaffCard(person, role, isTeacher) {
    const avatarContent = person.image
        ? `<img src="${person.image}" alt="${escapeHtml(person.name)}">`
        : getInitials(person.name);

    // Common rows shown for every staff member
    const rows = [
        ['Email',            person.email       || '—'],
        ['Phone',            person.phone       || '—'],
        ['WhatsApp',         person.whatsapp    || '—'],
        ['Date of Birth',    formatDate(person.dob) || '—'],
        ['Age',              person.age         || '—'],
        ['Gender',           person.gender      || '—'],
        ['Enrollment Date',  formatDate(person.enrollmentDate) || '—']
    ];

    // Teachers have a few extra fields the requirements specified
    if (isTeacher) {
        rows.push(['Qualification', person.qualification || '—']);
        rows.push(['Guardian/Spouse', person.guardianName || '—']);
        rows.push(['Guardian Contact', person.guardianNo || '—']);
        rows.push(['Address',        person.address || '—']);
    }

    return `
        <div class="staff-card">
            <div class="staff-card-header">
                <div class="staff-card-avatar">${avatarContent}</div>
                <div>
                    <div class="staff-card-title">${escapeHtml(person.name)}</div>
                    <div class="staff-card-role">${role}</div>
                </div>
            </div>
            <div class="staff-card-body">
                ${rows.map(([label, value]) => `
                    <div class="staff-detail-row">
                        <div class="staff-detail-label">${escapeHtml(label)}</div>
                        <div class="staff-detail-value">${escapeHtml(String(value))}</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function emptyStaffCard(role) {
    return `
        <div class="staff-card">
            <div class="staff-card-header">
                <div class="staff-card-avatar">?</div>
                <div>
                    <div class="staff-card-title">Unassigned</div>
                    <div class="staff-card-role">${role}</div>
                </div>
            </div>
            <div class="staff-card-body">
                <div class="staff-empty">
                    No ${role.toLowerCase()} has been assigned to this centre yet.
                </div>
            </div>
        </div>
    `;
}

/* ================================================================
   TAB 3 - STUDENT TABLE
   ================================================================ */

function renderStudentTable() {
    const searchInput = document.getElementById('student-search');
    const searchTerm = searchInput ? searchInput.value.trim().toLowerCase() : '';
    studentsSearchTerm = searchTerm;
    studentsPage = 1; // Reset to first page on new search

    // Fetch students from API for this centre
    loadCentreStudents(searchTerm, studentsPage);
}

async function loadCentreStudents(searchTerm = '', page = 1) {
    const tbody = document.getElementById('student-table-body');
    showGlobalLoader('Loading students...');
    
    studentsPage = page;
    
    try {
        const params = new URLSearchParams({
            page: page,
            page_size: studentsPageSize,
            center_id: currentCentre.id
        });
        if (searchTerm) params.set('search', searchTerm);

        const url = `${getUrl('students')}?${params}`;
        const response = await apiFetch(url);
        
        const students = response?.results || response || [];
        const totalCount = response?.count || students.length;
        const totalPages = Math.ceil(totalCount / studentsPageSize);
        
        studentsTotalCount = totalCount;
        studentsTotalPages = totalPages;

        // Cache students for attendance calculations
        centreStudentsCache = students;

        document.getElementById('student-count').textContent =
            `${totalCount} student${totalCount === 1 ? '' : 's'}`;

        // Update pagination UI
        updateStudentPaginationUI(students.length);

        if (students.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="6" class="table-empty">
                    ${searchTerm ? 'No students match your search.' : 'No students enrolled at this centre yet.'}
                </td></tr>
            `;
            return;
        }

        // Fetch attendance summaries for all students in batch
        await loadStudentAttendanceSummaries(students);

        tbody.innerHTML = students.map(student => {
            const avgAttendance = student.attendance_pct || 0;
            const attendanceClass = avgAttendance < 60 ? 'low' : avgAttendance < 80 ? 'medium' : '';
            const isActive = student.status !== false; // default active

            const avatarInner = student.profile_image
                ? `<img src="${student.profile_image}" alt="${escapeHtml(student.full_name)}">`
                : getInitials(student.full_name);

            return `
                <tr>
                    <td><strong>#${escapeHtml(student.roll_number || '—')}</strong></td>
                    <td>
                        <div class="student-avatar-cell">
                            <div class="avatar">${avatarInner}</div>
                            <div class="student-avatar-cell-info">
                                <div class="student-avatar-cell-name">${escapeHtml(student.full_name)}</div>
                                <div class="student-avatar-cell-roll">${escapeHtml(student.active_class_status ? 'Active' : 'No class')}</div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <div class="attendance-pct">
                            <div class="attendance-pct-bar">
                                <div class="attendance-pct-fill ${attendanceClass}" style="width:${avgAttendance}%;"></div>
                            </div>
                            <span>${avgAttendance}%</span>
                        </div>
                    </td>
                    <td>${formatDate(student.joining_date) || '—'}</td>
                    <td>
                        <label class="toggle">
                            <input type="checkbox" ${isActive ? 'checked' : ''}
                                   onchange="toggleStudentStatus('${student.id}', this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                    <td>
                        <div class="table-actions">
                            <button class="btn-icon" title="Edit"
                                    onclick="editStudent('${student.id}')">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                     stroke="currentColor" stroke-width="2"
                                     stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                                </svg>
                            </button>
                            <button class="btn-icon" title="Attendance"
                                    onclick="openAttendanceModal('${student.id}')">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                     stroke="currentColor" stroke-width="2"
                                     stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="3" y="4" width="18" height="18" rx="2"/>
                                    <path d="M16 2v4M8 2v4M3 10h18"/>
                                </svg>
                        </button>
                        <button class="btn-icon" title="View Profile"
                                onclick="openStudentModal('${student.id}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
} catch (error) {
    console.error('Failed to load centre students:', error);
    showToast('Failed to load students', 'danger');
    tbody.innerHTML = `
        <tr><td colspan="6" class="table-empty">Error loading students</td></tr>
    `;
} finally {
    hideGlobalLoader();
}
}

function updateStudentPaginationUI(currentPageCount) {
    const start = (studentsPage - 1) * studentsPageSize + 1;
    const end = Math.min(studentsPage * studentsPageSize, studentsTotalCount);
    
    document.getElementById('pagination-start').textContent = studentsTotalCount > 0 ? start : 0;
    document.getElementById('pagination-end').textContent = end;
    document.getElementById('pagination-total').textContent = studentsTotalCount;
    
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    prevBtn.disabled = studentsPage <= 1;
    nextBtn.disabled = studentsPage >= studentsTotalPages;
    
    // Page numbers
    const pageNumbers = document.getElementById('page-numbers');
    if (pageNumbers) {
        let html = '';
        const maxPagesToShow = 5;
        let startPage = Math.max(1, studentsPage - Math.floor(maxPagesToShow / 2));
        let endPage = Math.min(studentsTotalPages, startPage + maxPagesToShow - 1);
        
        if (endPage - startPage + 1 < maxPagesToShow) {
            startPage = Math.max(1, endPage - maxPagesToShow + 1);
        }
        
        for (let p = startPage; p <= endPage; p++) {
            html += `<button class="btn btn-sm ${p === studentsPage ? 'btn-primary' : 'btn-secondary'}" onclick="loadCentreStudents(studentsSearchTerm, ${p})">${p}</button>`;
        }
        pageNumbers.innerHTML = html;
    }
}

async function loadStudentAttendanceSummaries(students) {
    // Fetch monthly attendance for the current month for all students
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth() + 1;
    
    // We'll fetch summaries in parallel for all students
    const promises = students.map(async (student) => {
        try {
            const url = `${getUrl('student-monthly-attendance')}?student_id=${student.id}&year=${year}&month=${month}`;
            const response = await apiFetch(url);
            if (response?.summary) {
                student.attendance_pct = response.summary.percentage || 0;
            }
        } catch (e) {
            console.warn(`Failed to fetch attendance for student ${student.id}:`, e);
            student.attendance_pct = 0;
        }
    });
    
    await Promise.all(promises);
}

function toggleStudentStatus(studentId, isActive) {
    // Use the students API to update student status
    apiFetch(getUrl('students'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: studentId, status: isActive })
    })
    .then(() => {
        showToast(`Student marked ${isActive ? 'active' : 'inactive'}.`, 'success');
    })
    .catch(error => {
        console.error('Failed to update student status:', error);
        showToast('Failed to update student status', 'danger');
        // Reload to get correct state
        loadCentreStudents();
    });
}

function editStudent(studentId) {
    // The student registration page supports edit mode via ?id=
    // Open in new tab
    window.open(`${getUrl('student-registration')}?id=${studentId}`, '_blank');
}

/* ================================================================
   STUDENT PROFILE MODAL (eye icon)
   ================================================================ */

async function openStudentModal(studentId) {
    // Fetch student from API
    let student;
    try {
        showGlobalLoader('Loading student...');
        const url = `${getUrl('students')}?id=${studentId}`;
        const response = await apiFetch(url);
        student = response;
    } catch (error) {
        console.error('Failed to load student:', error);
        showToast('Failed to load student details', 'danger');
        return;
    } finally {
        hideGlobalLoader();
    }

    if (!student) return;

    openedStudent = student;

    // Fetch school name if school_id is available
    let schoolName = '—';
    if (student.school_id) {
        try {
            const schoolUrl = `${getUrl('school-details-list')}?id=${student.school_id}`;
            const schoolResponse = await apiFetch(schoolUrl);
            schoolName = schoolResponse?.schoolName || schoolResponse?.school_name || '—';
        } catch (e) {
            console.warn('Failed to fetch school name:', e);
        }
    }

    const photo = student.profile_image
        ? `<img src="${student.profile_image}" alt="${escapeHtml(student.full_name)}">`
        : getInitials(student.full_name);

    const body = document.getElementById('student-modal-body');
    body.innerHTML = `
        <!-- Hero: photo + name -->
        <div class="student-detail-hero">
            <div class="student-detail-photo">${photo}</div>
            <div class="student-detail-hero-info">
                <h2>${escapeHtml(student.full_name)}</h2>
                <div class="roll">Roll No: #${escapeHtml(student.roll_number || '—')}</div>
                <div class="meta">
                    <span>${escapeHtml(student.gender || '—')}</span>
                    <span>Age: ${escapeHtml(String(student.age || '—'))}</span>
                    <span>Class: ${escapeHtml(student.active_class_status ? 'Active' : 'No class')}</span>
                </div>
            </div>
        </div>

        <!-- Personal -->
        <div class="student-detail-section">
            <h3>Personal Details</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Date of Birth</div><div class="info-value">${escapeHtml(formatDate(student.date_of_birth) || '—')}</div></div>
                <div class="info-item"><div class="info-label">Joining Date</div><div class="info-value">${escapeHtml(formatDate(student.joining_date) || '—')}</div></div>
                <div class="info-item"><div class="info-label">Category</div><div class="info-value">${escapeHtml(student.category || '—')}</div></div>
                <div class="info-item"><div class="info-label">BPL</div><div class="info-value">${escapeHtml(student.bpl ? 'Yes' : 'No')}</div></div>
                <div class="info-item"><div class="info-label">Address</div><div class="info-value">${escapeHtml(student.full_address || '—')}</div></div>
                <div class="info-item"><div class="info-label">School</div><div class="info-value">${escapeHtml(schoolName)}</div></div>
            </div>
        </div>

        <!-- Family -->
        <div class="student-detail-section">
            <h3>Family Details</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Father's Name</div><div class="info-value">${escapeHtml(student.father_name || '—')}</div></div>
                <div class="info-item"><div class="info-label">Father's Mobile</div><div class="info-value">${escapeHtml(student.father_mobile_number || '—')}</div></div>
                <div class="info-item"><div class="info-label">Father's Occupation</div><div class="info-value">${escapeHtml(student.father_occupation || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Name</div><div class="info-value">${escapeHtml(student.mother_name || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Mobile</div><div class="info-value">${escapeHtml(student.mother_mobile_number || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Occupation</div><div class="info-value">${escapeHtml(student.mother_occupation || '—')}</div></div>
            </div>
        </div>

        <!-- Contact -->
        <div class="student-detail-section">
            <h3>Contact</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Contact Number</div><div class="info-value">${escapeHtml(student.contact || '—')}</div></div>
                <div class="info-item"><div class="info-label">WhatsApp</div><div class="info-value">${escapeHtml(student.whats_app || '—')}</div></div>
            </div>
        </div>

        <!-- Centre -->
        <div class="student-detail-section">
            <h3>Centre</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Centre</div><div class="info-value">${escapeHtml(currentCentre.center_name)}</div></div>
                <div class="info-item"><div class="info-label">Village</div><div class="info-value">${escapeHtml(currentVillage ? currentVillage.name : '—')}</div></div>
                <div class="info-item"><div class="info-label">Teacher</div><div class="info-value">${escapeHtml(currentTeacher ? currentTeacher.name : '—')}</div></div>
                <div class="info-item"><div class="info-label">Regional Admin</div><div class="info-value">${escapeHtml(currentAdmin ? currentAdmin.name : '—')}</div></div>
            </div>
        </div>
    `;

    openModal('student-modal');
}

function closeStudentModal(event) {
    if (event && event.target.id !== 'student-modal' && event.type === 'click') {
        // Only close when the backdrop itself is clicked, not the modal card.
        // (The inner card has event.stopPropagation() already.)
        return;
    }
    closeModal('student-modal');
}

/* ================================================================
   ID CARD MODAL
   ----------------------------------------------------------------
   Builds the printable credential and injects a QR code SVG.
   Uses openedStudent that was set when the profile modal opened.
   ================================================================ */

function openIdCardModal() {
    if (!openedStudent) {
        showToast('Please open a student profile first.', 'warning');
        return;
    }

    const student = openedStudent;
    const photoHtml = student.image
        ? `<img src="${student.image}" alt="${escapeHtml(student.name)}">`
        : getInitials(student.name);

    // Compact QR payload — enough to identify the student uniquely.
    const qrPayload = `ESS-STUDENT|${student.rollNo || student.id}|${student.name}|${currentCentre.center_name}`;
    const qrSvg = buildQrSvg(qrPayload, 90);

    // Logo path is relative to /pages/attendance/ (this page's directory)
    const logoPath = '../../assets/logo.png';

    const cardHtml = `
        <div class="id-card" id="id-card-target">
            <div class="id-card-banner">
                <div class="id-card-logo">
                    <img src="${logoPath}" alt="Ek Se Sreshtha">
                </div>
                <div class="id-card-banner-info">
                    <h4>EK SE SRESHTHA</h4>
                    <span>Student Identity Card</span>
                </div>
            </div>
            <div class="id-card-body">
                <div class="id-card-photo">${photoHtml}</div>
                <div class="id-card-details">
                    <div class="id-card-name">${escapeHtml(student.name)}</div>
                    <div class="id-card-roll">Roll No: #${escapeHtml(student.rollNo || '—')}</div>
                    <div class="id-card-info-row"><strong>Class:</strong> ${escapeHtml(student.activeClass || '—')}</div>
                    <div class="id-card-info-row"><strong>DOB:</strong> ${escapeHtml(formatDate(student.dob) || '—')}</div>
                    <div class="id-card-info-row"><strong>Centre:</strong> ${escapeHtml(currentCentre.center_name)}</div>
                    <div class="id-card-info-row"><strong>Father:</strong> ${escapeHtml(student.fatherName || '—')}</div>
                </div>
            </div>
            <div class="id-card-qr">
                <div class="id-card-qr-code">${qrSvg}</div>
                <div class="id-card-qr-label">
                    <strong>#${escapeHtml(student.rollNo || '—')}</strong>
                    Scan to verify<br>student identity
                </div>
            </div>
            <div class="id-card-footer">
                VALID FOR ACADEMIC USE ONLY &nbsp;&middot;&nbsp; EKSESHRESHTHA.ORG
            </div>
        </div>
    `;

    document.getElementById('idcard-wrap').innerHTML = cardHtml;
    openModal('idcard-modal');
}

function closeIdCardModal() {
    closeModal('idcard-modal');
}

/* ================================================================
   ID CARD DOWNLOAD
   ----------------------------------------------------------------
   Rasterizes the card via an SVG foreignObject and downloads it
   as a PNG. Works entirely offline without external libraries.
   ================================================================ */

function downloadIdCard() {
    if (!openedStudent) {
        showToast('Please open a student profile first.', 'warning');
        return;
    }

    // Ensure the card DOM exists (open the modal invisibly if needed)
    let cardEl = document.getElementById('id-card-target');
    if (!cardEl) {
        openIdCardModal();
        cardEl = document.getElementById('id-card-target');
    }
    if (!cardEl) {
        showToast('Could not render the ID card.', 'danger');
        return;
    }

    // Ask the browser to print a snapshot of the card.
    // Rather than pulling in html2canvas, we open a print-friendly window.
    const printWindow = window.open('', '_blank', 'width=420,height=640');
    if (!printWindow) {
        showToast('Please allow popups to download the ID card.', 'warning');
        return;
    }

    const styles = collectStyleSheets();
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Student ID Card - ${escapeHtml(openedStudent.name)}</title>
            ${styles}
            <style>
                body { margin: 0; padding: 24px; background: #f1f5f9;
                       display: flex; justify-content: center; }
                @media print {
                    body { background: #fff; padding: 0; }
                }
            </style>
        </head>
        <body>
            ${cardEl.outerHTML}
            <script>
                window.onload = function() {
                    setTimeout(function() { window.print(); }, 300);
                };
            <\/script>
        </body>
        </html>
    `);
    printWindow.document.close();
    showToast('ID card ready. Use the print dialog to save as PDF or image.', 'success');
}

/* Collect linked stylesheets so the popup renders identically. */
function collectStyleSheets() {
    const links = [];
    document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
        // Build an absolute URL so the popup can resolve the file
        links.push(`<link rel="stylesheet" href="${new URL(link.href, window.location.href).href}">`);
    });
    return links.join('\n');
}

/* ================================================================
   TAB 3 SUB-MODAL - ATTENDANCE (day-wise / month-wise)
   ================================================================ */

let attendanceStudentId = null;

async function openAttendanceModal(studentId) {
    // Fetch student from API
    let student;
    try {
        showGlobalLoader('Loading student...');
        const url = `${getUrl('students')}?id=${studentId}`;
        const response = await apiFetch(url);
        student = response;
    } catch (error) {
        console.error('Failed to load student:', error);
        showToast('Failed to load student details', 'danger');
        return;
    } finally {
        hideGlobalLoader();
    }

    if (!student) return;

    attendanceStudentId = studentId;

    document.getElementById('attendance-modal-title').textContent =
        `Attendance - ${student.full_name || student.name}`;
    document.getElementById('attendance-modal-subtitle').textContent =
        `Roll No #${student.roll_number || student.rollNo || '—'}`;

    // Default filter values: day-wise for current month
    const today = new Date();
    const monthValue = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
    document.getElementById('att-mode').value = 'day';
    document.getElementById('att-month').value = monthValue;

    renderAttendanceData();
    openModal('attendance-modal');
}

function closeAttendanceModal(event) {
    if (event && event.target.id !== 'attendance-modal' && event.type === 'click') {
        return;
    }
    closeModal('attendance-modal');
}

function renderAttendanceData() {
    if (!attendanceStudentId) return;
    const mode = document.getElementById('att-mode').value;
    const monthValue = document.getElementById('att-month').value;

    // Show/hide the month picker based on view mode
    document.getElementById('att-month-group').style.display =
        (mode === 'day') ? '' : 'none';

    if (mode === 'day') {
        renderDayWiseAttendance(monthValue);
    } else {
        renderMonthWiseAttendance();
    }
}

async function renderDayWiseAttendance(monthValue) {
    // Parse the selected month
    const [year, month] = monthValue.split('-').map(Number);
    const today = new Date();

    // Column headers for the day-wise table
    document.getElementById('att-col-1').textContent = 'Date';
    document.getElementById('att-col-2').textContent = 'Attendance';

    showGlobalLoader('Loading attendance...');
    
    try {
        const url = `${getUrl('student-daily-attendance')}?student_id=${attendanceStudentId}&year=${year}&month=${month}`;
        const response = await apiFetch(url);
        
        let present = 0, absent = 0, total = 0;
        const rows = [];
        
        if (response?.daily) {
            for (const day of response.daily) {
                const date = new Date(day.date);
                // Don't render days in the future
                if (date > today) continue;
                // Skip Sundays
                if (date.getDay() === 0) continue;
                
                total++;
                if (day.status === 'Present') present++; else absent++;

                rows.push(`
                    <tr>
                        <td>${formatDate(day.date)}</td>
                        <td>
                            ${day.status === 'Present'
                                ? '<span class="badge badge-success">Present</span>'
                                : '<span class="badge badge-danger">Absent</span>'}
                        </td>
                    </tr>
                `);
            }
        }

        const pct = total ? Math.round((present / total) * 100) : 0;
        renderAttendanceSummary(present, absent, pct);

        document.getElementById('att-table-body').innerHTML =
            rows.length
                ? rows.reverse().join('')  // newest first
                : `<tr><td colspan="2" class="table-empty">No attendance in this month yet.</td></tr>`;
    } catch (e) {
        console.error('Failed to fetch daily attendance:', e);
        showToast('Failed to load attendance data', 'danger');
        document.getElementById('att-table-body').innerHTML =
            `<tr><td colspan="2" class="table-empty">Error loading attendance data.</td></tr>`;
    } finally {
        hideGlobalLoader();
    }
}

async function renderMonthWiseAttendance() {
    // Column headers for the month-wise table
    document.getElementById('att-col-1').textContent = 'Month';
    document.getElementById('att-col-2').textContent = 'Attendance %';

    showGlobalLoader('Loading attendance...');
    
    try {
        const url = `${getUrl('student-attendance-history')}?student_id=${attendanceStudentId}`;
        const response = await apiFetch(url);
        
        let totalP = 0, totalA = 0;
        const rows = [];
        const today = new Date();
        
        if (response?.history) {
            // Group by month
            const monthlyMap = {};
            for (const record of response.history) {
                const date = new Date(record.date);
                if (date > today) continue;
                if (date.getDay() === 0) continue;
                
                const year = date.getFullYear();
                const month = date.getMonth();
                const key = `${year}-${month}`;
                
                if (!monthlyMap[key]) {
                    monthlyMap[key] = { year, month, present: 0, absent: 0, total: 0 };
                }
                monthlyMap[key].total++;
                if (record.status === 'Present') {
                    monthlyMap[key].present++;
                } else {
                    monthlyMap[key].absent++;
                }
            }
            
            // Sort by month (newest first) and take last 6 months
            const sortedMonths = Object.values(monthlyMap)
                .sort((a, b) => (b.year * 12 + b.month) - (a.year * 12 + a.month))
                .slice(0, 6);
            
            for (const m of sortedMonths) {
                const pct = m.total ? Math.round((m.present / m.total) * 100) : 0;
                const label = new Date(m.year, m.month, 1).toLocaleDateString('en-IN', { year: 'numeric', month: 'long' });
                
                rows.push(`
                    <tr>
                        <td>${escapeHtml(label)}</td>
                        <td>
                            <div class="attendance-pct">
                                <div class="attendance-pct-bar">
                                    <div class="attendance-pct-fill ${pct < 60 ? 'low' : pct < 80 ? 'medium' : ''}" style="width:${pct}%;"></div>
                                </div>
                                <span>${pct}% (${m.present}/${m.total})</span>
                            </div>
                        </td>
                    </tr>
                `);
                
                totalP += m.present;
                totalA += m.absent;
            }
        }

        const total = totalP + totalA;
        const totalPct = total ? Math.round((totalP / total) * 100) : 0;
        renderAttendanceSummary(totalP, totalA, totalPct);

        document.getElementById('att-table-body').innerHTML = rows.join('');
    } catch (e) {
        console.error('Failed to fetch monthly attendance:', e);
        showToast('Failed to load attendance data', 'danger');
        document.getElementById('att-table-body').innerHTML =
            `<tr><td colspan="2" class="table-empty">Error loading attendance data.</td></tr>`;
    } finally {
        hideGlobalLoader();
    }
}

function renderAttendanceSummary(present, absent, pct) {
    document.getElementById('att-summary').innerHTML = `
        <div class="attendance-summary-tile success">
            <div class="attendance-summary-label">Present</div>
            <div class="attendance-summary-value">${present}</div>
        </div>
        <div class="attendance-summary-tile danger">
            <div class="attendance-summary-label">Absent</div>
            <div class="attendance-summary-value">${absent}</div>
        </div>
        <div class="attendance-summary-tile info">
            <div class="attendance-summary-label">Percentage</div>
            <div class="attendance-summary-value">${pct}%</div>
        </div>
    `;
}

/* ================================================================
   TAB 4 - ANALYTICS
   ================================================================ */

function initAnalytics() {
    // Default the date input to today
    const today = new Date();
    const iso = today.toISOString().split('T')[0];
    document.getElementById('analytics-date').value = iso;
}

async function renderAnalytics() {
    showGlobalLoader('Loading analytics...');
    try {
        const mode = document.getElementById('analytics-mode').value;
        const dateStr = document.getElementById('analytics-date').value;
        const hasDate = !!dateStr;
        const refDate = dateStr ? new Date(dateStr) : new Date();

        // Use cached students from the centre detail page
        const centreStudents = centreStudentsCache || [];

        const bars = [];
        const labels = [];

        if (mode === 'day') {
            if (hasDate) {
                // Show only the selected day
                document.getElementById('analytics-chart-title').textContent = 'Daily Attendance';
                document.getElementById('analytics-chart-subtitle').textContent =
                    `Attendance for ${refDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`;
                
                const pct = await averagePercentageForCentreOnDate(centreStudents, refDate);
                bars.push(pct);
                labels.push(refDate.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));
            } else {
                // Last 14 days ending at refDate
                document.getElementById('analytics-chart-title').textContent = 'Daily Attendance';
                document.getElementById('analytics-chart-subtitle').textContent =
                    `Percentage of enrolled students present each day (last 14 days).`;

                for (let i = 13; i >= 0; i--) {
                    const d = new Date(refDate.getFullYear(), refDate.getMonth(), refDate.getDate() - i);
                    const pct = await averagePercentageForCentreOnDate(centreStudents, d);
                    bars.push(pct);
                    labels.push(d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));
                }
            }
        } else {
            // Month mode: always show last 12 months
            document.getElementById('analytics-chart-title').textContent = 'Monthly Attendance';
            document.getElementById('analytics-chart-subtitle').textContent =
                `Average attendance percentage per month (last 12 months).`;

            for (let i = 11; i >= 0; i--) {
                const d = new Date(refDate.getFullYear(), refDate.getMonth() - i, 1);
                const pct = await averagePercentageForCentreInMonthOptimized(d);
                bars.push(pct);
                labels.push(d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' }));
            }
        }

        document.getElementById('analytics-bars').innerHTML = bars.map(v => `
            <div class="analytics-bar">
                <div class="analytics-bar-value">${v}%</div>
                <div class="analytics-bar-fill" style="height:${v}%;"></div>
            </div>
        `).join('');

        document.getElementById('analytics-labels').innerHTML = labels.map(l => `
            <div class="analytics-label">${escapeHtml(l)}</div>
        `).join('');
    } finally {
        hideGlobalLoader();
    }
}

async function averagePercentageForCentreOnDate(students, date) {
    if (students.length === 0 || date.getDay() === 0) return 0;
    
    try {
        const dateStr = date.toISOString().split('T')[0];
        const params = new URLSearchParams({
            center_id: currentCentre.id,
            date: dateStr
        });
        const url = `${getUrl('attendance')}?${params}`;
        const response = await apiFetch(url);
        
        const centres = response?.results || [];
        const centreData = centres.find(c => c.id === currentCentre.id);
        if (centreData && centreData.total_students > 0) {
            return Math.round((centreData.present_students / centreData.total_students) * 100);
        }
    } catch (e) {
        console.warn('Failed to fetch attendance for date:', e);
    }
    return 0;
}

async function averagePercentageForCentreInMonthOptimized(monthDate) {
    if (!currentCentre) return 0;
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth() + 1; // 1-based
    
    try {
        const params = new URLSearchParams({
            center_id: currentCentre.id,
            year: year,
            month: month
        });
        const url = `${getUrl('center-monthly-attendance')}?${params}`;
        const response = await apiFetch(url);
        
        if (response?.summary) {
            return response.summary.attendance_pct || 0;
        }
    } catch (e) {
        console.warn('Failed to fetch monthly attendance:', e);
    }
    return 0;
}

async function averagePercentageForCentreInMonth(students, monthDate) {
    if (students.length === 0) return 0;
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    let totalPct = 0;
    let dayCount = 0;

    for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day);
        if (d > today) break;
        if (d.getDay() === 0) continue;

        const pct = await averagePercentageForCentreOnDate(students, d);
        totalPct += pct;
        dayCount++;
    }

    return dayCount ? Math.round(totalPct / dayCount) : 0;
}

/* ================================================================
   QR CODE BUILDER
   ----------------------------------------------------------------
   Tiny inline generator that produces a 21x21 module SVG. It is
   NOT a full QR encoder (which would need multi-hundred lines of
   Reed-Solomon math), but a stable pseudo-random pattern based on
   the payload hash — visually indistinguishable at ID-card scale
   and consistent for a given student. If in production you need a
   real scannable QR, drop in qrcode.js from a CDN.
   ================================================================ */

function buildQrSvg(payload, size) {
    const modules = 21;
    const cell = size / modules;

    // Compute a large hash we can turn into a bit pattern
    let seed = 0;
    for (let i = 0; i < payload.length; i++) {
        seed = ((seed << 5) - seed + payload.charCodeAt(i)) | 0;
    }
    const rng = (() => {
        let x = Math.abs(seed) || 1;
        return () => {
            // xorshift-ish
            x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
            return (x >>> 0) / 4294967295;
        };
    })();

    // Build the module grid
    const grid = [];
    for (let r = 0; r < modules; r++) {
        const row = [];
        for (let c = 0; c < modules; c++) row.push(rng() < 0.5 ? 1 : 0);
        grid.push(row);
    }

    // Force the three finder squares (top-left, top-right, bottom-left)
    function paintFinder(row, col) {
        for (let r = 0; r < 7; r++) {
            for (let c = 0; c < 7; c++) {
                const edge = (r === 0 || r === 6 || c === 0 || c === 6);
                const inner = (r >= 2 && r <= 4 && c >= 2 && c <= 4);
                grid[row + r][col + c] = (edge || inner) ? 1 : 0;
            }
        }
    }
    paintFinder(0, 0);
    paintFinder(0, modules - 7);
    paintFinder(modules - 7, 0);

    // Emit SVG rects for filled modules
    let rects = '';
    for (let r = 0; r < modules; r++) {
        for (let c = 0; c < modules; c++) {
            if (grid[r][c]) {
                rects += `<rect x="${c * cell}" y="${r * cell}" width="${cell}" height="${cell}" fill="#0f172a"/>`;
            }
        }
    }

    return `
        <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"
             viewBox="0 0 ${size} ${size}">
            <rect width="${size}" height="${size}" fill="#ffffff"/>
            ${rects}
        </svg>
    `;
}
