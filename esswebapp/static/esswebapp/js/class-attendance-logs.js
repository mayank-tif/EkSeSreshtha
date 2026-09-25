/* ================================================================
   EK SE SRESHTHA - CLASS ATTENDANCE LOGS PAGE SCRIPT
   ---------------------------------------------------------------
   Date-centric class attendance logs with:
   - Single date filter, center filter, teacher filter, status filter
   - Table per center with: Centre, Teacher, Class Time, Status, Present, Absent, Location, Gross Hours
   - Status badges with info tooltips (like Keka)
   - Location link to open Google Maps modal
   - Detail modal with student attendance breakdown
   ================================================================ */

// ── State ─────────────────────────────────────────────────────────
const state = {
    page: 1,
    pageSize: parseInt(document.body.getAttribute('data-page-size')) || 50,
    search: '',
    date: '',
    centerId: '',
    teacherId: '',
    statusFilter: '',
    totalLogs: 0,
    totalPages: 0,
    currentMap: null,
    currentMapMarker: null
};

// ── Google Maps Async Loading ─────────────────────────────────────
let mapsLoaded = false;

function initGoogleMaps() {
    mapsLoaded = true;
    console.log('Google Maps API loaded');
}

// Wait for Google Maps to load before initializing
function waitForMaps(callback) {
    if (mapsLoaded && typeof google !== 'undefined' && google.maps) {
        callback();
    } else {
        setTimeout(() => waitForMaps(callback), 50);
    }
}

// ── DOM References ────────────────────────────────────────────────
const els = {
    get date() { return document.getElementById('logs-date'); },
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

// Summary counter element IDs
const SUMMARY_IDS = {
    total: 'count-total',
    in_progress: 'count-in_progress',
    completed: 'count-completed',
    completed_no_attendance: 'count-completed_no_attendance',
    active_ended: 'count-active_ended',
    active_ended_no_att: 'count-active_ended_no_att',
    cancelled: 'count-cancelled',
    holiday: 'count-holiday',
    sunday: 'count-sunday',
    not_started: 'count-not_started',
    no_class: 'count-no_class'
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
    active_ended_no_att: {
        label: 'Not Ended (No Attendance)',
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
    sunday: {
        label: 'Sunday',
        color: '#6b7280',
        icon: '☀',
        className: 'status-sunday'
    },
    not_started: {
        label: 'Not Started',
        color: '#6b7280',
        icon: '—',
        className: 'status-not_started'
    },
    no_class: {
        label: 'Class Not Held',
        color: '#6b7280',
        icon: '—',
        className: 'status-no_class'
    },
    unknown: {
        label: 'Unknown',
        color: '#6b7280',
        icon: '?',
        className: 'status-unknown'
    }
};

// ── Utility Functions ─────────────────────────────────────────────
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&')
        .replace(/</g, '<')
        .replace(/>/g, '>')
        .replace(/"/g, '"')
        .replace(/'/g, '&#039;');
}

function formatDateTime(isoString) {
    if (!isoString) return '—';
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return '—';
        
        const timeStr = date.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit', 
            hour12: true 
        });
        const dateStr = date.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: 'short', 
            year: '2-digit' 
        });
        
        return `<div class="datetime-stack">
            <span class="datetime-time">${timeStr}</span>
            <span class="datetime-date">${dateStr}</span>
        </div>`;
    } catch {
        return '—';
    }
}

function formatTimeOnly(isoString) {
    if (!isoString) return '—';
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return '—';
        return date.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit', 
            hour12: true 
        });
    } catch {
        return '—';
    }
}

function formatDateOnly(isoString) {
    if (!isoString) return '—';
    try {
        const date = new Date(isoString);
        if (isNaN(date.getTime())) return '—';
        return date.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: 'short', 
            year: '2-digit' 
        });
    } catch {
        return '—';
    }
}

function showToast(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
}


function getUrl(name) {
    const urls = {
        'class-attendance-logs': '/attendance/class-logs/',
        'center-dropdown-list': '/centres/dropdown-list/',
        'teacher-dropdown-list': '/teacher/dropdown-list/'
    };
    return urls[name] || '#';
}

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

// ── Init ──────────────────────────────────────────────────────────
async function init() {
    // Set default date (today)
    const today = new Date();
    
    if (els.date) els.date.value = today.toISOString().split('T')[0];
    
    state.date = els.date?.value || '';
    
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
    // Date
    if (els.date) {
        els.date.addEventListener('change', () => {
            state.page = 1;
            state.date = els.date.value;
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

// ── Summary Fetching ──────────────────────────────────────────────
async function fetchSummary() {
    try {
        const params = new URLSearchParams({
            action: 'class_log_summary',
            page_size: 1
        });
        
        if (state.search) params.append('search', state.search);
        if (state.date) params.append('date', state.date);
        if (state.centerId) params.append('center_id', state.centerId);
        if (state.teacherId) params.append('teacher_id', state.teacherId);
        if (state.statusFilter) params.append('status', state.statusFilter);
        
        const url = getUrl('class-attendance-logs') + '?' + params.toString();
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch summary');
        
        updateSummary(data);
    } catch (e) {
        console.error('Summary fetch failed:', e);
        // Reset counters on error
        Object.values(SUMMARY_IDS).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '0';
        });
    }
}

function updateSummary(data) {
    Object.entries(SUMMARY_IDS).forEach(([key, id]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = data[key] || 0;
    });
}

// ── Data Fetching ─────────────────────────────────────────────────
async function fetchAndRender() {
    showGlobalLoader();
    const startTime = Date.now();
    try {
        // Fetch summary counts
        await fetchSummary();
        
        const params = new URLSearchParams({
            action: 'class_logs',
            page: state.page,
            page_size: state.pageSize
        });
        
        if (state.search) params.append('search', state.search);
        if (state.date) params.append('date', state.date);
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
        const center = log.center || {};
        const classObj = log.class_obj || {};
        const statusInfo = log.status_info || {};
        const statusConfig = STATUS_CONFIG[statusInfo.key] || STATUS_CONFIG.unknown;
        
        // Format start time
        let startTimeHtml = '<span class="text-muted">—</span>';
        let endTimeHtml = '<span class="text-muted">—</span>';
        if (classObj.started_date) {
            const startTime = formatTimeOnly(classObj.started_date);
            const startDate = formatDateOnly(classObj.started_date);
            startTimeHtml = `<div class="datetime-stack">
                <span class="datetime-time">${startTime}</span>
                <span class="datetime-date">${startDate}</span>
            </div>`;
        }
        if (classObj.end_date) {
            const endTime = formatTimeOnly(classObj.end_date);
            const endDate = formatDateOnly(classObj.end_date);
            endTimeHtml = `<div class="datetime-stack">
                <span class="datetime-time" style="font-weight: 400; color: #6b7280;">${endTime}</span>
                <span class="datetime-date">${endDate}</span>
            </div>`;
        }
        
        // Teacher name
        const teacherName = classObj.teacher_name || '—';
        
        // Center info with village/district
        const centerName = center.center_name || '—';
        const villageName = center.village_name || '';
        const districtName = center.district_name || '';
        const centerLocation = [villageName, districtName].filter(Boolean).join(', ') || '—';
        
        // Present/Absent links
        const classId = classObj.id || 0;
        const presentHtml = statusInfo.present > 0 ? 
            `<a href="#" class="count-link" style="color: #16a34a; font-weight: 500;" onclick="openStudentDetailModal(${classId}, 'present'); return false;">${statusInfo.present}</a>` : 
            '<span style="color: #16a34a; font-weight: 500;">0</span>';
        const absentHtml = statusInfo.absent > 0 ? 
            `<a href="#" class="count-link" style="color: #dc2626; font-weight: 500;" onclick="openStudentDetailModal(${classId}, 'absent'); return false;">${statusInfo.absent}</a>` : 
            '<span style="color: #dc2626; font-weight: 500;">0</span>';
        
        // Location link
        const centerId = center.id || 0;
        const lat = center.latitude || 0;
        const lng = center.longitude || 0;
        const locationHtml = centerId && centerName ? 
            `<a href="#" class="location-link" onclick="openLocationMap(${centerId}, '${escapeHtml(centerName)}', ${lat}, ${lng}); return false;">
                <svg class="location-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> View on Map
            </a>` : 
            '<span class="text-muted">—</span>';
        
        // Status badge
        let statusLabel = statusConfig.label;
        if (statusInfo.key === 'holiday' && statusInfo.tooltip) {
            statusLabel = statusInfo.tooltip.replace('Holiday: ', '');
        }
        
        // Gross hours
        const grossHoursHtml = statusInfo.gross_hours ? 
            `<span class="text-muted" style="font-size: 12px;">${statusInfo.gross_hours}h</span>` : 
            '<span class="text-muted">—</span>';
        
        return `
            <tr>
                <td class="text-center">${rowNum}</td>
                <td>${escapeHtml(teacherName)}</td>
                <td>${escapeHtml(centerName)}<br><span class="text-muted" style="font-size: 11px;">${escapeHtml(centerLocation)}</span></td>
                <td>${startTimeHtml}</td>
                <td>${endTimeHtml}</td>
                <td class="text-center hours-cell">${grossHoursHtml}</td>
                <td class="text-center">${presentHtml}</td>
                <td class="text-center">${absentHtml}</td>
                <td>${locationHtml}</td>
                <td>
                    <span class="status-badge ${statusConfig.className}">
                        <span class="status-icon" style="background: ${statusConfig.color};">${statusConfig.icon}</span>
                        <span class="status-text">${statusLabel}</span>
                    </span>
                </td>
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
            <td colspan="10" class="empty-state" style="color: #dc2626;">
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

// ── Detail Modal ──────────────────────────────────────────────────
window.openStudentDetailModal = async function(classId, filterType) {
    showGlobalLoader();
    try {
        const params = new URLSearchParams({
            action: 'class_log_detail',
            class_id: classId,
            filter: filterType
        });
        
        const url = getUrl('class-attendance-logs') + '?' + params.toString();
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch details');
        
        const modal = document.getElementById('student-detail-modal');
        const title = document.getElementById('student-detail-title');
        const body = document.getElementById('student-detail-body');
        
        title.textContent = `${filterType === 'present' ? 'Present' : 'Absent'} Students - ${data.class_name || 'Class'}`;
        
        if (!data.students || data.students.length === 0) {
            body.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                    <p>No ${filterType} students found</p>
                </div>
            `;
        } else {
            body.innerHTML = `
                <div class="table-wrapper" style="overflow-x: auto;">
                    <table class="table" style="min-width: 600px;">
                        <thead>
                            <tr>
                                <th style="width: 50px;">#</th>
                                <th>Student Name</th>
                                <th>Roll Number</th>
                                <th>Scan Time</th>
                                <th>Type</th>
                                <th>Location Verified</th>
                                <th>Coordinates</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.students.map((s, i) => `
                                <tr>
                                    <td class="text-center">${i + 1}</td>
                                    <td>${escapeHtml(s.name || '—')}</td>
                                    <td>${escapeHtml(s.roll_number || '—')}</td>
                                    <td>${escapeHtml(s.scan_time || '—')}</td>
                                    <td>
                                        <span class="status-badge ${s.type ? 'status-completed' : 'status-cancelled'}">
                                            ${s.type ? '✓ Present' : '✕ Absent'}
                                        </span>
                                    </td>
                                    <td class="text-center">
                                        ${s.location_verified ? 
                                            '<span style="color: #16a34a;">✓ Yes</span>' : 
                                            '<span style="color: #dc2626;">✕ No</span>'
                                        }
                                    </td>
                                    <td class="text-center">${escapeHtml(s.coordinates || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
        
        openModal(modal);
    } catch (e) {
        console.error('Detail fetch failed:', e);
        showToast('Failed to load student details', 'error');
    } finally {
        hideGlobalLoader();
    }
};

window.closeStudentDetailModal = function() {
    const modal = document.getElementById('student-detail-modal');
    closeModal(modal);
};

// ── Location Map Modal ────────────────────────────────────────────
window.openLocationMap = function(centerId, centerName, latitude, longitude) {
    if (els.mapClassName) els.mapClassName.textContent = centerName;
    if (els.mapCenterInfo) els.mapCenterInfo.textContent = `Centre ID: ${centerId}`;
    if (els.mapCoordinates) els.mapCoordinates.textContent = `Lat: ${latitude}, Lng: ${longitude}`;
    
    openModal(els.mapModal);
    
    // Initialize map after modal is visible and Google Maps is loaded
    waitForMaps(() => {
        setTimeout(() => {
            initLocationMap(latitude, longitude);
        }, 100);
    });
};

function initLocationMap(lat, lng) {
    if (state.currentMap) return;
    
    const canvas = document.getElementById('map-modal-canvas');
    if (!canvas) return;
    
    try {
        if (typeof google === 'undefined' || !google.maps) {
            console.warn('Google Maps not loaded');
            canvas.innerHTML = '<div style="padding: 20px; text-align: center; color: #6b7280;">Google Maps not available</div>';
            return;
        }
        
        const center = { lat: parseFloat(lat), lng: parseFloat(lng) };
        
        state.currentMap = new google.maps.Map(canvas, {
            center: center,
            zoom: 15,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true
        });
        
        state.currentMapMarker = new google.maps.Marker({
            position: center,
            map: state.currentMap,
            title: 'Centre Location'
        });
        
        google.maps.event.addListenerOnce(state.currentMap, 'idle', () => {
            google.maps.event.trigger(state.currentMap, 'resize');
            state.currentMap.setCenter(center);
        });
        
    } catch (e) {
        console.error('Map init failed:', e);
        canvas.innerHTML = '<div style="padding: 20px; text-align: center; color: #dc2626;">Failed to load map</div>';
    }
}

// Expose closeModal globally for modal-backdrop close buttons
window.closeModal = closeModal;