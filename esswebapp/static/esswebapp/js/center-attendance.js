/* ================================================================
   EK SE SRESHTHA - CENTER ATTENDANCE (LIST PAGE)
   ----------------------------------------------------------------
   Table list view of every educational centre. Each row shows:
     - Center name + location chain (District > VS > Panchayat > Village)
     - Assigned Teacher
     - Assigned Regional Admin
     - Total number of students
     - Average attendance (with mini progress bar)
   Toolbar: free-text search (left) + cascading location filters
   (right, see location-filter.js) + a live count badge.
   Clicking a row opens center-detail?id=<centreId>.
   ================================================================ */

/* Shared shell */
renderShell({
    title: 'Center Attendance',
    active: 'attendance',
    breadcrumbs: [{ label: 'Center Attendance' }]
});

/* Module state */
let currentPage = 1;
const pageSize = AppConfig.pageSize;
let totalPages = 1;
let totalCount = 0;
let isLoading = false;
let currentAttendanceDate = null;

/* Initialize once DOM is ready. */
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize date picker for attendance date (defaults to today)
    const dateInput = document.getElementById('attendance-date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
        currentAttendanceDate = today;
        dateInput.addEventListener('change', () => {
            currentAttendanceDate = dateInput.value;
            currentPage = 1;
            loadCentres();
        });
    }

    // Cascading District -> VS -> Panchayat -> Village filter;
    // every change re-renders the table and the live count.
    initLocationFilter(loadCentres);

    // Search input
    const searchInput = document.getElementById('centre-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(() => {
            currentPage = 1;
            loadCentres();
        }, 300));
    }

    // Pagination buttons
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadCentres();
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                loadCentres();
            }
        });
    }

    await loadCentres();
});

/* Debounce helper */
function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

/* ================================================================
   LOAD CENTRES FROM API (with pagination)
   ================================================================ */

async function loadCentres() {
    if (isLoading) return;
    isLoading = true;
    showGlobalLoader('Loading centres...');

    try {
        const searchTerm = document.getElementById('centre-search').value.trim();
        const locFilter = getLocationFilter();

        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize
        });
        if (searchTerm) params.set('search', searchTerm);
        if (locFilter.districtId) params.set('district_id', locFilter.districtId);
        if (locFilter.vsId) params.set('vidhan_sabha_id', locFilter.vsId);
        if (locFilter.panchayatId) params.set('panchayat_id', locFilter.panchayatId);
        if (locFilter.villageId) params.set('village_id', locFilter.villageId);
        if (currentAttendanceDate) params.set('date', currentAttendanceDate);

        const url = `${getUrl('attendance')}?${params}`;
        const response = await apiFetch(url);

        const centres = response?.results || [];
        totalCount = response?.count || 0;
        totalPages = response?.total_pages || 1;

        renderCentreTable(centres);
        updatePagination();
        updateCountBadge(searchTerm, locFilter, centres.length);
    } catch (error) {
        console.error('Failed to load centres:', error);
        showToast('Failed to load centres', 'danger');
        renderCentreTable([]);
        updatePagination();
        hideGlobalLoader();
    } finally {
        hideGlobalLoader();
        isLoading = false;
    }
}

/* ================================================================
   RENDER CENTRE TABLE
   ================================================================ */

function renderCentreTable(centres) {
    const tbody = document.getElementById('centre-table-body');

    if (centres.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="table-empty">
                No centres match your filters.
            </td></tr>
        `;
        return;
    }

    tbody.innerHTML = centres.map(centre => {
        const studentCount = centre.student_count || 0;
        const attendancePct = centre.attendance_pct || 0;
        const teacherName = centre.assigned_teacher_name || 'Unassigned';
        const adminName = centre.assigned_regional_admin_name || 'Unassigned';

        // Location chain with graceful fallbacks
        const chainParts = [
            centre.district_name,
            centre.vidhan_sabha_name,
            centre.panchayat_name,
            centre.village_name
        ].map(n => n || '—');

        const barClass = attendancePct < 60 ? 'low' : attendancePct < 80 ? 'medium' : '';

        return `
            <tr class="centre-row" onclick="openCentreDetail('${centre.id}')">
                <td>
                    <div class="centre-row-name">${escapeHtml(centre.center_name)}</div>
                    <div class="centre-row-chain">
                        ${chainParts.map((name, i) => `
                            <span class="centre-row-chain-part">${escapeHtml(name)}</span>
                            ${i < 3 ? '<span class="centre-row-chain-sep">&rsaquo;</span>' : ''}
                        `).join('')}
                    </div>
                </td>
                <td>${escapeHtml(teacherName)}</td>
                <td>${escapeHtml(adminName)}</td>
                <td><span class="count-pill">${studentCount}</span></td>
                <td>
                    <div class="attendance-pct">
                        <div class="attendance-pct-bar">
                            <div class="attendance-pct-fill ${barClass}" style="width:${attendancePct}%;"></div>
                        </div>
                        <span>${attendancePct}%</span>
                    </div>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="btn-icon btn-attendance" title="Attendance"
                                onclick="event.stopPropagation(); openAttendanceModal('${centre.id}', '${escapeHtml(centre.center_name)}')">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" y1="21" x2="19.5" y2="18.5"/><line x1="18" y1="21" x2="15.5" y2="18.5"/></svg>
                        </button>
                        <button class="btn-icon" title="View details"
                                onclick="event.stopPropagation(); openCentreDetail('${centre.id}')">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/* ================================================================
   PAGINATION & COUNT BADGE
   ================================================================ */

function updatePagination() {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const pageNumbers = document.getElementById('page-numbers');
    const paginationStart = document.getElementById('pagination-start');
    const paginationEnd = document.getElementById('pagination-end');
    const paginationTotal = document.getElementById('pagination-total');

    if (prevBtn) prevBtn.disabled = currentPage === 1;
    if (nextBtn) nextBtn.disabled = currentPage === totalPages;

    if (paginationStart) paginationStart.textContent = totalCount ? (currentPage - 1) * pageSize + 1 : 0;
    if (paginationEnd) paginationEnd.textContent = Math.min(currentPage * pageSize, totalCount || 0);
    if (paginationTotal) paginationTotal.textContent = totalCount || 0;

    if (!pageNumbers) return;
    pageNumbers.innerHTML = '';

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) startPage = Math.max(1, endPage - 4);

    if (startPage > 1) {
        addPageBtn(1);
        if (startPage > 2) addEllipsis();
    }

    for (let p = startPage; p <= endPage; p++) {
        addPageBtn(p);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) addEllipsis();
        addPageBtn(totalPages);
    }

    function addPageBtn(pageNum) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `page-btn ${pageNum === currentPage ? 'active' : ''}`;
        btn.textContent = pageNum;
        btn.onclick = () => {
            currentPage = pageNum;
            loadCentres();
        };
        pageNumbers.appendChild(btn);
    }

    function addEllipsis() {
        const span = document.createElement('span');
        span.className = 'page-ellipsis';
        span.textContent = '…';
        pageNumbers.appendChild(span);
    }
}

function updateCountBadge(searchTerm, locFilter, filteredCount) {
    const badge = document.getElementById('centre-count');
    if (!badge) return;

    const anyFilter = searchTerm ||
        locFilter.districtId || locFilter.vsId || locFilter.panchayatId || locFilter.villageId;
    
    badge.textContent = anyFilter
        ? `${filteredCount} / ${totalCount} centres`
        : `${totalCount} centre${totalCount === 1 ? '' : 's'}`;
}

/* ================================================================
   NAVIGATION
   ================================================================ */

function openCentreDetail(centreId) {
    // Use the Django URL pattern name 'center-detail' which maps to /attendance/center-detail/
    window.location.href = `${getUrl('center-detail')}?id=${centreId}`;
}

// Open attendance modal for a center
function openAttendanceModal(centerId, centerName) {
    // Check if modal exists, if not create it
    let modal = document.getElementById('centre-attendance-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'centre-attendance-modal';
        modal.className = 'modal-backdrop';
        modal.innerHTML = `
            <div class="modal modal-xl">
                <div class="modal-header">
                    <h3 class="modal-title" id="attendance-modal-title">Centre Attendance</h3>
                    <button class="modal-close" data-close-modal aria-label="Close">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="modal-body" style="padding: var(--space-4);">
                    <div class="form-group" style="margin-bottom: var(--space-4);">
                        <label class="form-label" for="attendance-date">Select Date</label>
                        <input type="date" id="attendance-date" class="form-input" style="max-width: 250px;">
                    </div>
                    <div class="attendance-summary" style="margin-bottom: var(--space-4); padding: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); display: flex; gap: var(--space-6); font-size: var(--text-sm);">
                        <span id="attendance-present-count" style="color: var(--success); font-weight: 600;">Present: 0</span>
                        <span id="attendance-absent-count" style="color: var(--danger); font-weight: 600;">Absent: 0</span>
                        <span id="attendance-total-count" style="color: var(--gray-700); font-weight: 600;">Total: 0</span>
                    </div>
                    <div class="table-wrapper" style="max-height: 500px; overflow-y: auto;">
                        <table class="table" style="min-width: 600px;">
                            <thead>
                                <tr>
                                    <th style="width: 50px;">#</th>
                                    <th>Student Name</th>
                                    <th>Enrollment No.</th>
                                    <th style="width: 120px;">Status</th>
                                    <th style="width: 150px;">Time</th>
                                </tr>
                            </thead>
                            <tbody id="attendance-student-tbody">
                            </tbody>
                        </table>
                    </div>
                    <div id="attendance-empty" class="empty-state" style="display: none; padding: var(--space-8); text-align: center;">
                        <div class="empty-state-icon">👥</div>
                        <div class="empty-state-title">No students found</div>
                        <div class="empty-state-desc">No active students enrolled in this centre.</div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Bind close button
        modal.querySelector('[data-close-modal]').addEventListener('click', () => {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        });
    }
    
    // Update title
    modal.querySelector('#attendance-modal-title').textContent = `Attendance - ${centerName}`;
    
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    modal.querySelector('#attendance-date').value = today;
    
    // Store center ID for reload
    modal.dataset.centerId = centerId;
    
    // Bind date change
    const dateInput = modal.querySelector('#attendance-date');
    dateInput.onchange = () => loadAttendanceData(centerId, dateInput.value);
    
    // Show modal
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Load data
    loadAttendanceData(centerId, today);
}

async function loadAttendanceData(centerId, date) {
    showGlobalLoader('Loading attendance...');
    try {
        const url = `${getUrl('attendance')}?action=students_attendance&center_id=${centerId}&date=${date}`;
        const data = await apiFetch(url);
        renderAttendanceTable(data);
    } catch (e) {
        console.error('Failed to load attendance:', e);
        showToast('Failed to load attendance', 'error');
        renderAttendanceTable({ students: [] });
    } finally {
        hideGlobalLoader();
    }
}

function renderAttendanceTable(data) {
    const tbody = document.getElementById('attendance-student-tbody');
    const emptyDiv = document.getElementById('attendance-empty');
    const students = data.students || [];
    const classHeld = data.class_held !== false; // default true for backward compat
    
    if (students.length === 0) {
        tbody.innerHTML = '';
        if (emptyDiv) emptyDiv.style.display = 'block';
        updateAttendanceSummary(0, 0, 0, classHeld);
        return;
    }
    
    if (emptyDiv) emptyDiv.style.display = 'none';
    
    // If no class held, show single message row instead of all students
    if (!classHeld) {
        const isCancelled = data.class_cancelled === true;
        const isHoliday = data.is_holiday === true;
        const holidayName = data.holiday_name;
        const reason = data.no_class_reason;
        
        let icon, title, message;
        if (isHoliday || reason === 'holiday') {
            icon = '🎉';
            title = 'Holiday';
            message = holidayName ? `${holidayName} - No class scheduled.` : 'Holiday - No class scheduled.';
        } else if (isCancelled || reason === 'cancelled') {
            icon = '🚫';
            title = 'Class Cancelled';
            message = 'This class was cancelled on this date.';
        } else {
            icon = '📅';
            title = 'No Class Scheduled';
            message = 'No class was conducted on this date (class not started yet).';
        }
        
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: var(--space-8); color: var(--gray-600);">
                    <div style="display: flex; flex-direction: column; align-items: center; gap: var(--space-2);">
                        <span style="font-size: 32px;">${icon}</span>
                        <span style="font-weight: 500; font-size: var(--text-lg);">${title}</span>
                        <span style="font-size: var(--text-sm);">${message}</span>
                    </div>
                </td>
            </tr>
        `;
        updateAttendanceSummary(0, 0, students.length, false, students.length);
        return;
    }
    
    let presentCount = 0;
    let absentCount = 0;
    
    tbody.innerHTML = students.map((student, i) => {
        const isPresent = student.status === 'Present';
        
        if (isPresent) presentCount++;
        else absentCount++;
        
        const statusBadge = isPresent 
            ? '<span class="status-badge" style="background: var(--success-light); color: var(--success);">Present</span>'
            : '<span class="status-badge" style="background: var(--danger-light); color: var(--danger);">Absent</span>';
        
        const timeDisplay = student.attendance_time 
            ? student.attendance_time.substring(0, 5)
            : '—';
        
        return `
            <tr>
                <td class="row-index">${i + 1}</td>
                <td>${escapeHtml(student.name || '')}</td>
                <td>${escapeHtml(student.enrollment_number || '—')}</td>
                <td>${statusBadge}</td>
                <td>${timeDisplay}</td>
            </tr>
        `;
    }).join('');
    
    updateAttendanceSummary(presentCount, absentCount, students.length, true);
}

function updateAttendanceSummary(present, absent, total, classHeld = true, noClassCount = 0, data = {}) {
    const presentEl = document.getElementById('attendance-present-count');
    const absentEl = document.getElementById('attendance-absent-count');
    const totalEl = document.getElementById('attendance-total-count');
    
    presentEl.textContent = `Present: ${present}`;
    
    if (!classHeld) {
        presentEl.style.display = 'none';
        const isHoliday = data.is_holiday === true;
        const holidayName = data.holiday_name;
        const isCancelled = data.class_cancelled === true;
        
        if (isHoliday) {
            absentEl.textContent = holidayName ? `Holiday: ${holidayName}` : 'Holiday';
            absentEl.style.color = 'var(--warning)';
        } else if (isCancelled) {
            absentEl.textContent = 'Class Cancelled';
            absentEl.style.color = 'var(--danger)';
        } else {
            absentEl.textContent = 'No Class Scheduled';
            absentEl.style.color = 'var(--gray-600)';
        }
        totalEl.textContent = '';
    } else {
        presentEl.style.display = '';
        absentEl.textContent = `Absent: ${absent}`;
        absentEl.style.color = 'var(--danger)';
        totalEl.textContent = `Total: ${total}`;
    }
}