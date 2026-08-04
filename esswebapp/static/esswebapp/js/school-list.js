/* ================================================================
   EK SE SRESHTHA - SCHOOL LIST SCRIPT
   ----------------------------------------------------------------
   Master list of partner schools with full CRUD via API.
   - Add a school with a single input field
   - Edit / delete existing school rows
   - Live search filter over the table
   - Pagination support
   ================================================================ */

let state = {
    schools: [],
    currentPage: 1,
    pageSize: AppConfig.pageSize,
    totalPages: 1,
    totalCount: 0
};

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('school-form').addEventListener('submit', handleSchoolSubmit);
    document.getElementById('school-search').addEventListener('input', () => {
        state.currentPage = 1;
        loadSchools();
    });

    // Pagination buttons
    document.getElementById('prev-page').addEventListener('click', () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            loadSchools();
        }
    });
    document.getElementById('next-page').addEventListener('click', () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            loadSchools();
        }
    });

    await loadSchools();
    renderSchoolTable();
});

/* ================================================================
   LOAD SCHOOLS FROM API (with pagination)
   ================================================================ */

async function loadSchools() {
    showGlobalLoader('Loading schools...');
    try {
        const search = document.getElementById('school-search').value.trim();
        const params = new URLSearchParams({
            page: state.currentPage,
            page_size: state.pageSize
        });
        if (search) params.set('search', search);

        const url = `${getUrl('school-details-list')}?${params}`;
        const response = await apiFetch(url);
        state.schools = response?.results || response || [];
        state.totalCount = response?.count || state.schools.length;
        state.totalPages = response?.total_pages || 1;
        console.log('Loaded schools:', state.schools.length, 'page:', state.currentPage, 'of', state.totalPages);
    } catch (error) {
        console.error('Failed to load schools:', error);
        showToast('Failed to load schools', 'danger');
        state.schools = [];
        state.totalCount = 0;
        state.totalPages = 1;
    } finally {
        hideGlobalLoader();
    }
    renderSchoolTable();
}

/* ================================================================
   FORM SUBMIT (add / update)
   ================================================================ */

async function handleSchoolSubmit(event) {
    event.preventDefault();

    const nameInput = document.getElementById('school-name');
    const name = nameInput.value.trim();
    const editingId = document.getElementById('school-editing-id').value;

    if (!name) {
        showToast('School name is required.', 'danger');
        return;
    }

    // Prevent duplicate school names (case-insensitive, excluding the row being edited)
    const existing = state.schools.find(s =>
        (s.schoolName || s.name || '').toLowerCase() === name.toLowerCase() &&
        s.id !== editingId
    );
    if (existing) {
        showToast('A school with this name already exists.', 'danger');
        return;
    }

    showGlobalLoader();
    try {
        let result;
        if (editingId) {
            // Update
            result = await apiFetch(getUrl('school-details-list'), {
                method: 'PUT',
                body: JSON.stringify({ id: editingId, name: name })
            });
        } else {
            // Create
            result = await apiFetch(getUrl('school-details-list'), {
                method: 'POST',
                body: JSON.stringify({ name: name })
            });
        }

        if (result?.detail) {
            showToast(result.detail, 'danger');
            return;
        }

        showToast(editingId ? 'School updated successfully.' : 'School added successfully.', 'success');
        resetSchoolForm();
        await loadSchools();
        renderSchoolTable();
    } catch (error) {
        console.error('School save failed:', error);
        showToast('Failed to save school: ' + error.message, 'danger');
    } finally {
        hideGlobalLoader();
    }
}

/* ================================================================
   RESET FORM
   ================================================================ */

function resetSchoolForm() {
    document.getElementById('school-form').reset();
    document.getElementById('school-editing-id').value = '';
    document.getElementById('school-form-title').textContent = 'Add School';
    document.getElementById('school-submit-btn').textContent = 'Add School';
    document.getElementById('school-cancel-btn').hidden = true;
}

/* ================================================================
   EDIT SCHOOL
   Loads the selected row into the form for editing.
   ================================================================ */

function editSchool(id) {
    // Find school by id
    const school = state.schools.find(s => s.id == id);
    if (!school) {
        showToast('School not found', 'danger');
        return;
    }

    document.getElementById('school-editing-id').value = school.id;
    document.getElementById('school-name').value = school.schoolName || school.name || '';
    document.getElementById('school-form-title').textContent = 'Edit School';
    document.getElementById('school-submit-btn').textContent = 'Update School';
    document.getElementById('school-cancel-btn').hidden = false;

    // Scroll form into view so the user knows edit mode kicked in
    document.getElementById('school-form').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ================================================================
   DELETE SCHOOL
   Confirms with the user before removing the row.
   ================================================================ */

async function deleteSchool(id) {
    const school = state.schools.find(s => s.id == id);
    if (!school) return;

    const schoolName = school.schoolName || school.name || 'this school';
    if (!confirm(`Delete "${schoolName}"? This action cannot be undone.`)) return;

    showGlobalLoader();
    try {
        const result = await apiFetch(getUrl('school-details-list'), {
            method: 'DELETE',
            body: JSON.stringify({ id })
        });

        if (result?.detail) {
            showToast(result.detail, 'danger');
        }

        await loadSchools();
        renderSchoolTable();
    } catch (error) {
        console.error('Failed to delete school:', error);
        showToast('Failed to delete school: ' + error.message, 'danger');
    } finally {
        hideGlobalLoader();
    }
}

/* ================================================================
   RENDER TABLE
   Applies the search filter, updates the record count, and paints
   one row per matching school.
   ================================================================ */

function renderSchoolTable() {
    const tbody = document.getElementById('school-table-body');
    const all = state.schools;

    // Update the record count pill
    document.getElementById('school-count').textContent =
        `${state.totalCount} school${state.totalCount === 1 ? '' : 's'}`;

    // Empty state
    if (all.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="table-empty">
                    No schools yet. Add your first one above.
                </td>
            </tr>
        `;
        updatePagination();
        return;
    }

    tbody.innerHTML = all.map((school, index) => {
        const createdOn = school.created_on
            ? new Date(school.created_on).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
            : '—';

        return `
            <tr data-id="${school.id}">
                <td>${index + 1}</td>
                <td>${school.schoolName || school.name || ''}</td>
                <td>${createdOn}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-icon" title="Edit" onclick="editSchool('${school.id}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"></path>
                            </svg>
                        </button>
                        <button class="btn-icon btn-icon-danger" title="Delete" onclick="deleteSchool('${school.id}')">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    updatePagination();
}

/* ================================================================
   PAGINATION
   ================================================================ */

function updatePagination() {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    const pageNumbers = document.getElementById('page-numbers');
    const paginationStart = document.getElementById('pagination-start');
    const paginationEnd = document.getElementById('pagination-end');
    const paginationTotal = document.getElementById('pagination-total');

    const page = state.currentPage;
    const totalPages = state.totalPages;
    const count = state.totalCount;
    const pageSize = state.pageSize;

    if (paginationStart) paginationStart.textContent = count ? (page - 1) * pageSize + 1 : 0;
    if (paginationEnd) paginationEnd.textContent = Math.min(page * pageSize, count || 0);
    if (paginationTotal) paginationTotal.textContent = count || 0;

    if (prevBtn) prevBtn.disabled = page === 1;
    if (nextBtn) nextBtn.disabled = page === totalPages;

    if (!pageNumbers) return;
    pageNumbers.innerHTML = '';

    let startPage = Math.max(1, page - 2);
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
    state.currentPage = page;
    loadSchools();
}