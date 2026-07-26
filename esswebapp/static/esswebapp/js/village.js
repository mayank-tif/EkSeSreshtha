/**
 * Village Management - CRUD operations with server-side pagination & search
 * Uses common.js utilities: showGlobalLoader, hideGlobalLoader, renderPagination, getUrl, getCsrfToken, escapeHtml, formatDate, showToast, openModal, closeModal
 */

(() => {
    'use strict';

    // ── State ──────────────────────────────────────────────────────
    const state = {
        page: 1,
        pageSize: AppConfig.pageSize,
        search: '',
        districts: [],
        vidhanSabhas: [],
        panchayats: [],
        editingId: null
    };

    // ── DOM refs ──────────────────────────────────────────────────
    const els = {
        get tbody() { return document.getElementById('village-tbody'); },
        get search() { return document.getElementById('village-search'); },
        get pagination() { return document.getElementById('village-pagination'); },
        get recordCount() { return document.getElementById('village-record-count'); },
        get modal() { return document.getElementById('village-modal'); },
        get form() { return document.getElementById('village-form'); },
        get modalTitle() { return document.getElementById('village-modal-title'); },
        get nameInput() { return document.getElementById('village-name'); },
        get districtSelect() { return document.getElementById('village-district'); },
        get vsSelect() { return document.getElementById('village-vs'); },
        get panchayatSelect() { return document.getElementById('village-panchayat'); },
        get editingId() { return document.getElementById('village-editing-id'); },
        get addBtn() { return document.getElementById('add-village-btn'); },
        get cancelBtn() { return document.getElementById('village-cancel-btn'); }
    };

    // ── Init ──────────────────────────────────────────────────────
    async function init() {
        await loadDistrictsForDropdown();
        await fetchAndRender();
        bindEvents();
    }

    // Handle case where DOMContentAlready fired
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init().catch(err => console.error('Init error:', err));
    }

    // ── Event bindings ────────────────────────────────────────────
    function bindEvents() {
        // Search with debounce
        if (els.search) {
            let debounceTimer;
            els.search.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    state.page = 1;
                    fetchAndRender();
                }, 300);
            });
        }

        // Add button
        if (els.addBtn) els.addBtn.addEventListener('click', () => openAddModal());

        // Form submit
        if (els.form) els.form.addEventListener('submit', handleFormSubmit);

        // Cancel button
        if (els.cancelBtn) els.cancelBtn.addEventListener('click', () => closeModal('village-modal'));

        // Event delegation for edit/delete
        if (els.tbody) {
            els.tbody.addEventListener('click', handleTableActions);
        }

        // Cascading dropdowns - listen to both native change and Select2 events
        if (els.districtSelect) {
            // Native change (works for Select2 too)
            els.districtSelect.addEventListener('change', onDistrictChange);
            // Select2 specific event
            $(els.districtSelect).on('select2:select', onDistrictChange);
        }
        if (els.vsSelect) {
            els.vsSelect.addEventListener('change', onVsChange);
            // Select2 specific event
            $(els.vsSelect).on('select2:select', onVsChange);
        }
    }

    // ── Load districts for dropdown ───────────────────────────────
    async function loadDistrictsForDropdown() {
        try {
            showGlobalLoader();
            const url = getUrl('district') + '?page=1&page_size=1000';
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            state.districts = data.results || [];

            if (els.districtSelect) {
                els.districtSelect.innerHTML = '<option value="">Select district</option>';
                state.districts.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    opt.textContent = escapeHtml(d.name);
                    els.districtSelect.appendChild(opt);
                });
                // Initialize Select2 on district dropdown
                if ($.fn.select2) {
                    $(els.districtSelect).select2({
                        placeholder: 'Select district',
                        allowClear: true,
                        width: '100%',
                        dropdownParent: $(els.modal)
                    });
                }
            }
        } catch (e) {
            console.error('Failed to load districts:', e);
            showToast('Failed to load districts', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    // ── District change -> fetch Vidhan Sabhas ────────────────────
    async function onDistrictChange() {
        const districtId = els.districtSelect.value;
        resetVsDropdown();
        resetPanchayatDropdown();

        if (!districtId) return;

        try {
            showGlobalLoader();
            const url = getUrl('vidhan-sabha') + '?page_size=500&district_id=' + districtId;
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            state.vidhanSabhas = data.results || [];

            populateVsDropdown(state.vidhanSabhas);
        } catch (e) {
            console.error('Failed to load Vidhan Sabhas:', e);
            showToast('Failed to load Vidhan Sabhas', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    // ── VS change -> fetch Panchayats ────────────────────────────
    async function onVsChange() {
        const districtId = els.districtSelect.value;
        const vsId = els.vsSelect.value;

        resetPanchayatDropdown();

        if (!vsId) return;

        try {
            showGlobalLoader();
            const url = getUrl('panchayat') + '?page_size=500&district_id=' + districtId + '&vidhan_sabha_id=' + vsId;
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            state.panchayats = data.results || [];

            populatePanchayatDropdown(state.panchayats);
        } catch (e) {
            console.error('Failed to load Panchayats:', e);
            showToast('Failed to load Panchayats', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    function populateVsDropdown(vsList) {
        if (!els.vsSelect) return;
        // Destroy existing Select2 if present
        if ($.fn.select2 && $(els.vsSelect).data('select2')) {
            $(els.vsSelect).select2('destroy');
        }
        els.vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
        vsList.forEach(vs => {
            const opt = document.createElement('option');
            opt.value = vs.id;
            opt.textContent = escapeHtml(vs.name);
            els.vsSelect.appendChild(opt);
        });
        els.vsSelect.disabled = false;
        // Initialize Select2
        $(els.vsSelect).select2({
            placeholder: 'Select Vidhan Sabha',
            allowClear: true,
            width: '100%',
            dropdownParent: $(els.modal)
        });
    }

    function resetVsDropdown() {
        if (els.vsSelect) {
            els.vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
            els.vsSelect.disabled = true;
            // Check if Select2 is initialized before destroying
            if ($.fn.select2 && $(els.vsSelect).data('select2')) {
                $(els.vsSelect).select2('destroy');
            }
            $(els.vsSelect).select2({
                placeholder: 'Select Vidhan Sabha',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.modal)
            });
        }
    }

    function populatePanchayatDropdown(pList) {
        if (!els.panchayatSelect) return;
        // Destroy existing Select2
        if ($.fn.select2 && $(els.panchayatSelect).data('select2')) {
            $(els.panchayatSelect).select2('destroy');
        }
        els.panchayatSelect.innerHTML = '<option value="">Select Panchayat</option>';
        pList.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = escapeHtml(p.name);
            els.panchayatSelect.appendChild(opt);
        });
        els.panchayatSelect.disabled = false;
        // Initialize Select2
        $(els.panchayatSelect).select2({
            placeholder: 'Select Panchayat',
            allowClear: true,
            width: '100%',
            dropdownParent: $(els.modal)
        });
    }

    function resetPanchayatDropdown() {
        if (els.panchayatSelect) {
            els.panchayatSelect.innerHTML = '<option value="">Select Panchayat</option>';
            els.panchayatSelect.disabled = true;
            // Check if Select2 is initialized before destroying
            if ($.fn.select2 && $(els.panchayatSelect).data('select2')) {
                $(els.panchayatSelect).select2('destroy');
            }
            $(els.panchayatSelect).select2({
                placeholder: 'Select Panchayat',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.modal)
            });
        }
    }

    function resetDistrictDropdown() {
        if (els.districtSelect) {
            // Check if Select2 is initialized before destroying
            if ($.fn.select2 && $(els.districtSelect).data('select2')) {
                $(els.districtSelect).select2('destroy');
            }
            $(els.districtSelect).select2({
                placeholder: 'Select district',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.modal)
            });
        }
    }

    // ── Fetch & render ────────────────────────────────────────────
    async function fetchAndRender() {
        showGlobalLoader();
        try {
            const search = els.search ? els.search.value.trim() : '';
            const params = new URLSearchParams({
                page: state.page,
                page_size: state.pageSize,
                search
            });
            const url = getUrl('village') + '?' + params.toString();
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();

            renderTable(data.results || []);
            renderPaginationEl(data);
            if (els.recordCount) els.recordCount.textContent = data.count || 0;
        } catch (e) {
            console.error('Fetch failed:', e);
            showToast('Failed to load Villages', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    function renderTable(items) {
        if (!els.tbody) return;
        if (!items.length) {
            els.tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="padding: 2rem;">No Villages found</td></tr>`;
            return;
        }
        const startIndex = (state.page - 1) * state.pageSize;
        els.tbody.innerHTML = items.map((v, i) => `
            <tr>
                <td>${startIndex + i + 1}</td>
                <td>${escapeHtml(v.name)}</td>
                <td>${escapeHtml(v.panchayat_name || '—')}</td>
                <td>${escapeHtml(v.vidhan_sabha_name || '—')}</td>
                <td>${escapeHtml(v.district_name || '—')}</td>
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

    // ── Table actions (edit / delete) ────────────────────────────
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
                deleteVillage(id);
            }
        }
    }

    // ── Modal handling ───────────────────────────────────────────
    function openAddModal() {
        resetForm();
        if (els.modalTitle) els.modalTitle.textContent = 'Add Village';
        resetDistrictDropdown();
        resetVsDropdown();
        resetPanchayatDropdown();
        openModal('village-modal');
        if (els.nameInput) els.nameInput.focus();
    }

    async function openEditModal(id) {
        showGlobalLoader();
        try {
            const url = getUrl('village') + '?id=' + id;
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

            resetForm();
            if (els.modalTitle) els.modalTitle.textContent = 'Edit Village';
            if (els.nameInput) els.nameInput.value = data.name || '';
            if (els.districtSelect) {
                els.districtSelect.value = data.district_id || '';
                $(els.districtSelect).val(data.district_id || '');
                // Update Select2 display
                $(els.districtSelect).trigger('change.select2');
            }
            if (els.editingId) els.editingId.value = data.id;

            // Load cascading dropdowns
            if (data.district_id) {
                await loadCascadingForEdit(data.district_id, data.vidhan_sabha_id, data.panchayat_id);
            }

            openModal('village-modal');
            if (els.nameInput) els.nameInput.focus();
        } catch (e) {
            console.error('Edit fetch failed:', e);
            showToast('Failed to load Village details', 'error');
        } finally {
            hideGlobalLoader();
        }
    }

    async function loadCascadingForEdit(districtId, selectedVsId, selectedPanchayatId) {
        try {
            // Load Vidhan Sabhas
            const vsUrl = getUrl('vidhan-sabha') + '?page_size=500&district_id=' + districtId;
            const vsRes = await fetch(vsUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const vsData = await vsRes.json();
            state.vidhanSabhas = vsData.results || [];
            populateVsDropdown(state.vidhanSabhas);
            if (els.vsSelect) {
                // Use setTimeout to ensure Select2 is fully initialized after populateVsDropdown
                setTimeout(() => {
                    $(els.vsSelect).val(selectedVsId || '').trigger('change');
                }, 0);
            }

            // Load Panchayats
            if (selectedVsId) {
                const pUrl = getUrl('panchayat') + '?page_size=500&district_id=' + districtId + '&vidhan_sabha_id=' + selectedVsId;
                const pRes = await fetch(pUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const pData = await pRes.json();
                state.panchayats = pData.results || [];
                populatePanchayatDropdown(state.panchayats);
                if (els.panchayatSelect) {
                    setTimeout(() => {
                        $(els.panchayatSelect).val(selectedPanchayatId || '').trigger('change');
                    }, 0);
                }
            }
        } catch (e) {
            console.error('Failed to load cascading dropdowns for edit:', e);
        }
    }

    function resetForm() {
        if (els.form) els.form.reset();
        if (els.editingId) els.editingId.value = '';
        state.editingId = null;
        if (els.districtSelect) els.districtSelect.value = '';
        resetDistrictDropdown();
        resetVsDropdown();
        resetPanchayatDropdown();
    }

    // ── Form submit (create / update) ────────────────────────────
    async function handleFormSubmit(e) {
        e.preventDefault();
        const name = els.nameInput ? els.nameInput.value.trim() : '';
        const districtId = els.districtSelect ? els.districtSelect.value : '';
        const vsId = els.vsSelect ? els.vsSelect.value : '';
        const panchayatId = els.panchayatSelect ? els.panchayatSelect.value : '';
        const editingId = els.editingId ? els.editingId.value : '';

        if (!name) { showToast('Please enter a name', 'error'); return; }
        if (!districtId) { showToast('Please select a district', 'error'); return; }
        if (!vsId) { showToast('Please select a Vidhan Sabha', 'error'); return; }
        if (!panchayatId) { showToast('Please select a Panchayat', 'error'); return; }

        const payload = {
            name,
            district_id: parseInt(districtId, 10),
            vidhan_sabha_id: parseInt(vsId, 10),
            panchayat_id: parseInt(panchayatId, 10)
        };
        const isEdit = !!editingId;
        if (isEdit) payload.id = parseInt(editingId, 10);

        showGlobalLoader();
        try {
            const url = getUrl('village');
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
                showToast(isEdit ? 'Village updated' : 'Village created', 'success');
                closeModal('village-modal');
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

    // ── Delete (soft) ────────────────────────────────────────────
    async function deleteVillage(id) {
        showGlobalLoader();
        try {
            const url = getUrl('village');
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
                showToast('Village deleted', 'success');
                if (state.page > 1) {
                    const checkUrl = getUrl('village') + `?page=${state.page}&page_size=${state.pageSize}`;
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
})();