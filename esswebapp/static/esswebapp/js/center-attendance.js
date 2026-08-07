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
                    <button class="btn-icon" title="View attendance"
                            onclick="event.stopPropagation(); openCentreDetail('${centre.id}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2"
                             stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>
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