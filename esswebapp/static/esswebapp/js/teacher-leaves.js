/* ================================================================
   TEACHER LEAVES PAGE - JAVASCRIPT
   List teacher leave applications (filters: center, teacher,
   approval status). Approve/Reject actions are shown ONLY for
   pending leaves (continuous working days beyond the maximum
   allowed, excluding Sat/Sun and AcademicHoliday days).
   ================================================================ */

let currentPage = 1;
const pageSize = 50;
let pendingLeaveAction = null; // { id, action }

document.addEventListener('DOMContentLoaded', function () {
    initializePage();
});

function initializePage() {
    initDateFilter();
    loadFilterOptions();
    loadLeaves();

    ['filter-center', 'filter-teacher', 'filter-approval-status'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            currentPage = 1;
            loadLeaves();
        });
    });

    ['filter-start-date', 'filter-end-date'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            currentPage = 1;
            loadLeaves();
        });
    });

    document.getElementById('btn-clear-filters').addEventListener('click', () => {
        document.getElementById('filter-center').value = '';
        document.getElementById('filter-teacher').value = '';
        document.getElementById('filter-approval-status').value = '';
        document.getElementById('filter-start-date').value = '';
        document.getElementById('filter-end-date').value = '';
        document.getElementById('filter-search').value = '';
        currentPage = 1;
        loadLeaves();
    });

    let searchTimer;
    document.getElementById('filter-search').addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => { currentPage = 1; loadLeaves(); }, 300);
    });

    document.getElementById('leave-action-confirm').addEventListener('click', confirmLeaveAction);
}

// ================================================================
// API CALLS
// ================================================================

function getTeacherLeavesUrl() {
    if (typeof window.sidebarGetUrl === 'function') {
        return window.sidebarGetUrl('teacher-leaves');
    }
    const attr = document.body.getAttribute('data-url-teacher-leaves');
    return attr || '/teacher-leaves/';
}

function apiCall(action, params = {}, method = 'GET', body = null) {
    const url = new URL(getTeacherLeavesUrl(), window.location.origin);
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

// Calendar filter on StartDate, defaulting to the current month
// (one month of leaves shown by default). Clear shows all leaves.
function initDateFilter() {
    const now = new Date();
    const first = new Date(now.getFullYear(), now.getMonth(), 1);
    const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    document.getElementById('filter-start-date').value = toISODate(first);
    document.getElementById('filter-end-date').value = toISODate(last);
}

function toISODate(d) {
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${m}-${day}`;
}

function loadFilterOptions() {
    apiCall('centers').then(data => {
        const select = document.getElementById('filter-center');
        (data.results || []).forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = c.name;
            select.appendChild(opt);
        });
    }).catch(err => console.error('Failed to load centers:', err));

    apiCall('teachers').then(data => {
        const select = document.getElementById('filter-teacher');
        (data.results || []).forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name;
            select.appendChild(opt);
        });
    }).catch(err => console.error('Failed to load teachers:', err));
}

function loadLeaves() {
    showTableLoading(true);

    const params = {
        page: currentPage,
        page_size: pageSize,
        center: document.getElementById('filter-center').value,
        teacher: document.getElementById('filter-teacher').value,
        approval_status: document.getElementById('filter-approval-status').value,
        start_date: document.getElementById('filter-start-date').value,
        end_date: document.getElementById('filter-end-date').value,
        search: document.getElementById('filter-search').value,
    };

    return apiCall('list', params)
        .then(data => {
            // The server echoes the range it actually filtered on
            // (default = current month when the inputs are empty) -
            // keep the calendar inputs in sync with the data shown
            // so an "empty" filter never hides the applied range.
            if (data.applied_start_date !== undefined) {
                document.getElementById('filter-start-date').value = data.applied_start_date || '';
                document.getElementById('filter-end-date').value = data.applied_end_date || '';
            }
            renderLeavesTable(data.results);
            renderPagination(data.count, data.page, data.page_size, data.total_pages);
        })
        .catch(err => {
            console.error('Failed to load leaves:', err);
            showToast('Failed to load leaves: ' + err.message, 'danger');
            renderLeavesTable([]);
            renderPagination(0, 1, pageSize, 0);
        })
        .finally(() => showTableLoading(false));
}

function renderLeavesTable(leaves) {
    const tbody = document.getElementById('leaves-tbody');

    if (!leaves || leaves.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center text-muted py-5">
                    No teacher leaves found.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = leaves.map(leave => `
        <tr data-id="${leave.id}">
            <td>
                <div class="fw-medium">${escapeHtml(leave.teacher_name || '-')}</div>
            </td>
            <td>${escapeHtml(leave.center_name || '-')}</td>
            <td>
                <div class="fw-medium">${escapeHtml(leave.name || '-')}</div>
                ${leave.description ? `<div class="text-muted small">${escapeHtml(leave.description)}</div>` : ''}
            </td>
            <td>${formatDate(leave.start_date)}</td>
            <td>${leave.end_date ? formatDate(leave.end_date) : '<span class="text-muted">-</span>'}</td>
            <td class="text-center">${leave.continuous_days ?? '-'}</td>
            <td>
                <span class="badge ${leave.approval_status === 'pending' ? 'badge-warning' : leave.approval_status === 'rejected' ? 'badge-danger' : 'badge-success'}">
                    ${leave.approval_status === 'pending' ? 'Pending' : leave.approval_status === 'rejected' ? 'Rejected' : 'Approved'}
                </span>
            </td>
            <td>${escapeHtml(leave.approved_by_name || '-')}</td>
            <td class="text-center">
                <div class="table-actions">
                    ${leave.approval_status === 'pending' ? `
                    <button type="button" class="btn btn-success btn-sm btn-approve" data-id="${leave.id}" title="Approve" aria-label="Approve">
                        Approve
                    </button>
                    <button type="button" class="btn btn-danger btn-sm btn-reject" data-id="${leave.id}" title="Reject" aria-label="Reject">
                        Reject
                    </button>` : ''}
                </div>
            </td>
        </tr>
    `).join('');

    tbody.querySelectorAll('.btn-approve').forEach(btn => {
        btn.addEventListener('click', () => openLeaveActionModal(btn.dataset.id, 'approve'));
    });
    tbody.querySelectorAll('.btn-reject').forEach(btn => {
        btn.addEventListener('click', () => openLeaveActionModal(btn.dataset.id, 'reject'));
    });
}

function renderPagination(total, page, pageSize, totalPages) {
    const container = document.getElementById('leaves-pagination');

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
                loadLeaves();
            }
        });
    });
}

function openLeaveActionModal(id, action) {
    pendingLeaveAction = { id, action };
    const isApprove = action === 'approve';
    document.getElementById('leave-action-title').textContent = isApprove ? 'Approve Leave' : 'Reject Leave';
    document.getElementById('leave-action-message').textContent = isApprove
        ? 'Are you sure you want to approve this leave?'
        : 'Are you sure you want to reject this leave?';
    document.getElementById('leave-action-confirm').textContent = isApprove ? 'Approve' : 'Reject';
    openModal('leave-action-modal');
}

function confirmLeaveAction() {
    if (!pendingLeaveAction) return;
    const { id, action } = pendingLeaveAction;
    const btn = document.getElementById('leave-action-confirm');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    apiCall(action, {}, 'POST', { action, id })
        .then(() => {
            showToast(action === 'approve' ? 'Leave approved successfully' : 'Leave rejected successfully', 'success');
            closeModal('leave-action-modal');
            loadLeaves();
        })
        .catch(err => showToast('Failed: ' + err.message, 'danger'))
        .finally(() => {
            btn.disabled = false;
            btn.textContent = action === 'approve' ? 'Approve' : 'Reject';
            pendingLeaveAction = null;
        });
}

function showTableLoading(show) {
    const tbody = document.getElementById('leaves-tbody');
    if (show) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-5">
                    <span class="text-muted">Loading...</span>
                </td>
            </tr>
        `;
    }
}
