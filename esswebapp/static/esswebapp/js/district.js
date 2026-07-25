/* ================================================================
   EK SE SRESHTHA - DISTRICT PAGE SCRIPT
   ----------------------------------------------------------------
   Manages the district list: fetch, search, pagination,
   and CRUD via modal forms. Uses common.js utilities.
   ================================================================ */

// ------------------------------------------------------------------
// PAGE INITIALISATION
// ------------------------------------------------------------------
renderShell({
    title: 'Districts',
    active: 'district',
    breadcrumbs: [
        { label: 'Home', urlName: 'dashboard' },
        { label: 'Constituency' },
        { label: 'District' }
    ]
});

// ------------------------------------------------------------------
// STATE
// ------------------------------------------------------------------
let currentPage = 1;
const pageSize = 50;
let isLoading = false;

// ------------------------------------------------------------------
// DOM REFERENCES
// ------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);

const tbody = $('#district-tbody');
const searchInput = $('#district-search');
const prevBtn = $('#prev-page');
const nextBtn = $('#next-page');
const pageNumbers = $('#page-numbers');
const totalEl = $('#total-districts');
const paginationStart = $('#pagination-start');
const paginationEnd = $('#pagination-end');
const paginationTotal = $('#pagination-total');
const modal = $('#district-modal');
const form = $('#district-form');
const editingId = $('#district-editing-id');
const modalTitle = $('#district-modal-title');
const submitBtn = $('#district-submit-btn');
const btnText = submitBtn.querySelector('.btn-text');
const btnLoader = submitBtn.querySelector('.btn-loader');
const districtNameInput = $('#district-name');
const addDistrictBtn = $('#add-district-btn');

// ------------------------------------------------------------------
// API CALLS
// ------------------------------------------------------------------
async function fetchDistricts() {
    if (isLoading) return;
    isLoading = true;
    showGlobalLoader('Fetching districts...');
    tbody.classList.add('loading');

    try {
        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            search: searchInput.value.trim()
        });

        const res = await fetch(`${getUrl('district')}?${params}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        renderTable(data.results);
        updatePagination(data);
        updateTotalCount(data.count);
    } catch (err) {
        console.error('fetchDistricts error:', err);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Failed to load districts: ${err.message}</td></tr>`;
    } finally {
        isLoading = false;
        tbody.classList.remove('loading');
        hideGlobalLoader();
    }
}

async function fetchDistrictById(id) {
    const res = await fetch(`${getUrl('district')}?id=${id}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin'
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

async function saveDistrictApi(payload) {
    const isEdit = !!payload.id;
    const res = await fetch(getUrl('district'), {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCsrfToken()
        },
        credentials: 'same-origin',
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

async function deleteDistrictApi(id) {
    const res = await fetch(`${getUrl('district')}?id=${id}`, {
        method: 'DELETE',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCsrfToken()
        },
        credentials: 'same-origin'
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Delete failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return true;
}

// ------------------------------------------------------------------
// RENDERING
// ------------------------------------------------------------------
function renderTable(districts) {
    if (!districts || !districts.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No districts found${searchInput.value.trim() ? ' matching "' + escapeHtml(searchInput.value.trim()) + '"' : ''}.</td></tr>`;
        return;
    }

    tbody.innerHTML = districts.map((district, idx) => `
        <tr data-id="${district.id}">
            <td>${idx + 1}</td>
            <td>${escapeHtml(district.name || '-')}</td>
            <td>${district.vidhan_sabha_count || 0}</td>
            <td>${district.panchayat_count || 0}</td>
            <td>${formatDate(district.created_on)}</td>
            <td>
                <div class="action-buttons">
                    <button type="button" class="btn-icon btn-edit" data-id="${district.id}" title="Edit">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button type="button" class="btn-icon btn-delete" data-id="${district.id}" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

function updateTotalCount(count) {
    if (totalEl) totalEl.textContent = count;
}

function updatePagination(data) {
    const totalPages = data.total_pages || 1;
    const page = data.page || currentPage;

    if (paginationStart) paginationStart.textContent = data.count ? (page - 1) * pageSize + 1 : 0;
    if (paginationEnd) paginationEnd.textContent = Math.min(page * pageSize, data.count || 0);
    if (paginationTotal) paginationTotal.textContent = data.count || 0;

    prevBtn.disabled = page === 1;
    nextBtn.disabled = page === totalPages;

    pageNumbers.innerHTML = '';

    if (totalPages <= 1) return;

    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, startPage + 4);

    if (endPage - startPage + 1 < 5) {
        startPage = Math.max(1, endPage - 4);
    }

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
        btn.className = `page-btn ${pageNum === page ? 'active' : ''}`;
        btn.textContent = pageNum;
        btn.onclick = () => goToPage(pageNum);
        pageNumbers.appendChild(btn);
    }

    function addEllipsis() {
        const span = document.createElement('span');
        span.className = 'page-ellipsis';
        span.textContent = '…';
        pageNumbers.appendChild(span);
    }
}

function goToPage(page) {
    currentPage = page;
    fetchDistricts();
}

// ------------------------------------------------------------------
// MODAL HANDLERS
// ------------------------------------------------------------------
function openDistrictModal() {
    resetForm();
    modalTitle.textContent = 'Add District';
    btnText.textContent = 'Save District';
    modal.classList.add('active');
    districtNameInput.focus();
}

function closeDistrictModal() {
    modal.classList.remove('active');
    resetForm();
}

function resetForm() {
    form.reset();
    editingId.value = '';
    districtNameInput.classList.remove('is-invalid');
    setBtnLoading(false);
}

function setBtnLoading(loading) {
    if (loading) {
        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'inline-flex';
    } else {
        submitBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
    }
}

// ------------------------------------------------------------------
// CRUD OPERATIONS
// ------------------------------------------------------------------
async function handleFormSubmit(e) {
    e.preventDefault();
    const name = districtNameInput.value.trim();
    if (!name) {
        districtNameInput.classList.add('is-invalid');
        districtNameInput.focus();
        return;
    }
    districtNameInput.classList.remove('is-invalid');

    const id = editingId.value ? parseInt(editingId.value, 10) : null;
    const payload = { name };
    if (id) payload.id = id;

    setBtnLoading(true);
    showGlobalLoader(id ? 'Updating district...' : 'Creating district...');

    try {
        await saveDistrictApi(payload);
        closeDistrictModal();
        await fetchDistricts();
    } catch (err) {
        console.error('Save district error:', err);
        alert(`Failed to ${id ? 'update' : 'create'} district: ${err.message}`);
    } finally {
        setBtnLoading(false);
        hideGlobalLoader();
    }
}

async function handleEditClick(id) {
    showGlobalLoader('Loading district details...');
    try {
        const district = await fetchDistrictById(id);
        editingId.value = district.id;
        districtNameInput.value = district.name || '';
        modalTitle.textContent = 'Edit District';
        btnText.textContent = 'Update District';
        modal.classList.add('active');
        districtNameInput.focus();
        districtNameInput.select();
    } catch (err) {
        console.error('Fetch district error:', err);
        alert(`Failed to load district: ${err.message}`);
    } finally {
        hideGlobalLoader();
    }
}

async function handleDeleteClick(id) {
    if (!confirm('Are you sure you want to delete this district? This will set its status to inactive.')) {
        return;
    }

    showGlobalLoader('Deleting district...');
    try {
        await deleteDistrictApi(id);
        await fetchDistricts();
    } catch (err) {
        console.error('Delete district error:', err);
        alert(`Failed to delete district: ${err.message}`);
    } finally {
        hideGlobalLoader();
    }
}

// ------------------------------------------------------------------
// EVENT LISTENERS
// ------------------------------------------------------------------
// Search input - debounced
let searchTimeout;
searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        currentPage = 1;
        fetchDistricts();
    }, 200);
});

// Form submit
form.addEventListener('submit', handleFormSubmit);

// Add District button
if (addDistrictBtn) {
    addDistrictBtn.addEventListener('click', openDistrictModal);
}

// Event delegation for table action buttons (edit/delete)
tbody.addEventListener('click', (e) => {
    const editBtn = e.target.closest('.btn-edit');
    const deleteBtn = e.target.closest('.btn-delete');

    if (editBtn) {
        const id = parseInt(editBtn.dataset.id, 10);
        if (!isNaN(id)) handleEditClick(id);
    } else if (deleteBtn) {
        const id = parseInt(deleteBtn.dataset.id, 10);
        if (!isNaN(id)) handleDeleteClick(id);
    }
});

// Close modal on backdrop click
modal.addEventListener('click', (e) => {
    if (e.target === modal) closeDistrictModal();
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('active')) {
        closeDistrictModal();
    }
});

// Pagination buttons
prevBtn.addEventListener('click', () => {
    if (currentPage > 1) goToPage(currentPage - 1);
});

nextBtn.addEventListener('click', () => {
    const totalPages = parseInt(nextBtn.dataset.totalPages) || 1;
    if (currentPage < totalPages) goToPage(currentPage + 1);
});

// ------------------------------------------------------------------
// INITIAL LOAD
// ------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', fetchDistricts);