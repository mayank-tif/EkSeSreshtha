/* ================================================================
   HOLIDAYS PAGE - JAVASCRIPT
   Academic holidays (global, all centers) + center holidays,
   filtered by type / center / year / status.
   ================================================================ */

let currentPage = 1;
const pageSize = 50;
let deleteHolidayId = null;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
});

function initializePage() {
    // Type + Center + Year filter dropdowns
    initCenterFilter();
    initYearFilter();
    
    // Load holidays list
    loadHolidays();
    
    // Event listeners
    setupEventListeners();
}

function setupEventListeners() {
    // Add holiday button
    document.getElementById('btn-add-holiday').addEventListener('click', () => openHolidayModal());
    
    // Form submit
    document.getElementById('holiday-form').addEventListener('submit', handleFormSubmit);

    // Academic checkbox toggles the center selector
    document.getElementById('holiday-academic').addEventListener('change', toggleCenterGroup);
    
    // Filter changes
    document.getElementById('filter-type').addEventListener('change', () => { currentPage = 1; loadHolidays(); });
    document.getElementById('filter-center').addEventListener('change', () => { currentPage = 1; loadHolidays(); });
    document.getElementById('filter-status').addEventListener('change', () => { currentPage = 1; loadHolidays(); });
    document.getElementById('filter-search').addEventListener('input', debounce(() => { currentPage = 1; loadHolidays(); }, 300));
    
    
    // Delete confirmation
    document.getElementById('confirm-delete-btn').addEventListener('click', confirmDelete);
}

// ================================================================
// API CALLS
// ================================================================

function getAcademicHolidaysUrl() {
    // Try sidebar's global function first
    if (typeof window.sidebarGetUrl === 'function') {
        return window.sidebarGetUrl('academic-holidays');
    }
    // Fallback: read directly from body data attribute
    const attr = document.body.getAttribute('data-url-academic-holidays');
    return attr || '/academic-holidays/';
}

function apiCall(action, params = {}, method = 'GET', body = null) {
    const url = new URL(getAcademicHolidaysUrl(), window.location.origin);
    url.searchParams.append('action', action);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
            url.searchParams.append(key, value);
        }
    });
    
    const options = {
        method: method,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': (typeof getCsrfToken === 'function' ? getCsrfToken() : (document.querySelector('meta[name="csrf-token"]')?.content || ''))
        }
    };
    
    if (body) {
        options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
        options.body = new URLSearchParams(body).toString();
    }
    
    return fetch(url, options)
        .then(res => res.json())
        .then(data => {
            if (data.detail) {
                throw new Error(data.detail);
            }
            return data;
        });
}

function initCenterFilter() {
    const select = document.getElementById('filter-center');
    if (!select) return;
    apiCall('centers')
        .then(data => {
            const currentVal = select.value;
            select.innerHTML = '<option value="">All Centers</option>';
            (data.results || []).forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = c.center_name;
                select.appendChild(opt);
            });
            select.value = currentVal;
        })
        .catch(err => console.error('Failed to load centers:', err));
}

let modalCentersLoaded = false;
function loadModalCenters() {
    const select = document.getElementById('holiday-center');
    if (!select || modalCentersLoaded) return;
    apiCall('centers')
        .then(data => {
            const currentVals = Array.from(select.selectedOptions).map(o => o.value);
            select.innerHTML = '';
            (data.results || []).forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = c.center_name;
                select.appendChild(opt);
            });
            currentVals.forEach(v => {
                const opt = select.querySelector(`option[value="${v}"]`);
                if (opt) opt.selected = true;
            });
            modalCentersLoaded = true;
        })
        .catch(err => console.error('Failed to load centers:', err));
}

function toggleCenterGroup() {
    const academic = document.getElementById('holiday-academic');
    const group = document.getElementById('holiday-center-group');
    const centerSelect = document.getElementById('holiday-center');
    if (!academic || !group) return;
    // Academic holiday = global (all centers): hide center selector
    group.style.display = academic.checked ? 'none' : 'block';
}

function initYearFilter() {
    const select = document.getElementById('filter-year');
    if (!select) return;

    // Load single calendar years (2025, 2026, ...) - not academic year
    // ranges like 2025-2026. Holidays are filtered by the year of
    // their start date.
    apiCall('years')
        .then(data => {
            const currentVal = select.value;
            select.innerHTML = '<option value="">-- Select Year --</option>';
            (data.results || []).forEach(year => {
                const opt = document.createElement('option');
                opt.value = year;
                opt.textContent = year;
                select.appendChild(opt);
            });
            select.value = currentVal;
        })
        .catch(err => console.error('Failed to load years:', err));

    select.addEventListener('change', () => {
        currentPage = 1;
        loadHolidays();
    });
}

function getYearFilterParams() {
    const select = document.getElementById('filter-year');
    const y = select ? select.value : '';
    return y ? { filter_year: y } : {};
}

function loadHolidays() {
    showTableLoading(true);
    
    const params = {
        page: currentPage,
        page_size: pageSize,
        search: document.getElementById('filter-search').value,
        holiday_type: document.getElementById('filter-type').value,
        center_id: document.getElementById('filter-center').value,
        ...getYearFilterParams(),
        status: document.getElementById('filter-status').value
    };
    
    return apiCall('list', params)
        .then(data => {
            renderHolidaysTable(data.results);
            renderPagination(data.count, data.page, data.page_size, data.total_pages);
        })
        .catch(err => {
            console.error('Failed to load holidays:', err);
            showToast('Failed to load holidays: ' + err.message, 'danger');
            renderHolidaysTable([]);
            renderPagination(0, 1, pageSize, 0);
        })
        .finally(() => showTableLoading(false));
}

function getHoliday(id) {
    return apiCall('get', { id })
        .then(data => data)
        .catch(err => {
            console.error('Failed to get holiday:', err);
            showToast('Failed to load holiday details: ' + err.message, 'danger');
            throw err;
        });
}

function createHoliday(formData) {
    return apiCall('create', {}, 'POST', formData);
}

function updateHoliday(formData) {
    return apiCall('update', {}, 'POST', formData);
}

function deleteHoliday(id) {
    return apiCall('delete', {}, 'POST', { action: 'delete', id });
}

// ================================================================
// UI RENDERING
// ================================================================

function renderHolidaysTable(holidays) {
    const tbody = document.getElementById('holidays-tbody');
    
    if (!holidays || holidays.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted py-5">
                    No holidays found
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = holidays.map(h => `
        <tr data-id="${h.id}">
            <td>
                <div class="fw-medium">${escapeHtml(h.name)}</div>
                ${h.description ? `<div class="text-muted small">${escapeHtml(h.description)}</div>` : ''}
            </td>
            <td>
                <span class="badge ${h.academic_holiday ? 'badge-info' : 'badge-warning'}">
                    ${h.academic_holiday ? 'Academic' : 'Center'}
                </span>
            </td>
            <td>${h.academic_holiday ? '<span class="text-muted">All Centers</span>' : escapeHtml(h.center_name || '-')}</td>
            <td>${formatDate(h.start_date)}</td>
            <td>${h.end_date ? formatDate(h.end_date) : '<span class="text-muted">-</span>'}</td>
            <td>
                <span class="badge ${h.status ? 'badge-success' : 'badge-neutral'}">
                    ${h.status ? 'Active' : 'Inactive'}
                </span>
            </td>
            <td>${h.created_on ? formatDateTime(h.created_on) : '-'}</td>
            <td class="text-center">
                <div class="table-actions">
                    <button type="button" class="row-action-btn btn-edit" data-id="${h.id}" title="Edit" aria-label="Edit">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    ${h.status ? `
                    <button type="button" class="row-action-btn danger btn-delete" data-id="${h.id}" title="Delete" aria-label="Delete">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `).join('');
    
    // Add event listeners to buttons
    tbody.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', () => openHolidayModal(btn.dataset.id));
    });
    tbody.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', () => openDeleteModal(btn.dataset.id));
    });
}

function renderPagination(total, page, pageSize, totalPages) {
    const container = document.getElementById('holidays-pagination');

    // Always show the pagination bar (like the Centres template),
    // even when there is only one page.
    if (totalPages < 1) totalPages = 1;
    if (page < 1) page = 1;
    if (page > totalPages) page = totalPages;

    const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);

    let html = '<div class="pagination-wrapper">';
    html += `<div class="pagination-info">Showing <span>${start}-${end}</span> of <span>${total}</span></div>`;
    html += '<div class="pagination-controls">';

    html += `<button type="button" class="page-btn pagination-prev" data-page="${page - 1}" ${page === 1 ? 'disabled' : ''}>Previous</button>`;

    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button type="button" class="page-btn ${i === page ? 'active' : ''}" data-page="${i}">${i}</button>`;
    }

    html += `<button type="button" class="page-btn pagination-next" data-page="${page + 1}" ${page === totalPages ? 'disabled' : ''}>Next</button>`;
    html += '</div></div>';

    container.innerHTML = html;

    container.querySelectorAll('.page-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const newPage = parseInt(btn.dataset.page);
            if (newPage && newPage !== page && newPage >= 1 && newPage <= totalPages) {
                currentPage = newPage;
                loadHolidays();
            }
        });
    });
}

function showTableLoading(show) {
    const tbody = document.getElementById('holidays-tbody');
    if (show) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5">
                    <span class="text-muted">Loading...</span>
                </td>
            </tr>
        `;
    }
}

// ================================================================
// MODAL HANDLING
// ================================================================

function openHolidayModal(holidayId = null) {
    resetForm();
    loadModalCenters();
    toggleCenterGroup();
    
    const title = document.getElementById('holiday-modal-label');
    const submitBtn = document.getElementById('holiday-submit-btn');
    const statusGroup = document.getElementById('holiday-status-group');
    
    if (holidayId) {
        // Edit mode
        title.textContent = 'Edit Holiday';
        submitBtn.textContent = 'Update Holiday';
        document.getElementById('holiday-action').value = 'update';
        statusGroup.style.display = 'block';
        
        // Load holiday data
        getHoliday(holidayId).then(holiday => {
            document.getElementById('holiday-id').value = holiday.id;
            document.getElementById('holiday-name').value = holiday.name;
            document.getElementById('holiday-description').value = holiday.description || '';

            if (holiday.start_date) {
                document.getElementById('holiday-start-date').value = holiday.start_date.split('T')[0];
            }
            if (holiday.end_date) {
                document.getElementById('holiday-end-date').value = holiday.end_date.split('T')[0];
            }
            
            document.getElementById('holiday-status').checked = holiday.status;
            loadModalCenters();
            document.getElementById('holiday-academic').checked = !!holiday.academic_holiday;
            if (holiday.center_id) {
                Array.from(document.getElementById('holiday-center').options).forEach(o => {
                    o.selected = (o.value == holiday.center_id);
                });
            }
            toggleCenterGroup();
        });
    } else {
        // Create mode
        title.textContent = 'Add Holiday';
        submitBtn.textContent = 'Save Holiday';
        document.getElementById('holiday-action').value = 'create';
        statusGroup.style.display = 'none';
        
        // Set default dates to today
        const today = new Date().toISOString().split('T')[0];
        document.getElementById('holiday-start-date').value = today;
    }
    
    openModal('holiday-modal');
}

function resetForm() {
    const form = document.getElementById('holiday-form');
    form.reset();
    document.getElementById('holiday-id').value = '';
    document.getElementById('holiday-action').value = 'create';
    document.getElementById('holiday-status-group').style.display = 'none';
    document.getElementById('holiday-status').checked = true;
    document.getElementById('holiday-academic').checked = false;
    Array.from(document.getElementById('holiday-center').options).forEach(o => { o.selected = false; });
    toggleCenterGroup();
}

function handleFormSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const action = document.getElementById('holiday-action').value;
    const submitBtn = document.getElementById('holiday-submit-btn');
    
    // Validate
    const name = document.getElementById('holiday-name').value.trim();
    const startDate = document.getElementById('holiday-start-date').value;
    
    if (!name) {
        showToast('Holiday name is required', 'danger');
        return;
    }
    if (!startDate) {
        showToast('Start date is required', 'danger');
        return;
    }
    const academic = document.getElementById('holiday-academic').checked;
    const centerSelect = document.getElementById('holiday-center');
    const centerIds = Array.from(centerSelect.selectedOptions).map(o => o.value);
    if (!academic && centerIds.length === 0) {
        showToast('Select at least one center for center holidays', 'danger');
        return;
    }
    
    // Prepare form data
    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });
    // Checkbox state is not always included in FormData
    data.academic_holiday = academic ? 'true' : 'false';
    data.center_id = academic ? '' : centerIds.join(',');
    
    // Disable button
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    
    const promise = action === 'create' ? createHoliday(data) : updateHoliday(data);
    
    promise
        .then(result => {
            showToast(result.message || 'Holiday saved successfully', 'success');
            closeModal('holiday-modal');
            loadHolidays();
        })
        .catch(err => {
            showToast(err.message || 'Failed to save holiday', 'danger');
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = action === 'create' ? 'Save Holiday' : 'Update Holiday';
        });
}

function openDeleteModal(holidayId) {
    deleteHolidayId = holidayId;
    
    // Get holiday name for confirmation
    getHoliday(holidayId).then(holiday => {
        document.getElementById('delete-holiday-name').textContent = holiday.name;
        openModal('delete-modal');
    });
}

function confirmDelete() {
    if (!deleteHolidayId) return;
    
    const btn = document.getElementById('confirm-delete-btn');
    btn.disabled = true;
    btn.textContent = 'Deleting...';
    
    deleteHoliday(deleteHolidayId)
        .then(result => {
            showToast(result.message || 'Holiday deleted successfully', 'success');
            closeModal('delete-modal');
            loadHolidays();
        })
        .catch(err => {
            showToast(err.message || 'Failed to delete holiday', 'danger');
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = 'Delete';
            deleteHolidayId = null;
        });
}

// ================================================================
// UTILITIES
// ================================================================

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
        return dateStr;
    }
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: 'short', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

