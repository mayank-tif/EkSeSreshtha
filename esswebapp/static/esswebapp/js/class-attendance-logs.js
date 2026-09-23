/* ================================================================
   EK SE SRESHTHA - CLASS ATTENDANCE LOGS PAGE SCRIPT
   ---------------------------------------------------------------
   Keka-style class attendance logs with:
   - Date range filter, center filter, teacher filter, status filter
   - Table with teacher, timings, present/absent, location, status
   - Status badges with info tooltips (like Keka)
   - Location link to open Google Maps modal
   - Detail modal with student attendance breakdown
   ================================================================ */

// ── State ─────────────────────────────────────────────────────────
const state = {
    page: 1,
    pageSize: parseInt(document.body.getAttribute('data-page-size')) || 50,
    search: '',
    dateFrom: '',
    dateTo: '',
    centerId: '',
    teacherId: '',
    statusFilter: '',
    totalLogs: 0,
    totalPages: 0,
    currentMap: null,
    currentMapMarker: null
};

// ── DOM References ────────────────────────────────────────────────
const els = {
    get dateFrom() { return document.getElementById('logs-date-from'); },
    get dateTo() { return document.getElementById('logs-date-to'); },
    get centerFilter() { return document.getElementById('logs-center-filter'); },
    get teacherFilter() { return document.getElementById('logs-teacher-filter'); },
    get statusFilter() { return document.getElementById('logs-status-filter'); },
    get search() { return document.getElementById('logs-search'); },
    get tbody() { return document.getElementById('logs-tbody'); },
    get pagination() { return document.getElementById('logs-pagination'); },
    get pageNumbers() { return document.getElementById('logs-page-numbers'); },
    get total() { return document.getElementById('logs-total-logs'); },
    get start() { return document.getElementById('logs-pagination-start'); },
    get end() { return document.getElementById('logs-pagination-end'); },
    get prevPage() { return document.getElementById('logs-prev-page'); },
    get nextPage() { return document.getElementById('logs-next-page'); },
    get mapModal() { return document.getElementById('map-modal'); },
    get mapClassName() { return document.getElementById('map-modal-class-name'); },
    get mapCenterInfo() { return document.getElementById('map-modal-center-info'); },
    get mapCoordinates() { return document.getElementById('map-modal-coordinates'); }
};

// ── Status Config (Keka-style) ────────────────────────────────────
const STATUS_CONFIG = {
    completed: {
        label: 'Completed',
        color: '#16a34a',
        icon: '✓',
        className: 'status-completed'
    },
    completed_no_attendance: {
        label: 'Completed (No Attendance)',
        color: '#f59e0b',
        icon: '⚠',
        className: 'status-completed_no_attendance'
    },
    in_progress: {
        label: 'In Progress',
        color: '#8b5cf6',
        icon: '▶',
        className: 'status-in_progress'
    },
    active_ended: {
        label: 'Ended (Not Closed)',
        color: '#3b82f6',
        icon: '⏱',
        className: 'status-active_ended'
    },
    cancelled: {
        label: 'Cancelled',
        color: '#dc2626',
        icon: '✕',
        className: 'status-cancelled'
    },
    holiday: {
        label: 'Holiday',
        color: '#f59e0b',
        icon: '🎉',
        className: 'status-holiday'
    },
    no_class: {
        label: 'No Class',
        color: '#9ca3af',
        icon: '—',
        className: 'status-no_class'
    },
    unknown: {
        label: 'Unknown',
        color: '#6b7280',
        icon: '?',
        className: ''
    }
};

// ── Init ──────────────────────────────────────────────────────────
async function init() {
    // Set default dates (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(today.getDate() - 30);
    
    if (els.dateFrom) els.dateFrom.value = thirtyDaysAgo.toISOString().split('T')[0];
    if (els.dateTo) els.dateTo.value = today.toISOString().split('T')[0];
    
    state.dateFrom = els.dateFrom?.value || '';
    state.dateTo = els.dateTo?.value || '';
    
    await loadCenterDropdown();
    await loadTeacherDropdown();
    await fetchAndRender();
    bindEvents();
}

// Handle case where DOMContentLoaded already fired
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init().catch(err => console.error('Init error:', err));
}

// ── Event Bindings ────────────────────────────────────────────────
function bindEvents() {
    // Date from
    if (els.dateFrom) {
        els.dateFrom.addEventListener('change', () => {
            state.page = 1;
            state.dateFrom = els.dateFrom.value;
            fetchAndRender();
        });
    }
    
    // Date to
    if (els.dateTo) {
        els.dateTo.addEventListener('change', () => {
            state.page = 1;
            state.dateTo = els.dateTo.value;
            fetchAndRender();
        });
    }
    
    // Center filter
    if (els.centerFilter) {
        els.centerFilter.addEventListener('change', () => {
            state.page = 1;
            state.centerId = els.centerFilter.value;
            fetchAndRender();
        });
    }
    
    // Teacher filter
    if (els.teacherFilter) {
        els.teacherFilter.addEventListener('change', () => {
            state.page = 1;
            state.teacherId = els.teacherFilter.value;
            fetchAndRender();
        });
    }
    
    // Status filter
    if (els.statusFilter) {
        els.statusFilter.addEventListener('change', () => {
            state.page = 1;
            state.statusFilter = els.statusFilter.value;
            fetchAndRender();
        });
    }
    
    // Search with debounce
    if (els.search) {
        let debounceTimer;
        els.search.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                state.page = 1;
                state.search = els.search.value.trim().toLowerCase();
                fetchAndRender();
            }, 300);
        });
    }
    
    // Pagination
    if (els.prevPage) {
        els.prevPage.addEventListener('click', () => {
            if (state.page > 1) {
                state.page--;
                fetchAndRender();
            }
        });
    }
    
    if (els.nextPage) {
        els.nextPage.addEventListener('click', () => {
            if (state.page < state.totalPages) {
                state.page++;
                fetchAndRender();
            }
        });
    }
    
    // Modal close buttons
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal-backdrop');
            if (modal) closeModal(modal);
        });
    });
    
    // Click outside modal to close
    document.querySelectorAll('.modal-backdrop').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal(modal);
        });
    });
}

// ── Data Fetching ─────────────────────────────────────────────────
async function fetchAndRender() {
    showGlobalLoader();
    try {
        const params = new URLSearchParams({
            action: 'class_logs',
            page: state.page,
            page_size: state.pageSize
        });
        
        if (state.search) params.append('search', state.search);
        if (state.dateFrom) params.append('date_from', state.dateFrom);
        if (state.dateTo) params.append('date_to', state.dateTo);
        if (state.centerId) params.append('center_id', state.centerId);
        if (state.teacherId) params.append('teacher_id', state.teacherId);
        if (state.statusFilter) params.append('status', state.statusFilter);
        
        const url = getUrl('class-attendance-logs') + '?' + params.toString();
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch');
        
        renderTable(data.results);
        updatePagination(data);
    } catch (e) {
        console.error('Fetch failed:', e);
        showToast('Failed to load class logs', 'error');
        renderError();
    } finally {
        hideGlobalLoader();
    }
}

function renderTable(logs) {
    if (!els.tbody) return;
    
    if (!logs || logs.length === 0) {
        els.tbody.innerHTML = `
            <tr>
                <td colspan="10" class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <p>No class logs found</p>
                </td>
            </tr>
        `;
        return;
    }
    
    els.tbody.innerHTML = logs.map((log, index) => {
        const rowNum = (state.page - 1) * state.pageSize + index + 1;
        const statusInfo = log.status_info || {};
        const statusConfig = STATUS_CONFIG[statusInfo.key] || STATUS_CONFIG.unknown;
        
        return `
            <tr>
                <td class="text-center">${rowNum}</td>
                <td>${escapeHtml(log.teacher_name || '—')}</td>
                <td>
                    <div>${escapeHtml(log.center_name || '—')}</div>
                    <div class="text-muted" style="font-size: 12px;">${escapeHtml(log.village_name || '')} ${log.district_name ? '· ' + escapeHtml(log.district_name) : ''}</div>
                </td>
                <td class="datetime-cell">${formatDateTime(log.started_date)}</td>
                <td class="datetime-cell">${formatDateTime(log.end_date)}</td>
                <td class="hours-cell text-center">${statusInfo.gross_hours ? statusInfo.gross_hours + 'h' : '—'}</td>
                <td class="text-center">
                    ${statusInfo.present > 0 ? 
                        `<a href="#" class="count-link" style="color: #16a34a; font-weight: 500;" onclick="openStudentDetailModal(${log.id}, 'present'); return false;">${statusInfo.present}</a>` : 
                        '<span style="color: #16a34a; font-weight: 500;">0</span>'
                    }
                </td>
                <td class="text-center">
                    ${statusInfo.absent > 0 ? 
                        `<a href="#" class="count-link" style="color: #dc2626; font-weight: 500;" onclick="openStudentDetailModal(${log.id}, 'absent'); return false;">${statusInfo.absent}</a>` : 
                        '<span style="color: #dc2626; font-weight: 500;">0</span>'
                    }
                </td>
                <td>
                    ${log.center_id && log.center_name ? 
                        `<a href="#" class="location-link" onclick="openLocationMap(${log.center_id}, '${escapeHtml(log.center_name)}', ${log.latitude || 0}, ${log.longitude || 0}); return false;">
                            <svg class="location-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> View on Map
                        </a>` : 
                        '<span class="text-muted">—</span>'
                    }
                </td>
                <td>
                    <span class="status-badge ${statusConfig.className}">
                        <span class="status-icon" style="background: ${statusConfig.color};">${statusConfig.icon}</span>
                        <span class="status-text">${statusConfig.label}</span>
                    </span>
                </td
            </tr>
        `;
    }).join('');
    
}

function updatePagination(data) {
    state.totalLogs = data.count || 0;
    state.totalPages = data.total_pages || 0;
    
    if (state.totalLogs > 0) {
        if (els.pagination) els.pagination.style.display = 'flex';
        if (els.start) els.start.textContent = data.page * state.pageSize - state.pageSize + 1;
        if (els.end) els.end.textContent = Math.min(data.page * state.pageSize, state.totalLogs);
        if (els.total) els.total.textContent = state.totalLogs;
        
        // Update prev/next buttons
        if (els.prevPage) els.prevPage.disabled = state.page <= 1;
        if (els.nextPage) els.nextPage.disabled = state.page >= state.totalPages;
        
        // Page numbers
        renderPageNumbers();
    } else {
        if (els.pagination) els.pagination.style.display = 'none';
    }
}

function renderPageNumbers() {
    if (!els.pageNumbers) return;
    
    let html = '';
    const maxPages = 5;
    let startPage = Math.max(1, state.page - Math.floor(maxPages / 2));
    let endPage = Math.min(state.totalPages, startPage + maxPages - 1);
    
    if (endPage - startPage + 1 < maxPages) {
        startPage = Math.max(1, endPage - maxPages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="btn btn-sm ${i === state.page ? 'btn-primary' : 'btn-secondary'}" data-page="${i}">${i}</button>`;
    }
    
    els.pageNumbers.innerHTML = html;
    
    els.pageNumbers.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('click', () => {
            state.page = parseInt(btn.dataset.page);
            fetchAndRender();
        });
    });
}

function renderError() {
    if (!els.tbody) return;
    els.tbody.innerHTML = `
        <tr>
            <td colspan="10" class="empty-state" style="color: #dc2626;":
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <p>Failed to load class logs</p>
            </td>
        </tr>
    `;
}

// ── Dropdown Loading ──────────────────────────────────────────────
async function loadCenterDropdown() {
    try {
        const res = await fetch(getUrl('center-dropdown-list'), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();
        
        if (els.centerFilter && data.results) {
            els.centerFilter.innerHTML = '<option value="">All Centres</option>' +
                data.results.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
        }
    } catch (e) {
        console.error('Failed to load centers:', e);
    }
}

async function loadTeacherDropdown() {
    try {
        const res = await fetch(getUrl('teacher-dropdown-list'), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();
        
        if (els.teacherFilter && data.results) {
            els.teacherFilter.innerHTML = '<option value="">All Teachers</option>' +
                data.results.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
        }
    } catch (e) {
        console.error('Failed to load teachers:', e);
    }
}

// ── Formatters ────────────────────────────────────────────────────
function formatDateTime(isoString) {
    if (!isoString) return '<span class="text-muted">—</span>';
    try {
        const date = new Date(isoString);
        // Two-line format: time on top, date below
        const time = date.toLocaleString('en-IN', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        }).toLowerCase();
        const dateStr = date.toLocaleString('en-IN', {
            day: '2-digit',
            month: 'short',
            year: '2-digit'
        });
        return `<div class="datetime-stack"><span class="datetime-time">${time}</span><span class="datetime-date">${dateStr}</span></div>`;
    } catch {
        return isoString;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Location Map Modal ────────────────────────────────────────────
window.openLocationMap = function(centerId, centerName, latitude, longitude) {
    if (!els.mapClassName || !els.mapCenterInfo || !els.mapCoordinates) return;
    
    els.mapClassName.textContent = centerName;
    els.mapCenterInfo.textContent = `Centre ID: ${centerId}`;
    els.mapCoordinates.textContent = `Coordinates: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
    
    openModal(els.mapModal);
    
    // Initialize map after modal is visible
    setTimeout(() => {
        initLocationMap(latitude, longitude);
    }, 100);
};

function initLocationMap(lat, lng) {
    if (!window.google || !google.maps) {
        console.error('Google Maps not loaded');
        return;
    }
    
    const canvas = document.getElementById('map-modal-canvas');
    if (!canvas) return;
    
    // Destroy existing map
    if (state.currentMap) {
        state.currentMap = null;
        state.currentMapMarker = null;
    }
    
    const position = { lat: parseFloat(lat), lng: parseFloat(lng) };
    
    state.currentMap = new google.maps.Map(canvas, {
        center: position,
        zoom: 15,
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true,
        gestureHandling: 'cooperative'
    });
    
    state.currentMapMarker = new google.maps.Marker({
        position: position,
        map: state.currentMap,
        title: 'Centre Location',
        animation: google.maps.Animation.DROP
    });
    
    // Add info window
    const infoWindow = new google.maps.InfoWindow({
        content: `<div style="padding: 8px;"><strong>${els.mapClassName?.textContent || 'Centre'}</strong><br>Lat: ${lat.toFixed(6)}<br>Lng: ${lng.toFixed(6)}</div>`
    });
    
    state.currentMapMarker.addListener('click', () => {
        infoWindow.open(state.currentMap, state.currentMapMarker);
    });
    
    infoWindow.open(state.currentMap, state.currentMapMarker);
}

// ── Modal Helpers ─────────────────────────────────────────────────
function openModal(modal) {
    if (!modal) return;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('active');
    document.body.style.overflow = '';
    
    // Clean up map if closing map modal
    if (modal === els.mapModal && state.currentMap) {
        state.currentMap = null;
        state.currentMapMarker = null;
    }
}

// ── Global Loader ─────────────────────────────────────────────────
function showGlobalLoader() {
    const loader = document.getElementById('global-loader');
    if (loader) loader.classList.add('active');
}

function hideGlobalLoader() {
    const loader = document.getElementById('global-loader');
    if (loader) loader.classList.remove('active');
}

// ── Toast ─────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <svg class="toast-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                ${type === 'error' ? '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>' : 
                  type === 'success' ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>' :
                  '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>'}
            </svg>
            <span>${escapeHtml(message)}</span>
        </div>
        <button class="toast-close" aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
    `;
    container.appendChild(toast);
    
    toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());
    setTimeout(() => toast.remove(), 5000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 8px;';
    document.body.appendChild(container);
    return container;
}

// ── Student Detail Modal ─────────────────────────────────────────
function openStudentDetailModal(classId, filterType) {
    console.log('openStudentDetailModal called:', classId, filterType);
    const modal = document.getElementById('student-detail-modal');
    const title = document.getElementById('student-detail-title');
    const body = document.getElementById('student-detail-body');
    
    if (!modal) {
        console.error('Modal not found! Check if modal HTML exists in DOM');
        console.log('All modals:', document.querySelectorAll('[id*="modal"]'));
        return;
    }
    if (!title) console.warn('Title element not found');
    if (!body) console.warn('Body element not found');
    
    title.textContent = filterType === 'present' ? 'Present Students' : 'Absent Students';
    body.innerHTML = '<div style="text-align: center; padding: 40px; color: #9ca3af;">Loading...</div>';
    modal.style.display = 'flex';
    console.log('Modal display set to flex');
    
    if (typeof showGlobalLoader === 'function') showGlobalLoader('Loading student details...');
    
    fetch(getUrl('class-attendance-logs') + `?action=class_log_detail&class_id=${classId}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin'
    })
    .then(res => res.json())
    .then(data => {
        if (!data.students) {
            body.innerHTML = '<div style="text-align: center; padding: 40px; color: #9ca3af;">No student data available</div>';
            return;
        }
        
        const students = data.students.filter(s => 
            filterType === 'present' ? s.status === true : s.status === false
        );
        
        if (students.length === 0) {
            body.innerHTML = `<div style="text-align: center; padding: 40px; color: #9ca3af;">No ${filterType} students found</div>`;
            return;
        }
        
        body.innerHTML = `
            <div style="overflow-x: auto;">
                <table class="table" style="min-width: 600px;">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Student Name</th>
                            <th>Enrollment</th>
                            <th>Scan Time</th>
                            <th>Type</th>
                            <th>Location Verified</th>
                            <th>Coordinates</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${students.map((s, i) => `
                            <tr>
                                <td>${i + 1}</td>
                                <td>${escapeHtml(s.student_name || '—')}</td>
                                <td>${escapeHtml(s.enrollment_number || '—')}</td>
                                <td>${s.scan_date ? new Date(s.scan_date).toLocaleString('en-IN') : '—'}</td>
                                <td>${escapeHtml(s.attendance_type || '—')}</td>
                                <td>${s.location_verified ? '<span style="color:#16a34a">✓ Yes</span>' : '<span style="color:#dc2626">✕ No</span>'}</td>
                                <td>
                                    ${s.captured_latitude && s.captured_longitude ? 
                                        `${parseFloat(s.captured_latitude).toFixed(6)}, ${parseFloat(s.captured_longitude).toFixed(6)}` : '—'}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    })
    .catch(e => {
        console.error('Failed to load student details:', e);
        body.innerHTML = '<div style="text-align: center; padding: 40px; color: #dc2626;">Failed to load details</div>';
    })
    .finally(() => {
        if (typeof hideGlobalLoader === 'function') hideGlobalLoader();
    });
}

function closeStudentDetailModal() {
    const modal = document.getElementById('student-detail-modal');
    if (modal) modal.style.display = 'none';
}

// Expose to global scope for onclick handlers
window.openStudentDetailModal = openStudentDetailModal;
window.closeStudentDetailModal = closeStudentDetailModal;

// ── URL Helper ────────────────────────────────────────────────────
function getUrl(name) {
    const attr = `data-url-${name}`;
    return document.body.getAttribute(attr) || '';
}