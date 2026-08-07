/* ================================================================
   EK SE SRESHTHA - STUDENT LIST SCRIPT
   ----------------------------------------------------------------
   Global list view of every registered student. Provides:
   - Filter by educational centre (via location cascade)
   - Free-text search on name / roll no / father's name
   - Active/inactive status toggle per row
   - Edit (opens student-registration in edit mode)
   - View profile popup
   - Delete
   ================================================================ */

window.__STUDENT_LIST_LOADED__ = true;

/* ================================================================
   STATE
   ================================================================ */

const state = {
    page: 1,
    pageSize: AppConfig.pageSize,
    search: '',
    districtId: null,
    vsId: null,
    panchayatId: null,
    villageId: null,
    loading: false
};

/* ================================================================
   LOCATION FILTER COMPONENT (inline)
   ----------------------------------------------------------------
   Cascading filter: District -> Vidhan Sabha -> Panchayat -> Village
   ================================================================ */

const locationCache = {
    districts: null,
    vidhanSabhas: {},
    panchayats: {},
    villages: {}
};

async function fetchDistricts() {
    try {
        return await fetchDistrictsForDropdown(true);
    } catch (e) {
        console.error('Failed to fetch districts:', e);
        return [];
    }
}

async function fetchVidhanSabhas(districtId) {
    if (!districtId) return [];
    try {
        return await fetchVidhanSabhasForDropdown(districtId, true);
    } catch (e) {
        console.error('Failed to fetch vidhan sabhas:', e);
        return [];
    }
}

async function fetchPanchayats(vidhanSabhaId) {
    if (!vidhanSabhaId) return [];
    try {
        return await fetchPanchayatsForDropdown(vidhanSabhaId, true);
    } catch (e) {
        console.error('Failed to fetch panchayats:', e);
        return [];
    }
}

async function fetchVillages(panchayatId) {
    if (!panchayatId) return [];
    try {
        return await fetchVillagesForDropdown(panchayatId, true);
    } catch (e) {
        console.error('Failed to fetch villages:', e);
        return [];
    }
}

function initLocationFilter(onChange) {
    const districtSel  = document.getElementById('filter-district');
    const vsSel        = document.getElementById('filter-vs');
    const panchayatSel = document.getElementById('filter-panchayat');
    const villageSel   = document.getElementById('filter-village');

    if (!districtSel) return; // Page has no filter bar

    // Initialize Select2 on filter dropdowns
    initSelect2(districtSel, { placeholder: 'All Districts' });
    initSelect2(vsSel, { placeholder: 'All Vidhan Sabhas' });
    initSelect2(panchayatSel, { placeholder: 'All Panchayats' });
    initSelect2(villageSel, { placeholder: 'All Villages' });

    // Load districts from API
    loadDistricts();
    resetFilterSelect(vsSel, 'All Vidhan Sabhas');
    resetFilterSelect(panchayatSel, 'All Panchayats');
    resetFilterSelect(villageSel, 'All Villages');

    /* District change -> repopulate VS, clear the two below */
    districtSel.addEventListener('change', async () => {
        console.log('District changed:', districtSel.value);
        const districtId = districtSel.value;
        if (districtId) {
            const vsList = await fetchVidhanSabhas(districtId);
            console.log('Got VS list:', vsList);
            locationCache.vidhanSabhas[districtId] = vsList;
            fillFilterSelect(vsSel, vsList, 'All Vidhan Sabhas');
        } else {
            // If no district selected, clear VS and below
            resetFilterSelect(vsSel, 'All Vidhan Sabhas');
            resetFilterSelect(panchayatSel, 'All Panchayats');
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Vidhan Sabha change -> repopulate Panchayat, clear Village */
    vsSel.addEventListener('change', async () => {
        console.log('VS changed:', vsSel.value);
        const vsId = vsSel.value;
        if (vsId) {
            const pList = await fetchPanchayats(vsId);
            console.log('Got panchayat list:', pList);
            locationCache.panchayats[vsId] = pList;
            fillFilterSelect(panchayatSel, pList, 'All Panchayats');
        } else {
            resetFilterSelect(panchayatSel, 'All Panchayats');
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Panchayat change -> repopulate Village */
    panchayatSel.addEventListener('change', async () => {
        console.log('Panchayat changed:', panchayatSel.value);
        const pId = panchayatSel.value;
        if (pId) {
            const vList = await fetchVillages(pId);
            console.log('Got village list:', vList);
            locationCache.villages[pId] = vList;
            fillFilterSelect(villageSel, vList, 'All Villages');
        } else {
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Village change -> just re-render */
    villageSel.addEventListener('change', () => {
        if (onChange) onChange();
    });
}

async function loadDistricts() {
    const districtSel = document.getElementById('filter-district');
    if (!districtSel) {
        console.error('filter-district element not found');
        return;
    }
    
    if (locationCache.districts) {
        fillFilterSelect(districtSel, locationCache.districts, 'All Districts');
        return;
    }
    
    try {
        const districts = await fetchDistricts();
        locationCache.districts = districts;
        fillFilterSelect(districtSel, districts, 'All Districts');
    } catch (e) {
        console.error('loadDistricts error:', e);
    }
}

/* Replace a select's options with a placeholder + record list. */
function fillFilterSelect(select, records, placeholder) {
    if (!select) return;
    select.innerHTML = `<option value="">${placeholder}</option>` +
        records.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');
    select.value = '';
    // Refresh Select2 to pick up new options
    if ($.fn.select2 && $(select).data('select2')) {
        $(select).select2('destroy');
        initSelect2(select, { placeholder });
    }
}

/* Clear a select down to only its placeholder option. */
function resetFilterSelect(select, placeholder) {
    if (!select) return;
    select.innerHTML = `<option value="">${placeholder}</option>`;
    select.value = '';
    // Refresh Select2
    if ($.fn.select2 && $(select).data('select2')) {
        $(select).select2('destroy');
        initSelect2(select, { placeholder });
    }
}

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    initLocationFilter(updateFilters);
    bindEvents();
    renderStudentListTable();
});

/* ================================================================
   EVENT BINDINGS
   ================================================================ */

function bindEvents() {
    // Search input
    const searchInput = document.getElementById('student-search');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                state.page = 1;
                state.search = searchInput.value.trim().toLowerCase();
                renderStudentListTable();
            }, 300);
        });
    }

    // Location filter changes are handled by initLocationFilter
}

/* ================================================================
   LOCATION FILTER CALLBACK
   Updates state from dropdowns and re-renders table
   ================================================================ */

function updateFilters() {
    state.districtId = document.getElementById('filter-district')?.value || '';
    state.vsId = document.getElementById('filter-vs')?.value || '';
    state.panchayatId = document.getElementById('filter-panchayat')?.value || '';
    state.villageId = document.getElementById('filter-village')?.value || '';
    state.page = 1;
    renderStudentListTable();
}

/* ================================================================
   RENDER TABLE
   ================================================================ */

async function renderStudentListTable() {
    const tbody = document.getElementById('student-table-body');
    if (!tbody) return;

    showGlobalLoader();
    try {
        const params = {
            page: state.page,
            page_size: state.pageSize
        };

        // Add location filters
        if (state.districtId) params.district_id = state.districtId;
        if (state.vsId) params.vidhan_sabha_id = state.vsId;
        if (state.panchayatId) params.panchayat_id = state.panchayatId;
        if (state.villageId) params.village_id = state.villageId;
        if (state.search) params.search = state.search;

        const data = await fetchStudents(params);
        const students = data.results || [];

        // Update count badge
        const countEl = document.getElementById('student-count');
        if (countEl) {
            const hasFilters = state.search ||
                state.districtId || state.vsId || state.panchayatId || state.villageId;
            countEl.textContent = hasFilters
                ? `${students.length} / ${data.count} students`
                : `${data.count} student${data.count === 1 ? '' : 's'}`;
        }

        // Empty state
        if (students.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="7" class="table-empty">
                    ${state.search || state.districtId || state.vsId || state.panchayatId || state.villageId
                        ? 'No students match your filters.'
                        : 'No students registered yet. Use "Add Student" to add one.'}
                </td></tr>
            `;
            renderPagination({
                currentPage: data.page || 1,
                pageSize: data.page_size || state.pageSize,
                totalItems: data.count || 0,
                containerSelector: '#student-pagination',
                onPageChange: goToPage
            });
            return;
        }

        // Render rows
        tbody.innerHTML = students.map(student => renderStudentRow(student)).join('');

        // Render pagination
        renderPagination({
            currentPage: data.page || 1,
            pageSize: data.page_size || state.pageSize,
            totalItems: data.count || 0,
            containerSelector: '#student-pagination',
            onPageChange: goToPage
        });

    } catch (error) {
        console.error('Failed to load students:', error);
        tbody.innerHTML = `<tr><td colspan="7" class="table-empty">Failed to load students: ${escapeHtml(error.message)}</td></tr>`;
        showToast('Failed to load students', 'danger');
    } finally {
        hideGlobalLoader();
    }
}

function renderStudentRow(student) {
    // Handle status that may be boolean, int, or string
    const statusVal = student.status;
    const isActive = statusVal === true || statusVal === 1 || statusVal === '1';
    const profileImage = student.image;
    // API now returns full /media/ URL
    const avatarInner = profileImage
        ? `<img src="${escapeHtml(profileImage)}" alt="${escapeHtml(student.full_name)}">`
        : getInitials(student.full_name);

    const centreName = student.center_name || 'Unassigned';
    const contact = student.contact || student.phone_number || '—';

    return `
        <tr data-id="${student.id}">
            <td><strong>#${escapeHtml(student.roll_number || '')}</strong></td>
            <td>
                <div class="student-avatar-cell">
                    <div class="avatar">${avatarInner}</div>
                    <div class="student-avatar-cell-info">
                        <div class="student-avatar-cell-name">${escapeHtml(student.full_name)}</div>
                        <div class="student-avatar-cell-roll">
                            ${escapeHtml(student.gender || '')}
                            ${student.age ? ', ' + student.age + ' yrs' : ''}
                        </div>
                    </div>
                </div>
            </td>
            <td>${escapeHtml(student.grade || student.active_class || '—')}</td>
            <td>${escapeHtml(centreName)}</td>
            <td>${escapeHtml(contact)}</td>
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
                            onclick="window.location.href='${getUrl('student-registration')}?id=${student.id}'">
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
}

/* ================================================================
   ROW ACTIONS
   ================================================================ */

async function toggleStudentActive(studentId, isActive) {
    try {
        showGlobalLoader();
        const response = await toggleStudentStatus(studentId, isActive ? 1 : 0);
        showToast(`Student marked ${isActive ? 'active' : 'inactive'}.`, 'success');
        // Use the updated student data from response to immediately update UI
        if (response && response.data) {
            updateStudentInTable(response.data);
        } else {
            // Fallback: refresh table with cache-busting
            renderStudentListTable();
        }
    } catch (error) {
        console.error('Toggle student status failed:', error);
        showToast('Failed to update status: ' + error.message, 'danger');
        renderStudentListTable(); // Re-render to revert UI
    } finally {
        hideGlobalLoader();
    }
}

async function deleteStudentRow(studentId) {
    // Find student name for confirmation
    let studentName = 'this student';
    try {
        const student = await fetchStudentById(studentId);
        studentName = student.full_name || student.name || 'this student';
    } catch (e) {
        // Ignore, use default name
    }

    if (!confirm(`Delete student "${studentName}"? This cannot be undone.`)) return;

    try {
        showGlobalLoader();
        await deleteStudent(studentId);
        showToast('Student deleted.', 'success');
        renderStudentListTable();
    } catch (error) {
        console.error('Delete student failed:', error);
        showToast('Failed to delete student: ' + error.message, 'danger');
    } finally {
        hideGlobalLoader();
    }
}

/* ================================================================
   PAGINATION
   ================================================================ */

function goToPage(page) {
    state.page = page;
    renderStudentListTable();
}

/* ================================================================
   STUDENT PROFILE MODAL
   ================================================================ */

async function openStudentProfile(studentId) {
    showGlobalLoader();
    try {
        const student = await fetchStudentById(studentId);
        if (!student) {
            showToast('Student not found', 'danger');
            hideGlobalLoader();
            return;
        }

        // Student API already returns center_name, school_name, bpl, category,
        // district_name, vidhan_sabha_name, panchayat_name, village_name
        // And center's interconnected location: center_district_name, center_vidhan_sabha_name,
        // center_panchayat_name, center_village_name, center_address
        // No need for separate API calls
        const centreName = student.center_name || 'Unassigned';
        const schoolName = student.school_name || '—';
        const bplValue = student.bpl === true || student.bpl === 'true' || student.bpl === 1 || student.bpl === '1' ? 'Yes' : (student.bpl === false || student.bpl === 'false' || student.bpl === 0 || student.bpl === '0' ? 'No' : '—');
        const category = student.category || '—';

        // Use center's interconnected location hierarchy (District -> VS -> Panchayat -> Village)
        const centreDistrict = student.center_district_name || student.district_name || '—';
        const centreVS = student.center_vidhan_sabha_name || student.vidhan_sabha_name || '—';
        const centrePanchayat = student.center_panchayat_name || student.panchayat_name || '—';
        const centreVillage = student.center_village_name || student.village_name || '—';
        const centreAddress = student.center_address || '—';

        const profileImage = student.image;
        const imageUrl = profileImage && (profileImage.startsWith('http') || profileImage.startsWith('/media/') || profileImage.startsWith('data:'))
            ? profileImage
            : (profileImage ? '/media/' + profileImage : '');
        const photo = imageUrl
            ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(student.full_name)}">`
            : getInitials(student.full_name);

        document.getElementById('student-modal-body').innerHTML = `
            <div class="student-detail-hero">
                <div class="student-detail-photo">${photo}</div>
                <div class="student-detail-hero-info">
                    <h2>${escapeHtml(student.full_name)}</h2>
                    <div class="roll">Roll No: #${escapeHtml(student.roll_number || '')}</div>
                    <div class="meta">
                        <span>${escapeHtml(student.gender || '—')}</span>
                        <span>Age: ${escapeHtml(String(student.age || '—'))}</span>
                        <span>Class: ${escapeHtml(student.grade || student.active_class || '—')}</span>
                    </div>
                </div>
            </div>

            <div class="student-detail-section">
                <h3>Personal Details</h3>
                <div class="info-grid">
                    <div class="info-item"><div class="info-label">Date of Birth</div><div class="info-value">${escapeHtml(formatDate(student.date_of_birth) || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Joining Date</div><div class="info-value">${escapeHtml(formatDate(student.joining_date) || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Category</div><div class="info-value">${escapeHtml(category)}</div></div>
                    <div class="info-item"><div class="info-label">BPL</div><div class="info-value">${escapeHtml(bplValue)}</div></div>
                    <div class="info-item"><div class="info-label">Address</div><div class="info-value">${escapeHtml(student.full_address || student.address || '—')}</div></div>
                    <div class="info-item"><div class="info-label">School</div><div class="info-value">${escapeHtml(schoolName)}</div></div>
                </div>
            </div>

            <div class="student-detail-section">
                <h3>Family Details</h3>
                <div class="info-grid">
                    <div class="info-item"><div class="info-label">Father's Name</div><div class="info-value">${escapeHtml(student.father_name || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Father's Mobile</div><div class="info-value">${escapeHtml(student.father_mobile_number || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Mother's Name</div><div class="info-value">${escapeHtml(student.mother_name || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Mother's Mobile</div><div class="info-value">${escapeHtml(student.mother_mobile_number || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Father's Occupation</div><div class="info-value">${escapeHtml(student.father_occupation || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Mother's Occupation</div><div class="info-value">${escapeHtml(student.mother_occupation || '—')}</div></div>
                </div>
            </div>

            <div class="student-detail-section">
                <h3>Centre & Location</h3>
                <div class="info-grid">
                    <div class="info-item"><div class="info-label">Centre</div><div class="info-value">${escapeHtml(centreName)}</div></div>
                    <div class="info-item"><div class="info-label">Teacher</div><div class="info-value">${escapeHtml(student.center_teacher_name || '—')}</div></div>
                    <div class="info-item"><div class="info-label">Regional Admin</div><div class="info-value">${escapeHtml(student.center_regional_admin_name || '—')}</div></div>
                </div>
            </div>
        `;

        openModal('student-profile-modal');
    } catch (error) {
        console.error('Failed to load student profile:', error);
        showToast('Failed to load student profile', 'danger');
    } finally {
        hideGlobalLoader();
    }
}

function closeStudentProfile(event) {
    if (event && event.target.id !== 'student-modal' && event.type === 'click') return;
    closeModal('student-modal');
}

/* ================================================================
   STUDENT API FUNCTIONS
   ================================================================ */

/**
 * Fetch all students with pagination and filters
 */
async function fetchStudents(params = {}) {
    const query = new URLSearchParams(params).toString();
    return apiFetch(getUrl('students') + '?' + query);
}

/**
 * Fetch single student by ID
 */
async function fetchStudentById(id) {
    return apiFetch(getUrl('students') + '?id=' + id);
}

/**
 * Toggle student active/inactive status
 */
async function toggleStudentStatus(id, status) {
    return apiFetch(getUrl('students'), {
        method: 'PUT',
        body: JSON.stringify({ id: id, status: status })
    });
}

/**
 * Update a single student row in the table with new data
 */
function updateStudentInTable(student) {
    const row = document.querySelector(`#student-table-body tr[data-id='${student.id}']`);
    if (!row) return;
    
    // Handle status that may be boolean, int, or string
    const statusVal = student.status;
    const isActive = statusVal === true || statusVal === 1 || statusVal === '1';
    
    // Update the toggle checkbox
    const toggle = row.querySelector('input[type="checkbox"]');
    if (toggle) {
        toggle.checked = isActive;
    }
    
    // Update status badge if present
    const statusBadge = row.querySelector('.status-badge');
    if (statusBadge) {
        statusBadge.textContent = isActive ? 'Active' : 'Inactive';
        statusBadge.className = 'status-badge ' + (isActive ? 'status-active' : 'status-inactive');
    }
}

/**
 * Delete student
 */
async function deleteStudent(id) {
    return apiFetch(getUrl('students') + '?id=' + id, {
        method: 'DELETE'
    });
}

/**
 * Fetch a record by type and ID (for centre, school, teacher, admin)
 */
async function fetchRecord(type, id) {
    const urlMap = {
        'centres': 'centres',
        'schools': 'school-dropdown-list',
        'teachers': 'teacher',
        'regional-admins': 'regional-admin'
    };
    const endpoint = urlMap[type] || type;
    return apiFetch(getUrl(endpoint) + '?id=' + id);
}