/**
 * Vidhan Sabha Management - CRUD operations with server-side pagination & search
 * Uses common.js utilities: showGlobalLoader, hideGlobalLoader, renderPagination, getUrl, getCsrfToken, escapeHtml, formatDate, showToast, openModal, closeModal
 */
(function () {
    'use strict';

    // ────────────────────────────────────────────────────────────────
    // State
    // ────────────────────────────────────────────────────────────────
    const state = {
        page: 1,
        pageSize: AppConfig.pageSize,
        search: '',
        districts: [],           // cached list for dropdown
        editingId: null
    };

    // ────────────────────────────────────────────────────────────────
    // DOM refs - lazy getters (re-query after renderShell rebuilds DOM)
    // ────────────────────────────────────────────────────────────────
    const els = {
        get tbody() { return document.getElementById('vs-tbody'); },
        get search() { return document.getElementById('vs-search'); },
        get pagination() { return document.getElementById('vs-pagination'); },
        get recordCount() { return document.getElementById('vs-record-count'); },
        get modal() { return document.getElementById('vs-modal'); },
        get form() { return document.getElementById('vs-form'); },
        get modalTitle() { return document.getElementById('vs-modal-title'); },
        get nameInput() { return document.getElementById('vs-name'); },
        get districtSelect() { return document.getElementById('vs-district'); },
        get editingId() { return document.getElementById('vs-editing-id'); },
        get addBtn() { return document.getElementById('add-vs-btn'); },
        get cancelBtn() { return document.getElementById('vs-cancel-btn'); }
    };

    // ────────────────────────────────────────────────────────────────
    // Init
    // ────────────────────────────────────────────────────────────────
    async function init() {
        await loadDistrictsForDropdown();
        await fetchAndRender();

        // Event listeners - re-attach after renderShell rebuilds DOM
        bindEvents();
    }

    function bindEvents() {
        if (els.addBtn) els.addBtn.addEventListener('click', () => openAddModal());
        if (els.cancelBtn) els.cancelBtn.addEventListener('click', () => closeModal('vs-modal'));
        if (els.form) els.form.addEventListener('submit', handleFormSubmit);
        if (els.search) {
            els.search.addEventListener('input', debounce(() => {
                state.page = 1;
                fetchAndRender();
            }, 300));
        }

        // Event delegation for edit/delete buttons
        if (els.tbody) {
            els.tbody.addEventListener('click', handleTableActions);
        }
    }

    // Initialize when shell is ready
    function onShellReady() {
        // If shell already rendered (main-area exists), init immediately
        if (document.querySelector('.main-area')) {
            init();
        } else {
            // Otherwise wait for shell:rendered event from sidebar.js
            document.addEventListener('shell:rendered', init, { once: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onShellReady);
    } else {
        onShellReady();
    }

    // ────────────────────────────────────────────────────────────────
    // Load districts for dropdown
    // ────────────────────────────────────────────────────────────────
    async function loadDistrictsForDropdown() {
        try {
            const url = getUrl('district') + '?page=1&page_size=1000';
            const res = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await res.json();
            state.districts = data.results || [];

            // Populate dropdown
            if (els.districtSelect) {
                els.districtSelect.innerHTML = '<option value="">Select a district</option>';
                state.districts.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = d.name;
                    els.districtSelect.appendChild(opt);
                });
                // Initialize Select2
                $(els.districtSelect).select2({
                    placeholder: 'Select a district',
                    allowClear: true,
                    width: '100%',
                    dropdownParent: $(els.modal) // Ensure dropdown appears in modal
                });
            }
        } catch (e) {
            console.error('Failed to load districts:', e);
            showToast('Failed to load districts for dropdown', 'error');
        }
    }

    // ────────────────────────────────────────────────────────────────
    // Fetch & render
    // ────────────────────────────────────────────────────────────────
    async function fetchAndRender() {
        // Read search from input
        state.search = els.search ? els.search.value.trim() : '';
        showGlobalLoader();
        try {
            const params = new URLSearchParams({
                page: state.page,
                page_size: state.pageSize,
                search: state.search
            });
            const url = getUrl('vidhan-sabha') + '?' + params.toString();
            const res = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await res.json();

            renderTable(data.results || []);
            renderPaginationEl(data);
            if (els.recordCount) els.recordCount.textContent = data.count || 0;
        } catch (e) {
            console.error('Fetch error:', e);
            showToast('Failed to load Vidhan Sabhas', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    function renderTable(items) {
        if (!els.tbody) return;
        if (!items.length) {
            els.tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="padding: 2rem;">No Vidhan Sabhas found</td></tr>`;
            return;
        }

        const startIndex = (state.page - 1) * state.pageSize;
        els.tbody.innerHTML = items.map((v, i) => `
            <tr>
                <td>${startIndex + i + 1}</td>
                <td>${escapeHtml(v.name)}</td>
                <td>${escapeHtml(v.district_name || '—')}</td>
                <td>${v.panchayat_count || 0}</td>
                <td>${formatDate(v.created_on)}</td>
                <td>
                    <button class="btn btn-sm btn-ghost btn-edit" data-id="${v.id}" title="Edit">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="btn btn-sm btn-ghost btn-delete" data-id="${v.id}" data-name="${escapeHtml(v.name)}" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </td>
            </tr>
        `).join('');
    }

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

    // ────────────────────────────────────────────────────────────────
    // Table actions (edit / delete) - event delegation
    // ────────────────────────────────────────────────────────────────
    function handleTableActions(e) {
        const editBtn = e.target.closest('.btn-edit');
        const deleteBtn = e.target.closest('.btn-delete');

        if (editBtn) {
            const id = parseInt(editBtn.dataset.id, 10);
            openEditModal(id);
            return;
        }

        if (deleteBtn) {
            const id = parseInt(deleteBtn.dataset.id, 10);
            const name = deleteBtn.dataset.name;
            if (confirm(`Delete "${name}"? This will mark it as inactive.`)) {
                deleteVidhanSabha(id);
            }
        }
    }

    // ────────────────────────────────────────────────────────────────
    // Modal handling
    // ────────────────────────────────────────────────────────────────
    function openAddModal() {
        resetForm();
        if (els.modalTitle) els.modalTitle.textContent = 'Add Vidhan Sabha';
        openModal('vs-modal');
        if (els.nameInput) els.nameInput.focus();
    }

    async function openEditModal(id) {
        showGlobalLoader();
        try {
            const url = getUrl('vidhan-sabha') + '?id=' + id;
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

            resetForm();
            if (els.modalTitle) els.modalTitle.textContent = 'Edit Vidhan Sabha';
            if (els.nameInput) els.nameInput.value = data.name || '';
            if (els.districtSelect) {
                els.districtSelect.value = data.district_id || '';
                // Update Select2 to reflect the selected value
                $(els.districtSelect).val(data.district_id || '').trigger('change');
            }
            if (els.editingId) els.editingId.value = data.id;

            openModal('vs-modal');
            if (els.nameInput) els.nameInput.focus();
        } catch (e) {
            console.error('Edit fetch failed:', e);
            showToast('Failed to load Vidhan Sabha details', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    function resetForm() {
        if (els.form) els.form.reset();
        if (els.editingId) els.editingId.value = '';
        if (els.nameInput) els.nameInput.value = '';
        if (els.districtSelect) els.districtSelect.value = '';
        state.editingId = null;
    }

    // ────────────────────────────────────────────────────────────────
    // CRUD operations
    // ────────────────────────────────────────────────────────────────
    async function handleFormSubmit(e) {
        e.preventDefault();
        const name = els.nameInput ? els.nameInput.value.trim() : '';
        const districtId = els.districtSelect ? els.districtSelect.value : '';
        const editingId = els.editingId ? els.editingId.value : '';

        if (!name) { showToast('Please enter a name', 'error'); return; }
        if (!districtId) { showToast('Please select a district', 'error'); return; }

        const payload = { name, district_id: parseInt(districtId, 10) };
        const isEdit = !!editingId;
        if (isEdit) payload.id = parseInt(editingId, 10);

        showGlobalLoader();
        try {
            const url = getUrl('vidhan-sabha');
            const method = isEdit ? 'PUT' : 'POST';
            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (res.ok || res.status === 201) {
                showToast(isEdit ? 'Vidhan Sabha updated' : 'Vidhan Sabha created', 'success');
                closeModal('vs-modal');
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

    async function deleteVidhanSabha(id) {
        showGlobalLoader();
        try {
            const url = getUrl('vidhan-sabha');
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
                showToast('Vidhan Sabha deleted', 'success');
                // Adjust page if current page becomes empty
                if (state.page > 1) {
                    const checkUrl = getUrl('vidhan-sabha') + `?page=${state.page}&page_size=${state.pageSize}`;
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

    // ────────────────────────────────────────────────────────────────
    // Helpers
    // ────────────────────────────────────────────────────────────────
    function debounce(fn, delay) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    }

    // Expose for inline script if needed
    window.vidhanSabha = { fetchAndRender };
})();