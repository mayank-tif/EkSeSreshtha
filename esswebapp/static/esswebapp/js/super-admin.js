/* ================================================================
   EK SE SRESHTHA - SUPER ADMIN PAGE SCRIPT
   ----------------------------------------------------------------
   Manages Super Admin accounts: fetch, search, pagination,
   and CRUD via modal forms. Uses common.js utilities.
   ================================================================ */

// ── State ─────────────────────────────────────────────────────────
const state = {
    page: 1,
    pageSize: AppConfig.pageSize,
    search: '',
    editingId: null
};

// ── DOM References ────────────────────────────────────────────────
const els = {
    get search() { return document.getElementById('sa-search'); },
    get list() { return document.getElementById('sa-list'); },
    get pagination() { return document.getElementById('sa-pagination'); },
    get pageNumbers() { return document.getElementById('sa-page-numbers'); },
    get total() { return document.getElementById('sa-total-super-admins'); },
    get start() { return document.getElementById('sa-pagination-start'); },
    get end() { return document.getElementById('sa-pagination-end'); },

    get form() { return document.getElementById('sa-form'); },
    get formTitle() { return document.getElementById('sa-form-title'); },
    get name() { return document.getElementById('sa-name'); },
    get email() { return document.getElementById('sa-email'); },
    get enrolment() { return document.getElementById('sa-enrolment'); },
    get phone() { return document.getElementById('sa-phone'); },
    get whatsapp() { return document.getElementById('sa-whatsapp'); },
    get password() { return document.getElementById('sa-password'); },
    get confirmPassword() { return document.getElementById('sa-confirm-password'); },
    get image() { return document.getElementById('sa-image'); },
    get imagePreview() { return document.getElementById('sa-image-preview'); },
    get imageData() { return document.getElementById('sa-image-data'); },
    get editingId() { return document.getElementById('sa-editing-id'); },
    get resetBtn() { return document.getElementById('sa-reset-btn'); }
};

// ── Init ──────────────────────────────────────────────────────────
async function init() {
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
    // Search with debounce
    if (els.search) {
        let debounceTimer;
        els.search.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                state.page = 1;
                state.search = els.search.value.trim().toLowerCase();
                fetchAndRender();
            }, AppConfig.debounceDelay);
        });
    }

    // Form submit
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    // Reset button
    if (els.resetBtn) els.resetBtn.addEventListener('click', resetForm);

    // Image preview
    if (els.image) els.image.addEventListener('change', handleImageChange);
}

// ── Image Preview ─────────────────────────────────────────────────
function handleImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Guard against oversized uploads (2 MB)
    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be under 2 MB.', 'error');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        els.imageData.value = dataUrl;
        els.imagePreview.innerHTML = `<img src="${dataUrl}" alt="Profile preview">`;
    };
    reader.readAsDataURL(file);
}

// ── Fetch & Render ────────────────────────────────────────────────
async function fetchAndRender() {
    showGlobalLoader();
    try {
        const params = new URLSearchParams({
            page: state.page,
            page_size: state.pageSize,
            search: state.search
        });
        const url = getUrl('super-admin') + '?' + params.toString();
        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        const data = await res.json();

        renderTable(data.results || []);
        renderPaginationEl(data);
        if (els.total) els.total.textContent = data.count || 0;
        if (els.start) els.start.textContent = ((state.page - 1) * state.pageSize) + 1;
        if (els.end) els.end.textContent = Math.min(state.page * state.pageSize, data.count || 0);
    } catch (e) {
        console.error('Fetch failed:', e);
        showToast('Failed to load Super Admins', 'error');
    } finally {
        hideGlobalLoader();
    }
}

function renderTable(items) {
    if (!els.list) return;
    if (!items.length) {
        els.list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👤</div>
                <div class="empty-state-title">No Super Admins found</div>
                <div class="empty-state-text">Add one using the form on the left.</div>
            </div>
        `;
        return;
    }
    els.list.innerHTML = items.map(sa => {
        const avatarHtml = sa.picture
            ? `<img src="${escapeHtml(sa.picture)}" alt="${escapeHtml(sa.name)}">`
            : getInitials(sa.name);

        return `
            <div class="user-list-item">
                <div class="avatar">${avatarHtml}</div>
                <div class="user-list-info">
                    <div class="user-list-name">${escapeHtml(sa.name)}</div>
                    <div class="user-list-meta">${escapeHtml(sa.email)} · ${escapeHtml(sa.phone_number || '')}</div>
                </div>
                <div class="user-list-actions">
                    <button class="row-action-btn btn-edit" data-id="${sa.id}" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn btn-delete danger" data-id="${sa.id}" data-name="${escapeHtml(sa.name)}" title="Delete">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// ── Pagination ────────────────────────────────────────────────────
function renderPaginationEl(data) {
    if (!els.pagination) return;
    renderPagination({
        currentPage: data.page,
        pageSize: data.page_size,
        totalItems: data.count,
        containerSelector: '#' + els.pagination.id,
        onPageChange: (page) => {
            state.page = page;
            fetchAndRender();
        }
    });
}

// ── Form Submit (Create / Update) ─────────────────────────────────
async function handleFormSubmit(e) {
    e.preventDefault();

    const editingId = els.editingId.value;
    const isEdit = !!editingId;

    // Collect form data
    const payload = {
        name: els.name.value.trim(),
        email: els.email.value.trim().toLowerCase(),
        enrolment_roll_id: els.enrolment.value.trim() || null,
        phone_number: els.phone.value.trim(),
        whats_app: els.whatsapp.value.trim() || null,
        password: els.password.value
    };

    // Validation
    if (!payload.name || !payload.email || !payload.phone_number) {
        showToast('Please fill in all required fields.', 'error');
        return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
        showToast('Please enter a valid email.', 'error');
        return;
    }
    if (!isEdit && !payload.password) {
        showToast('Password is required for new accounts.', 'error');
        return;
    }
    if (payload.password && payload.password.length < 8) {
        showToast('Password must be at least 8 characters.', 'error');
        return;
    }
    if (payload.password && payload.password !== els.confirmPassword.value) {
        showToast('Passwords do not match.', 'error');
        return;
    }

    // Include image data if present
    if (els.imageData.value) {
        payload.picture = els.imageData.value;
    }

    showGlobalLoader();
    try {
        const url = getUrl('super-admin');
        const method = isEdit ? 'PUT' : 'POST';
        const body = isEdit ? { ...payload, id: parseInt(editingId, 10) } : payload;

        const res = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(body)
        });
        const data = await res.json();

        if (res.ok || res.status === 201) {
            showToast(isEdit ? 'Super Admin updated' : 'Super Admin created', 'success');
            closeModal('sa-modal');
            resetForm();
            fetchAndRender();
        } else {
            showToast(data.detail || 'Operation failed', 'error');
        }
    } catch (e) {
        console.error('Submit error:', e);
        showToast('Request failed', 'error');
    } finally {
        hideGlobalLoader();
    }
}

// ── Edit / Delete (Event Delegation) ──────────────────────────────
document.addEventListener('click', async (e) => {
    // Edit button
    const editBtn = e.target.closest('.btn-edit');
    if (editBtn) {
        const id = parseInt(editBtn.dataset.id, 10);
        await openEditModal(id);
        return;
    }

    // Delete button
    const deleteBtn = e.target.closest('.btn-delete');
    if (deleteBtn) {
        const id = parseInt(deleteBtn.dataset.id, 10);
        const name = deleteBtn.dataset.name;
        if (confirm(`Delete Super Admin "${name}"? This will deactivate the account.`)) {
            await deleteSuperAdmin(id);
        }
        return;
    }
});

async function openEditModal(id) {
    showGlobalLoader();
    try {
        const url = getUrl('super-admin') + '?id=' + id;
        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

        resetForm();
        if (els.formTitle) els.formTitle.textContent = 'Edit Super Admin';
        els.editingId.value = data.id;

        els.name.value = data.name || '';
        els.email.value = data.email || '';
        els.enrolment.value = data.enrolment_roll_id || '';
        els.phone.value = data.phone_number || '';
        els.whatsapp.value = data.whats_app || '';

        // Passwords not loaded - user must retype to change
        els.password.value = '';
        els.confirmPassword.value = '';
        els.password.required = false;
        els.confirmPassword.required = false;

        // Show existing profile image if any
        if (data.picture) {
            els.imagePreview.innerHTML = `<img src="${escapeHtml(data.picture)}" alt="Profile">`;
            els.imageData.value = data.picture;
        }

        openModal('sa-modal');
        if (els.name) els.name.focus();
    } catch (e) {
        console.error('Edit fetch failed:', e);
        showToast('Failed to load Super Admin details', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function deleteSuperAdmin(id) {
    showGlobalLoader();
    try {
        const url = getUrl('super-admin');
        const res = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ id })
        });
        const data = await res.json();

        if (res.ok) {
            showToast('Super Admin deactivated', 'success');
            // If current page becomes empty, go back one page
            if (state.page > 1) {
                const checkUrl = getUrl('super-admin') + `?page=${state.page}&page_size=${state.pageSize}`;
                const checkRes = await fetch(checkUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const checkData = await checkRes.json();
                if (!checkData.results?.length) state.page--;
            }
            fetchAndRender();
        } else {
            showToast(data.detail || 'Delete failed', 'error');
        }
    } catch (e) {
        console.error('Delete error:', e);
        showToast('Request failed', 'error');
    } finally {
        hideGlobalLoader();
    }
}

// ── Reset Form ────────────────────────────────────────────────────
function resetForm() {
    if (els.form) els.form.reset();
    if (els.editingId) els.editingId.value = '';
    if (els.imageData) els.imageData.value = '';
    state.editingId = null;

    if (els.formTitle) els.formTitle.textContent = 'Register Super Admin';
    if (els.password) els.password.required = true;
    if (els.confirmPassword) els.confirmPassword.required = true;

    if (els.imagePreview) {
        els.imagePreview.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    }
}