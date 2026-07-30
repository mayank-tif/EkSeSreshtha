/* ================================================================
   EK SE SRESHTHA - EDUCATIONAL CENTRE PAGE SCRIPT
   ---------------------------------------------------------------
   Manages Educational Centres: fetch, search, pagination,
   and CRUD via API calls. Uses common.js utilities.
   Cascading dropdowns: District -> Vidhan Sabha -> Panchayat -> Village
   Map pin picker for latitude/longitude
   ================================================================ */

// ── State ─────────────────────────────────────────────────────────
const state = {
    page: 1,
    pageSize: AppConfig.pageSize,
    search: '',
    editingId: null,
    mapPin: { lat: null, lng: null }
};

// ── DOM References ────────────────────────────────────────────────
const els = {
    get search() { return document.getElementById('centre-search'); },
    get tbody() { return document.getElementById('centre-tbody'); },
    get count() { return document.getElementById('centre-count'); },
    get pagination() { return document.getElementById('centre-pagination'); },
    get pageNumbers() { return document.getElementById('centre-page-numbers'); },
    get total() { return document.getElementById('centre-total-centres'); },
    get start() { return document.getElementById('centre-pagination-start'); },
    get end() { return document.getElementById('centre-pagination-end'); },

    // Modal elements
    get modal() { return document.getElementById('centre-modal'); },
    get viewModal() { return document.getElementById('centre-view-modal'); },
    get form() { return document.getElementById('centre-form'); },
    get modalTitle() { return document.getElementById('centre-modal-title'); },
    get name() { return document.getElementById('centre-name'); },
    get startDate() { return document.getElementById('centre-start-date'); },
    get address() { return document.getElementById('centre-address'); },
    get lat() { return document.getElementById('centre-lat'); },
    get lng() { return document.getElementById('centre-lng'); },
    get district() { return document.getElementById('centre-district'); },
    get vs() { return document.getElementById('centre-vs'); },
    get panchayat() { return document.getElementById('centre-panchayat'); },
    get village() { return document.getElementById('centre-village'); },
    get ra() { return document.getElementById('centre-ra'); },
    get teacher() { return document.getElementById('centre-teacher'); },
    get editingId() { return document.getElementById('centre-editing-id'); },
    get addBtn() { return document.getElementById('add-centre-btn'); },
    get mapPin() { return document.getElementById('map-pin'); },
    get mapCanvas() { return document.getElementById('map-canvas'); },
    get viewBody() { return document.getElementById('centre-view-body'); }
};

// ── Init ──────────────────────────────────────────────────────────
async function init() {
    // Set default start date to today
    if (els.startDate) {
        const today = new Date().toISOString().split('T')[0];
        els.startDate.value = today;
    }

    await loadDistrictDropdown();
    await loadRegionalAdminDropdown();
    await loadTeacherDropdown();
    await fetchAndRender();
    bindEvents();
    initMapPicker();
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

    // Add button opens modal
    if (els.addBtn) els.addBtn.addEventListener('click', openAddModal);

    // Modal close buttons
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            closeModal(els.modal);
            closeModal(els.viewModal);
        });
    });

    // Event delegation for edit/view/delete buttons
    document.addEventListener('click', async (e) => {
        // Edit button
        const editBtn = e.target.closest('.btn-edit');
        if (editBtn) {
            const id = parseInt(editBtn.dataset.id, 10);
            await openEditModal(id);
            return;
        }

        // View button
        const viewBtn = e.target.closest('.btn-view');
        if (viewBtn) {
            const id = parseInt(viewBtn.dataset.id, 10);
            await openViewModal(id);
            return;
        }

        // Delete button
        const deleteBtn = e.target.closest('.btn-delete');
        if (deleteBtn) {
            const id = parseInt(deleteBtn.dataset.id, 10);
            const name = deleteBtn.dataset.name;
            if (confirm(`Deactivate centre "${name}"? This will deactivate the centre.`)) {
                await deleteCenter(id);
            }
            return;
        }
    });
}

// ── Map Pin Picker ────────────────────────────────────────────────
function initMapPicker() {
    const canvas = els.mapCanvas;
    const pin = els.mapPin;
    if (!canvas || !pin) return;

    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Calculate percentage position
        const pctX = x / rect.width;
        const pctY = y / rect.height;

        // Map to approximate lat/lng for India (Panipat area as default)
        // These are rough bounds - in production you'd use actual map tiles
        const lat = 29.0 + (1 - pctY) * 2.0;  // ~29.0 to 31.0
        const lng = 75.5 + pctX * 3.0;         // ~75.5 to 78.5

        state.mapPin = { lat, lng };

        // Position pin
        pin.style.left = `${pctX * 100}%`;
        pin.style.top = `${pctY * 100}%`;
        pin.hidden = false;

        // Update inputs
        if (els.lat) els.lat.value = lat.toFixed(6);
        if (els.lng) els.lng.value = lng.toFixed(6);
    });
}

// ── Cascading Dropdowns ───────────────────────────────────────────
// Guard flag: prevents cascade handlers from firing when values are
// set programmatically (edit modal pre-selection, form reset)
let suppressCascade = false;

// Initialize Select2 on a cascade dropdown and bind a namespaced change
// handler exactly once. Using jQuery 'change.cascade' covers BOTH
// 'select2:select' and 'select2:clear' (Select2 triggers native change).
function initCascadeSelect2(el, placeholder, onChange) {
    if (!el || !$.fn.select2) return;
    if ($(el).data('select2')) {
        $(el).select2('destroy');
    }
    $(el).select2({
        placeholder: placeholder,
        allowClear: true,
        width: '100%',
        dropdownParent: $(els.modal)
    });
    if (onChange) {
        $(el).off('change.cascade').on('change.cascade', function () {
            if (!suppressCascade) onChange();
        });
    }
}

// Reset a downstream dropdown to empty/disabled state and re-init
// Select2 so it stays styled (previously Select2 was destroyed but
// never re-created, leaving a broken plain <select>)
function resetChildSelect(el, placeholder, onChange) {
    if (!el) return;
    el.innerHTML = `<option value="">${placeholder}</option>`;
    el.disabled = true;
    initCascadeSelect2(el, placeholder, onChange);
}

// Set a dropdown value without triggering cascade handlers
function setSelectValue(el, value) {
    if (!el) return;
    suppressCascade = true;
    try {
        el.value = value;
        if ($.fn.select2 && $(el).data('select2')) {
            $(el).val(value).trigger('change');
        }
    } finally {
        suppressCascade = false;
    }
}

async function loadDistrictDropdown() {
    showGlobalLoader();
    try {
        const url = getUrl('district') + '?page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.district) return;
        els.district.innerHTML = '<option value="">Select district</option>' +
            (data.results || []).map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');

        initCascadeSelect2(els.district, 'Select district', onDistrictChange);
    } catch (e) {
        console.error('Failed to load districts:', e);
        showToast('Failed to load districts', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function onDistrictChange() {
    const districtId = els.district?.value;

    // Reset all downstream dropdowns (keeps Select2 styling intact)
    resetChildSelect(els.vs, 'Select Vidhan Sabha', onVsChange);
    resetChildSelect(els.panchayat, 'Select Panchayat', onPanchayatChange);
    resetChildSelect(els.village, 'Select Village', null);

    if (!districtId) return;

    showGlobalLoader();
    try {
        const url = getUrl('vidhan-sabha') + '?district_id=' + districtId + '&page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.vs) return;
        els.vs.innerHTML = '<option value="">Select Vidhan Sabha</option>' +
            (data.results || []).map(v =>
                `<option value="${v.id}">${escapeHtml(v.name)}</option>`
            ).join('');
        els.vs.disabled = false;
        initCascadeSelect2(els.vs, 'Select Vidhan Sabha', onVsChange);
    } catch (e) {
        console.error('Failed to load Vidhan Sabhas:', e);
        showToast('Failed to load Vidhan Sabhas', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function onVsChange() {
    const vsId = els.vs?.value;

    resetChildSelect(els.panchayat, 'Select Panchayat', onPanchayatChange);
    resetChildSelect(els.village, 'Select Village', null);

    if (!vsId) return;

    showGlobalLoader();
    try {
        const url = getUrl('panchayat') + '?vidhan_sabha_id=' + vsId + '&page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.panchayat) return;
        els.panchayat.innerHTML = '<option value="">Select Panchayat</option>' +
            (data.results || []).map(p =>
                `<option value="${p.id}">${escapeHtml(p.name)}</option>`
            ).join('');
        els.panchayat.disabled = false;
        initCascadeSelect2(els.panchayat, 'Select Panchayat', onPanchayatChange);
    } catch (e) {
        console.error('Failed to load Panchayats:', e);
        showToast('Failed to load Panchayats', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function onPanchayatChange() {
    const panchayatId = els.panchayat?.value;

    resetChildSelect(els.village, 'Select Village', null);

    if (!panchayatId) return;

    showGlobalLoader();
    try {
        const url = getUrl('village') + '?panchayat_id=' + panchayatId + '&page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.village) return;
        els.village.innerHTML = '<option value="">Select Village</option>' +
            (data.results || []).map(v =>
                `<option value="${v.id}">${escapeHtml(v.name)}</option>`
            ).join('');
        els.village.disabled = false;
        initCascadeSelect2(els.village, 'Select Village', null);
    } catch (e) {
        console.error('Failed to load Villages:', e);
        showToast('Failed to load Villages', 'error');
    } finally {
        hideGlobalLoader();
    }
}

// Load dropdowns for editing (with pre-selected values).
// Values are set with cascade suppressed, then each cascade is awaited
// sequentially - no setTimeout hacks, no double execution.
async function loadDropdownsForEdit(districtId, vsId, panchayatId, villageId) {
    if (!districtId) return;
    setSelectValue(els.district, districtId);
    await onDistrictChange();

    if (!vsId) return;
    setSelectValue(els.vs, vsId);
    await onVsChange();

    if (!panchayatId) return;
    setSelectValue(els.panchayat, panchayatId);
    await onPanchayatChange();

    if (!villageId) return;
    setSelectValue(els.village, villageId);
}

// Load Regional Admin dropdown
async function loadRegionalAdminDropdown() {
    try {
        const url = getUrl('regional-admin') + '?page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.ra) return;
        els.ra.innerHTML = '<option value="">Select Regional Admin</option>' +
            (data.results || []).map(ra =>
                `<option value="${ra.id}">${escapeHtml(ra.name)} (${escapeHtml(ra.district_name || '')} / ${escapeHtml(ra.vidhan_sabha_name || '')})</option>`
            ).join('');

        if ($.fn.select2 && $(els.ra).data('select2')) {
            $(els.ra).select2('destroy');
        }
        if ($.fn.select2) {
            $(els.ra).select2({
                placeholder: 'Select Regional Admin',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.modal)
            });
        }
    } catch (e) {
        console.error('Failed to load Regional Admins:', e);
    }
}

// Load Teacher dropdown
async function loadTeacherDropdown() {
    try {
        const url = getUrl('teacher') + '?page=1&page_size=1000';
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        if (!els.teacher) return;
        els.teacher.innerHTML = '<option value="">Select Teacher</option>' +
            (data.results || []).map(t =>
                `<option value="${t.id}">${escapeHtml(t.name)} (${escapeHtml(t.village_name || 'No village')})</option>`
            ).join('');

        if ($.fn.select2 && $(els.teacher).data('select2')) {
            $(els.teacher).select2('destroy');
        }
        if ($.fn.select2) {
            $(els.teacher).select2({
                placeholder: 'Select Teacher',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.modal)
            });
        }
    } catch (e) {
        console.error('Failed to load Teachers:', e);
    }
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
        const url = getUrl('centres') + '?' + params.toString();
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        renderTable(data.results || []);
        renderPaginationEl(data);
        if (els.total) els.total.textContent = data.count || 0;
        if (els.start) els.start.textContent = ((state.page - 1) * state.pageSize) + 1;
        if (els.end) els.end.textContent = Math.min(state.page * state.pageSize, data.count || 0);
        if (els.count) els.count.textContent = data.count || 0;
    } catch (e) {
        console.error('Fetch failed:', e);
        showToast('Failed to load Centres', 'error');
    } finally {
        hideGlobalLoader();
    }
}

function renderTable(items) {
    if (!els.tbody) return;
    if (!items.length) {
        els.tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state-cell">
                    <div class="empty-state">
                        <div class="empty-state-icon">🏫</div>
                        <div class="empty-state-title">No Centres found</div>
                        <div class="empty-state-text">Add one using the "Add Centre" button.</div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    els.tbody.innerHTML = items.map((c, i) => {
        const rowNum = (state.page - 1) * state.pageSize + i + 1;
        return `
            <tr>
                <td class="row-index">${rowNum}</td>
                <td><strong>${escapeHtml(c.center_name || '')}</strong></td>
                <td>${escapeHtml(c.village_name || '—')}</td>
                <td>${escapeHtml(c.assigned_regional_admin_name || 'Unassigned')}</td>
                <td>${escapeHtml(c.assigned_teacher_name || 'Unassigned')}</td>
                <td><span class="count-pill">${c.student_count || 0}</span></td>
                <td>${c.started_date ? formatDate(c.started_date) : '—'}</td>
                <td>
                    <div class="table-actions">
                        <button class="row-action-btn view btn-view" data-id="${c.id}" title="View details">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                        <button class="row-action-btn btn-edit" data-id="${c.id}" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="row-action-btn danger btn-delete" data-id="${c.id}" data-name="${escapeHtml(c.center_name)}" title="Deactivate">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
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

// ── Form Submit (Create / Update) ─────────────────────────────────
async function handleFormSubmit(e) {
    e.preventDefault();

    const editingId = els.editingId.value;
    const isEdit = !!editingId;

    const payload = {
        center_name: els.name.value.trim(),
        address: els.address.value.trim(),
        started_date: els.startDate.value || null,
        latitude: els.lat.value ? parseFloat(els.lat.value) : null,
        longitude: els.lng.value ? parseFloat(els.lng.value) : null,
        district_id: els.district.value ? parseInt(els.district.value, 10) : null,
        vidhan_sabha_id: els.vs.value ? parseInt(els.vs.value, 10) : null,
        panchayat_id: els.panchayat.value ? parseInt(els.panchayat.value, 10) : null,
        village_id: els.village.value ? parseInt(els.village.value, 10) : null,
        assigned_regional_admin: els.ra.value ? parseInt(els.ra.value, 10) : null,
        assigned_teachers: els.teacher.value ? parseInt(els.teacher.value, 10) : null,
        class_status: true
    };

    // Validation
    if (!payload.center_name || !payload.address) {
        showToast('Please fill in all required fields.', 'error');
        return;
    }
    if (!payload.district_id || !payload.vidhan_sabha_id || !payload.panchayat_id || !payload.village_id) {
        showToast('Please select District, Vidhan Sabha, Panchayat, and Village.', 'error');
        return;
    }

    showGlobalLoader();
    try {
        const url = getUrl('centres');
        const method = isEdit ? 'PUT' : 'POST';
        const body = isEdit ? { ...payload, id: parseInt(editingId, 10) } : payload;

        const res = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify(body)
        });
        const data = await res.json();

        if (res.ok || res.status === 201) {
            showToast(isEdit ? 'Centre updated' : 'Centre created', 'success');
            closeModal(els.modal);
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

// ── Edit / View / Delete ──────────────────────────────────────────
async function openEditModal(id) {
    showGlobalLoader();
    try {
        const url = getUrl('centres') + '?id=' + id;
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

        resetForm();
        if (els.modalTitle) els.modalTitle.textContent = 'Edit Educational Centre';
        els.editingId.value = data.id;

        els.name.value = data.center_name || '';
        els.startDate.value = data.started_date ? data.started_date.split('T')[0] : '';
        els.address.value = data.address || '';
        els.lat.value = data.latitude || '';
        els.lng.value = data.longitude || '';

        // Load cascading dropdowns with pre-selected values
        await loadDropdownsForEdit(data.district_id, data.vidhan_sabha_id, data.panchayat_id, data.village_id);

        // Position map pin
        if (data.latitude && data.longitude && els.mapPin && els.mapCanvas) {
            // Calculate percentage from lat/lng (reverse of initMapPicker)
            const lat = parseFloat(data.latitude);
            const lng = parseFloat(data.longitude);
            const pctX = (lng - 75.5) / 3.0;
            const pctY = 1 - (lat - 29.0) / 2.0;

            els.mapPin.style.left = `${Math.max(0, Math.min(100, pctX * 100))}%`;
            els.mapPin.style.top = `${Math.max(0, Math.min(100, pctY * 100))}%`;
            els.mapPin.hidden = false;
            state.mapPin = { lat, lng };
        }

        openModal(els.modal);
        if (els.name) els.name.focus();

        // Set dropdown values AFTER modal is open (required for Select2 dropdownParent)
        if (data.assigned_regional_admin) {
            setSelectValue(els.ra, data.assigned_regional_admin);
        }
        if (data.assigned_teachers) {
            setSelectValue(els.teacher, data.assigned_teachers);
        }
    } catch (e) {
        console.error('Edit fetch failed:', e);
        showToast('Failed to load Centre details', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function openViewModal(id) {
    showGlobalLoader();
    try {
        const url = getUrl('centres') + '?id=' + id;
        const res = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

        const html = `
            <div class="centre-details">

                <!-- Header banner -->
                <div class="centre-details-hero">
                    <div class="centre-details-hero-icon">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M3 21h18M5 21V7l7-4 7 4v14"/></svg>
                    </div>
                    <div class="centre-details-hero-info">
                        <h2>${escapeHtml(data.center_name || '')}</h2>
                        <p>Started ${data.started_date ? formatDate(data.started_date) : '—'}</p>
                    </div>
                    <div class="centre-details-hero-stat">
                        <div class="centre-details-hero-stat-number">${data.student_count || 0}</div>
                        <div class="centre-details-hero-stat-label">Students</div>
                    </div>
                </div>

                <!-- Location grid -->
                <div class="centre-details-section">
                    <h4>Location</h4>
                    <div class="centre-info-grid">
                        <div class="centre-info-item">
                            <div class="centre-info-label">District</div>
                            <div class="centre-info-value">${escapeHtml(data.district_name || '—')}</div>
                        </div>
                        <div class="centre-info-item">
                            <div class="centre-info-label">Vidhan Sabha</div>
                            <div class="centre-info-value">${escapeHtml(data.vidhan_sabha_name || '—')}</div>
                        </div>
                        <div class="centre-info-item">
                            <div class="centre-info-label">Panchayat</div>
                            <div class="centre-info-value">${escapeHtml(data.panchayat_name || '—')}</div>
                        </div>
                        <div class="centre-info-item">
                            <div class="centre-info-label">Village</div>
                            <div class="centre-info-value">${escapeHtml(data.village_name || '—')}</div>
                        </div>
                        <div class="centre-info-item">
                            <div class="centre-info-label">Coordinates</div>
                            <div class="centre-info-value">${data.latitude && data.longitude
                                ? `${parseFloat(data.latitude).toFixed(6)}°, ${parseFloat(data.longitude).toFixed(6)}°`
                                : '—'}</div>
                        </div>
                    </div>
                </div>

                <!-- Staff assignments -->
                <div class="centre-details-section">
                    <h4>Assigned Staff</h4>
                    <div class="centre-info-grid">
                        <div class="centre-info-item">
                            <div class="centre-info-label">Regional Admin</div>
                            <div class="centre-info-value">${escapeHtml(data.assigned_regional_admin_name || 'Unassigned')}</div>
                        </div>
                        <div class="centre-info-item">
                            <div class="centre-info-label">Teacher</div>
                            <div class="centre-info-value">${escapeHtml(data.assigned_teacher_name || 'Unassigned')}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (els.viewBody) els.viewBody.innerHTML = html;
        openModal(els.viewModal);
    } catch (e) {
        console.error('View fetch failed:', e);
        showToast('Failed to load Centre details', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function deleteCenter(id) {
    showGlobalLoader();
    try {
        const url = getUrl('centres');
        const res = await fetch(url, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ id })
        });
        const data = await res.json();

        if (res.ok) {
            showToast('Centre deactivated', 'success');
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

// ── Reset / Open / Close Modal ────────────────────────────────────
function openAddModal() {
    resetForm();
    if (els.modalTitle) els.modalTitle.textContent = 'Add Educational Centre';
    // Set default start date to today
    if (els.startDate) {
        const today = new Date().toISOString().split('T')[0];
        els.startDate.value = today;
    }
    openModal(els.modal);
}

function resetForm() {
    if (els.form) els.form.reset();
    if (els.editingId) els.editingId.value = '';
    if (els.modalTitle) els.modalTitle.textContent = 'Add Educational Centre';

    // Reset map pin
    if (els.mapPin) {
        els.mapPin.hidden = true;
        state.mapPin = { lat: null, lng: null };
    }

    // Reset cascading dropdowns (suppressed so no cascade/API calls fire)
    setSelectValue(els.district, '');
    resetChildSelect(els.vs, 'Select Vidhan Sabha', onVsChange);
    resetChildSelect(els.panchayat, 'Select Panchayat', onPanchayatChange);
    resetChildSelect(els.village, 'Select Village', null);

    // Reset RA and Teacher dropdowns
    setSelectValue(els.ra, '');
    setSelectValue(els.teacher, '');

    // Set default start date
    if (els.startDate) {
        const today = new Date().toISOString().split('T')[0];
        els.startDate.value = today;
    }
}

function openModal(modal) {
    if (!modal) return;
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (!el) return;
    el.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(modal) {
    if (!modal) return;
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (!el) return;
    el.classList.remove('active');
    document.body.style.overflow = '';
}