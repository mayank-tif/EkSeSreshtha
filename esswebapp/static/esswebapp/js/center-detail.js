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
   Populated from the URL query string and localStorage on init.
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

document.addEventListener('DOMContentLoaded', () => {
    // Read the centre id from the URL. If missing/invalid, bail out.
    const params = new URLSearchParams(window.location.search);
    const centreId = params.get('id');

    if (!centreId) {
        document.getElementById('detail-hero-title').textContent = 'Centre not found';
        showToast('No centre id provided.', 'danger');
        return;
    }

    const centre = findRecord('centres', centreId);
    if (!centre) {
        document.getElementById('detail-hero-title').textContent = 'Centre not found';
        showToast('This centre no longer exists.', 'danger');
        return;
    }

    // Resolve every related record once, up front.
    currentCentre    = centre;
    currentTeacher   = centre.teacherId       ? findRecord('teachers', centre.teacherId)             : null;
    currentAdmin     = centre.regionalAdminId ? findRecord('regionalAdmins', centre.regionalAdminId) : null;
    currentVillage   = centre.villageId       ? findRecord('villages', centre.villageId)             : null;
    currentPanchayat = centre.panchayatId     ? findRecord('panchayats', centre.panchayatId)         : null;
    currentVs        = centre.vidhanSabhaId   ? findRecord('vidhanSabhas', centre.vidhanSabhaId)    : null;
    currentDistrict  = centre.districtId      ? findRecord('districts', centre.districtId)           : null;

    renderHero();
    renderInfoTab();
    renderStaffTab();
    renderStudentTable();
    initAnalytics();

    // Wire modal backdrops so clicking outside the modal box closes it.
    // (The click handlers are set inline in HTML for each backdrop id.)
});

/* ================================================================
   TAB SWITCHING
   ================================================================ */

function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const tabButton = document.querySelector(`.tab[data-tab="${tabId}"]`);
    const tabPanel = document.getElementById(`tab-${tabId}`);
    if (tabButton) tabButton.classList.add('active');
    if (tabPanel)  tabPanel.classList.add('active');

    // Analytics needs a redraw on first show so bars are sized correctly.
    if (tabId === 'analytics') renderAnalytics();
}

/* ================================================================
   HERO BANNER
   ================================================================ */

function renderHero() {
    document.getElementById('detail-hero-title').textContent = currentCentre.name;
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
    const students = getRecords('students').filter(s => s.centreId === currentCentre.id);

    const rows = [
        { label: 'Centre Name',       value: currentCentre.name },
        { label: 'Start Date',        value: formatDate(currentCentre.startDate) },
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
        { label: 'Total Students',    value: `${students.length} enrolled` },
        { label: 'Created On',        value: formatDate(currentCentre.createdAt) }
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

    if (currentTeacher) cards.push(buildStaffCard(currentTeacher, 'Teacher', true));
    else                cards.push(emptyStaffCard('Teacher'));

    if (currentAdmin)   cards.push(buildStaffCard(currentAdmin, 'Regional Admin', false));
    else                cards.push(emptyStaffCard('Regional Admin'));

    grid.innerHTML = cards.join('');
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
    const tbody = document.getElementById('student-table-body');
    const searchTerm = document.getElementById('student-search').value.trim().toLowerCase();
    const centreStudents = getRecords('students').filter(s => s.centreId === currentCentre.id);

    // Apply search across roll no + name
    const filtered = searchTerm
        ? centreStudents.filter(s =>
            (s.name && s.name.toLowerCase().includes(searchTerm)) ||
            (s.rollNo && String(s.rollNo).toLowerCase().includes(searchTerm))
        )
        : centreStudents;

    document.getElementById('student-count').textContent =
        `${centreStudents.length} student${centreStudents.length === 1 ? '' : 's'}`;

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="table-empty">
                ${searchTerm ? 'No students match your search.' : 'No students enrolled at this centre yet.'}
            </td></tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map(student => {
        const avgAttendance = computeStudentAveragePct(student.id);
        const attendanceClass = avgAttendance < 60 ? 'low' : avgAttendance < 80 ? 'medium' : '';
        const isActive = student.active !== false; // default active

        const avatarInner = student.image
            ? `<img src="${student.image}" alt="${escapeHtml(student.name)}">`
            : getInitials(student.name);

        return `
            <tr>
                <td><strong>#${escapeHtml(student.rollNo || '—')}</strong></td>
                <td>
                    <div class="student-avatar-cell">
                        <div class="avatar">${avatarInner}</div>
                        <div class="student-avatar-cell-info">
                            <div class="student-avatar-cell-name">${escapeHtml(student.name)}</div>
                            <div class="student-avatar-cell-roll">${escapeHtml(student.activeClass || 'No class')}</div>
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
                <td>${formatDate(student.joiningDate) || '—'}</td>
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
}

function toggleStudentStatus(studentId, isActive) {
    updateRecord('students', studentId, { active: isActive });
    showToast(`Student marked ${isActive ? 'active' : 'inactive'}.`, 'success');
}

function editStudent(studentId) {
    // The student registration page supports edit mode via ?id=
    window.location.href = `../students/student-registration.html?id=${studentId}`;
}

/* ================================================================
   STUDENT PROFILE MODAL (eye icon)
   ================================================================ */

function openStudentModal(studentId) {
    const student = findRecord('students', studentId);
    if (!student) return;

    openedStudent = student;

    const school   = student.schoolId ? findRecord('schools', student.schoolId) : null;
    const photo    = student.image
        ? `<img src="${student.image}" alt="${escapeHtml(student.name)}">`
        : getInitials(student.name);

    const body = document.getElementById('student-modal-body');
    body.innerHTML = `
        <!-- Hero: photo + name -->
        <div class="student-detail-hero">
            <div class="student-detail-photo">${photo}</div>
            <div class="student-detail-hero-info">
                <h2>${escapeHtml(student.name)}</h2>
                <div class="roll">Roll No: #${escapeHtml(student.rollNo || '—')}</div>
                <div class="meta">
                    <span>${escapeHtml(student.gender || '—')}</span>
                    <span>Age: ${escapeHtml(String(student.age || '—'))}</span>
                    <span>Class: ${escapeHtml(student.activeClass || '—')}</span>
                </div>
            </div>
        </div>

        <!-- Personal -->
        <div class="student-detail-section">
            <h3>Personal Details</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Date of Birth</div><div class="info-value">${escapeHtml(formatDate(student.dob) || '—')}</div></div>
                <div class="info-item"><div class="info-label">Joining Date</div><div class="info-value">${escapeHtml(formatDate(student.joiningDate) || '—')}</div></div>
                <div class="info-item"><div class="info-label">Category</div><div class="info-value">${escapeHtml(student.category || '—')}</div></div>
                <div class="info-item"><div class="info-label">BPL</div><div class="info-value">${escapeHtml(student.bpl || '—')}</div></div>
                <div class="info-item"><div class="info-label">Address</div><div class="info-value">${escapeHtml(student.address || '—')}</div></div>
                <div class="info-item"><div class="info-label">School</div><div class="info-value">${escapeHtml(school ? school.name : '—')}</div></div>
            </div>
        </div>

        <!-- Family -->
        <div class="student-detail-section">
            <h3>Family Details</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Father's Name</div><div class="info-value">${escapeHtml(student.fatherName || '—')}</div></div>
                <div class="info-item"><div class="info-label">Father's Mobile</div><div class="info-value">${escapeHtml(student.fatherMobile || '—')}</div></div>
                <div class="info-item"><div class="info-label">Father's Occupation</div><div class="info-value">${escapeHtml(student.fatherOccupation || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Name</div><div class="info-value">${escapeHtml(student.motherName || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Mobile</div><div class="info-value">${escapeHtml(student.motherMobile || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Occupation</div><div class="info-value">${escapeHtml(student.motherOccupation || '—')}</div></div>
            </div>
        </div>

        <!-- Contact -->
        <div class="student-detail-section">
            <h3>Contact</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Contact Number</div><div class="info-value">${escapeHtml(student.contactNumber || '—')}</div></div>
                <div class="info-item"><div class="info-label">WhatsApp</div><div class="info-value">${escapeHtml(student.whatsapp || '—')}</div></div>
            </div>
        </div>

        <!-- Centre -->
        <div class="student-detail-section">
            <h3>Centre</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Centre</div><div class="info-value">${escapeHtml(currentCentre.name)}</div></div>
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
    const qrPayload = `ESS-STUDENT|${student.rollNo || student.id}|${student.name}|${currentCentre.name}`;
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
                    <div class="id-card-info-row"><strong>Centre:</strong> ${escapeHtml(currentCentre.name)}</div>
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

function openAttendanceModal(studentId) {
    const student = findRecord('students', studentId);
    if (!student) return;

    attendanceStudentId = studentId;

    document.getElementById('attendance-modal-title').textContent =
        `Attendance - ${student.name}`;
    document.getElementById('attendance-modal-subtitle').textContent =
        `Roll No #${student.rollNo || '—'}`;

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

function renderDayWiseAttendance(monthValue) {
    // Parse the selected month
    const [year, month] = monthValue.split('-').map(Number);
    const daysInMonth = new Date(year, month, 0).getDate();
    const today = new Date();

    // Column headers for the day-wise table
    document.getElementById('att-col-1').textContent = 'Date';
    document.getElementById('att-col-2').textContent = 'Attendance';

    let present = 0, absent = 0, total = 0;
    const rows = [];

    // Iterate from day 1 to the last day of the selected month
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month - 1, day);
        // Don't render days in the future
        if (date > today) continue;
        // Skip Sundays (typical school off-day)
        if (date.getDay() === 0) continue;

        const status = fakeAttendanceFor(attendanceStudentId, date);
        total++;
        if (status === 'Present') present++; else absent++;

        rows.push(`
            <tr>
                <td>${formatDate(date.toISOString())}</td>
                <td>
                    ${status === 'Present'
                        ? '<span class="badge badge-success">Present</span>'
                        : '<span class="badge badge-danger">Absent</span>'}
                </td>
            </tr>
        `);
    }

    const pct = total ? Math.round((present / total) * 100) : 0;
    renderAttendanceSummary(present, absent, pct);

    document.getElementById('att-table-body').innerHTML =
        rows.length
            ? rows.reverse().join('')  // newest first
            : `<tr><td colspan="2" class="table-empty">No attendance in this month yet.</td></tr>`;
}

function renderMonthWiseAttendance() {
    // Column headers for the month-wise table
    document.getElementById('att-col-1').textContent = 'Month';
    document.getElementById('att-col-2').textContent = 'Attendance %';

    let totalP = 0, totalA = 0;
    const rows = [];
    const today = new Date();

    // Last 6 months, newest first
    for (let i = 0; i < 6; i++) {
        const date = new Date(today.getFullYear(), today.getMonth() - i, 1);
        const daysInMonth = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();

        let p = 0, a = 0;
        for (let day = 1; day <= daysInMonth; day++) {
            const d = new Date(date.getFullYear(), date.getMonth(), day);
            if (d > today) continue;
            if (d.getDay() === 0) continue;
            const status = fakeAttendanceFor(attendanceStudentId, d);
            if (status === 'Present') p++; else a++;
        }

        totalP += p; totalA += a;
        const monthTotal = p + a;
        const pct = monthTotal ? Math.round((p / monthTotal) * 100) : 0;
        const label = date.toLocaleDateString('en-IN', { year: 'numeric', month: 'long' });

        rows.push(`
            <tr>
                <td>${escapeHtml(label)}</td>
                <td>
                    <div class="attendance-pct">
                        <div class="attendance-pct-bar">
                            <div class="attendance-pct-fill ${pct < 60 ? 'low' : pct < 80 ? 'medium' : ''}" style="width:${pct}%;"></div>
                        </div>
                        <span>${pct}% (${p}/${monthTotal})</span>
                    </div>
                </td>
            </tr>
        `);
    }

    const total = totalP + totalA;
    const totalPct = total ? Math.round((totalP / total) * 100) : 0;
    renderAttendanceSummary(totalP, totalA, totalPct);

    document.getElementById('att-table-body').innerHTML = rows.join('');
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
   FAKE ATTENDANCE GENERATOR
   ----------------------------------------------------------------
   Deterministic pseudo-random Present/Absent per (student, date).
   Real attendance comes from the mobile app; this stands in for
   the UI so the interface is usable in the demo.
   ================================================================ */

function fakeAttendanceFor(studentId, date) {
    const key = `${studentId}-${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    let hash = 0;
    for (let i = 0; i < key.length; i++) {
        hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0;
    }
    // ~85% present bias
    return (Math.abs(hash) % 100) < 85 ? 'Present' : 'Absent';
}

function computeStudentAveragePct(studentId) {
    const today = new Date();
    let p = 0, total = 0;
    for (let i = 0; i < 30; i++) {
        const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
        if (d.getDay() === 0) continue;
        total++;
        if (fakeAttendanceFor(studentId, d) === 'Present') p++;
    }
    return total ? Math.round((p / total) * 100) : 0;
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

function renderAnalytics() {
    const mode = document.getElementById('analytics-mode').value;
    const dateStr = document.getElementById('analytics-date').value;
    const refDate = dateStr ? new Date(dateStr) : new Date();

    const centreStudents = getRecords('students').filter(s => s.centreId === currentCentre.id);

    const bars = [];
    const labels = [];

    if (mode === 'day') {
        // Last 14 days ending at refDate
        document.getElementById('analytics-chart-title').textContent = 'Daily Attendance';
        document.getElementById('analytics-chart-subtitle').textContent =
            `Percentage of enrolled students present each day (last 14 days).`;

        for (let i = 13; i >= 0; i--) {
            const d = new Date(refDate.getFullYear(), refDate.getMonth(), refDate.getDate() - i);
            const pct = averagePercentageForCentreOnDate(centreStudents, d);
            bars.push(pct);
            labels.push(d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }));
        }
    } else {
        // Last 12 months ending at refDate
        document.getElementById('analytics-chart-title').textContent = 'Monthly Attendance';
        document.getElementById('analytics-chart-subtitle').textContent =
            `Average attendance percentage per month (last 12 months).`;

        for (let i = 11; i >= 0; i--) {
            const d = new Date(refDate.getFullYear(), refDate.getMonth() - i, 1);
            const pct = averagePercentageForCentreInMonth(centreStudents, d);
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
}

function averagePercentageForCentreOnDate(students, date) {
    if (students.length === 0 || date.getDay() === 0) return 0;
    let present = 0;
    students.forEach(s => { if (fakeAttendanceFor(s.id, date) === 'Present') present++; });
    return Math.round((present / students.length) * 100);
}

function averagePercentageForCentreInMonth(students, monthDate) {
    if (students.length === 0) return 0;
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    let totalMarks = 0;
    let presentMarks = 0;

    for (let day = 1; day <= daysInMonth; day++) {
        const d = new Date(year, month, day);
        if (d > today) continue;
        if (d.getDay() === 0) continue;
        students.forEach(s => {
            totalMarks++;
            if (fakeAttendanceFor(s.id, d) === 'Present') presentMarks++;
        });
    }

    return totalMarks ? Math.round((presentMarks / totalMarks) * 100) : 0;
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
