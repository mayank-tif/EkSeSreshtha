/* ================================================================
   EK SE SRESHTHA - STUDENT LIST SCRIPT
   ----------------------------------------------------------------
   Global list view of every registered student. Provides:
   - Filter by educational centre
   - Free-text search on name / roll no / father's name
   - Active/inactive status toggle per row
   - Edit (opens student-registration in edit mode)
   - View profile popup
   - Delete
   ================================================================ */

renderShell({
    title: 'Student Registration',
    active: 'student-registration',
    breadcrumbs: [
        { label: 'Students' },
        { label: 'Student Registration' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    // Cascading District -> VS -> Panchayat -> Village filter.
    // Every change re-renders the table (and the live count).
    initLocationFilter(renderStudentListTable);
    renderStudentListTable();
});

/* ================================================================
   RENDER TABLE
   ================================================================ */

function renderStudentListTable() {
    const tbody = document.getElementById('student-table-body');
    const searchTerm = document.getElementById('student-search').value.trim().toLowerCase();

    const students = getRecords('students');
    const centres = getRecords('centres');
    const centreMap = Object.fromEntries(centres.map(c => [c.id, c]));

    // ------------------------------------------------------------
    // Filter chain:
    //   1. Location cascade (students inherit location via centre)
    //   2. Free-text search
    // ------------------------------------------------------------
    const locFilter = getLocationFilter();
    let filtered = students;

    if (locFilter.districtId || locFilter.vsId || locFilter.panchayatId || locFilter.villageId) {
        filtered = filtered.filter(s => {
            const centre = centreMap[s.centreId];
            return centre ? matchesLocationFilter(centre, locFilter) : false;
        });
    }
    if (searchTerm) {
        filtered = filtered.filter(s =>
            (s.name && s.name.toLowerCase().includes(searchTerm)) ||
            (s.rollNo && String(s.rollNo).toLowerCase().includes(searchTerm)) ||
            (s.fatherName && s.fatherName.toLowerCase().includes(searchTerm))
        );
    }

    // Live count badge on the right of the filter row
    const anyFilter = searchTerm ||
        locFilter.districtId || locFilter.vsId || locFilter.panchayatId || locFilter.villageId;
    document.getElementById('student-count').textContent = anyFilter
        ? `${filtered.length} / ${students.length} students`
        : `${students.length} student${students.length === 1 ? '' : 's'}`;

    // Empty state
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="7" class="table-empty">
                ${anyFilter
                    ? 'No students match your filters.'
                    : 'No students registered yet. Use "Register Student" to add one.'}
            </td></tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map(student => {
        const isActive = student.active !== false;
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
                            <div class="student-avatar-cell-roll">${escapeHtml(student.gender || '')}${student.age ? ', ' + student.age + ' yrs' : ''}</div>
                        </div>
                    </div>
                </td>
                <td>${escapeHtml(student.activeClass || '—')}</td>
                <td>${escapeHtml(centreMap[student.centreId] ? centreMap[student.centreId].name : 'Unassigned')}</td>
                <td>${escapeHtml(student.contactNumber || '—')}</td>
                <td>
                    <label class="toggle">
                        <input type="checkbox" ${isActive ? 'checked' : ''}
                               onchange="toggleStudentActive('${student.id}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="btn-icon" title="View Profile"
                                onclick="openStudentProfile('${student.id}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                        </button>
                        <button class="btn-icon" title="Edit"
                                onclick="window.location.href='student-registration.html?id=${student.id}'">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                            </svg>
                        </button>
                        <button class="btn-icon btn-icon-danger" title="Delete"
                                onclick="deleteStudentRow('${student.id}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                                 stroke="currentColor" stroke-width="2"
                                 stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/* ================================================================
   ROW ACTIONS
   ================================================================ */

function toggleStudentActive(studentId, isActive) {
    updateRecord('students', studentId, { active: isActive });
    showToast(`Student marked ${isActive ? 'active' : 'inactive'}.`, 'success');
}

function deleteStudentRow(studentId) {
    const student = findRecord('students', studentId);
    if (!student) return;
    if (!confirm(`Delete student "${student.name}"? This cannot be undone.`)) return;
    deleteRecord('students', studentId);
    showToast('Student deleted.', 'success');
    renderStudentListTable();
}

/* ================================================================
   STUDENT PROFILE MODAL
   Same layout used on the attendance detail page.
   ================================================================ */

function openStudentProfile(studentId) {
    const student = findRecord('students', studentId);
    if (!student) return;

    const centre  = student.centreId ? findRecord('centres', student.centreId) : null;
    const school  = student.schoolId ? findRecord('schools', student.schoolId) : null;
    const teacher = centre && centre.teacherId ? findRecord('teachers', centre.teacherId) : null;
    const admin   = centre && centre.regionalAdminId ? findRecord('regionalAdmins', centre.regionalAdminId) : null;

    const photo = student.image
        ? `<img src="${student.image}" alt="${escapeHtml(student.name)}">`
        : getInitials(student.name);

    document.getElementById('student-modal-body').innerHTML = `
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

        <div class="student-detail-section">
            <h3>Family Details</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Father's Name</div><div class="info-value">${escapeHtml(student.fatherName || '—')}</div></div>
                <div class="info-item"><div class="info-label">Father's Mobile</div><div class="info-value">${escapeHtml(student.fatherMobile || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Name</div><div class="info-value">${escapeHtml(student.motherName || '—')}</div></div>
                <div class="info-item"><div class="info-label">Mother's Mobile</div><div class="info-value">${escapeHtml(student.motherMobile || '—')}</div></div>
            </div>
        </div>

        <div class="student-detail-section">
            <h3>Centre</h3>
            <div class="info-grid">
                <div class="info-item"><div class="info-label">Centre</div><div class="info-value">${escapeHtml(centre ? centre.name : 'Unassigned')}</div></div>
                <div class="info-item"><div class="info-label">Teacher</div><div class="info-value">${escapeHtml(teacher ? teacher.name : '—')}</div></div>
                <div class="info-item"><div class="info-label">Regional Admin</div><div class="info-value">${escapeHtml(admin ? admin.name : '—')}</div></div>
            </div>
        </div>
    `;

    openModal('student-modal');
}

function closeStudentProfile(event) {
    if (event && event.target.id !== 'student-modal' && event.type === 'click') return;
    closeModal('student-modal');
}
