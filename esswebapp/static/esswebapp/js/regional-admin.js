/* ================================================================
   EK SE SRESHTHA - REGIONAL ADMIN PAGE SCRIPT
   ---------------------------------------------------------------
   Manages Regional Admin accounts: fetch, search, pagination,
   and CRUD via API calls. Uses common.js utilities.
   Left form handles both Add and Edit. Cascading dropdowns:
   District -> Vidhan Sabha -> Panchayat
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
    get search() { return document.getElementById('ra-search'); },
    get list() { return document.getElementById('ra-list'); },
    get countLabel() { return document.getElementById('ra-count-label'); },
    get pagination() { return document.getElementById('ra-pagination'); },
    get pageNumbers() { return document.getElementById('ra-page-numbers'); },
    get total() { return document.getElementById('ra-total-regional-admins'); },
    get start() { return document.getElementById('ra-pagination-start'); },
    get end() { return document.getElementById('ra-pagination-end'); },

    get form() { return document.getElementById('ra-form'); },
    get formTitle() { return document.getElementById('ra-form-title'); },
    get name() { return document.getElementById('ra-name'); },
    get email() { return document.getElementById('ra-email'); },
    get age() { return document.getElementById('ra-age'); },
    get gender() { return document.getElementById('ra-gender'); },
    get dob() { return document.getElementById('ra-dob'); },
    get enrollment() { return document.getElementById('ra-enrollment'); },
    get phone() { return document.getElementById('ra-phone'); },
    get whatsapp() { return document.getElementById('ra-whatsapp'); },

    get district() { return document.getElementById('ra-district'); },
    get vs() { return document.getElementById('ra-vs'); },
    get panchayat() { return document.getElementById('ra-panchayat'); },

    get password() { return document.getElementById('ra-password'); },
    get confirmPassword() { return document.getElementById('ra-confirm-password'); },
    get image() { return document.getElementById('ra-image'); },
    get imagePreview() { return document.getElementById('ra-image-preview'); },
    get imageData() { return document.getElementById('ra-image-data'); },
    get editingId() { return document.getElementById('ra-editing-id'); }
};

// ── Init ──────────────────────────────────────────────────────────
async function init() {
    await loadDistrictDropdown();
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
            }, 300);
        });
    }

    // Form submit
    if (els.form) els.form.addEventListener('submit', handleFormSubmit);

    // Reset button - using inline onclick from template
    // Image preview
    if (els.image) els.image.addEventListener('change', handleImageChange);
}

// Global functions called from template inline handlers
window.onRaDistrictChange = onDistrictChange;
window.resetRegionalAdminForm = resetForm;

// ── Image Preview ─────────────────────────────────────────────────
function handleImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be under 2 MB.', 'error');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        els.imageData.value = dataUrl;
        if (els.imagePreview) {
            els.imagePreview.innerHTML = `<img src="${dataUrl}" alt="Profile preview">`;
        }
    };
    reader.readAsDataURL(file);
}

// ── Cascading Dropdowns ──

// Checkbox-style multi-select (select2 with checkbox in every option row)
function multiSelectTemplates($select, marker) {
    return {
        templateResult: (state) => {
            if (!state.id) return state.text; // placeholder
            const checked = ($select.val() || []).includes(String(state.id)) ? 'checked' : '';
            return $('<span><input type="checkbox" ' + marker + '="' + String(state.id) + '" ' + checked +
                ' style="margin-right:8px;vertical-align:middle;">' + escapeHtml(state.text) + '</span>');
        },
        templateSelection: (state) => state.text
    };
}

// Show "N selected" inside the closed select2 box instead of individual tag chips
function applyCountSummary($select) {
    const render = () => {
        const inst = $select.data('select2');
        if (!inst || !inst.$selection) return;
        const $rendered = inst.$selection.find('.select2-selection__rendered');
        const count = ($select.val() || []).length;
        $rendered.find('li.select2-selection__choice').hide();
        $rendered.find('.ra-count-item').remove();
        if (count > 0) {
            $rendered.prepend($('<li class="select2-selection__choice ra-count-item">' +
                count + ' selected</li>'));
        }
    };
    $select.off('change.raCount').on('change.raCount', render);
    render();
}

function bindMultiCheckboxSync($select, marker) {
    // namespaced + de-duplicated so repeated re-inits never stack handlers
    $select.off('select2:select.raCb select2:unselect.raCb');
    const toggle = (id, checked) => {
        const inst = $select.data('select2');
        if (inst && inst.$dropdown) {
            inst.$dropdown.find('input[' + marker + '="' + String(id) + '"]').prop('checked', checked);
        }
    };
    $select.on('select2:select.raCb', (e) => toggle(e.params.data.id, true));
    $select.on('select2:unselect.raCb', (e) => toggle(e.params.data.id, false));
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

        if ($.fn.select2 && $(els.district).data('select2')) {
            $(els.district).select2('destroy');
        }
        if ($.fn.select2) {
            $(els.district).select2({
                placeholder: 'Select district',
                allowClear: true,
                width: '100%',
                dropdownParent: $(els.district).parent()
            });
            $(els.district).off('select2:select').on('select2:select', onDistrictChange);
        }
    } catch (e) {
        console.error('Failed to load districts:', e);
        showToast('Failed to load districts', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function onDistrictChange() {
    const districtId = els.district?.value;

    // Reset children
    if (els.vs) {
        els.vs.innerHTML = '<option value="">Select Vidhan Sabha</option>';
        els.vs.disabled = true;
        if ($.fn.select2 && $(els.vs).data('select2')) {
            $(els.vs).select2('destroy');
        }
    }
    if (els.panchayat) {
        els.panchayat.innerHTML = '<option value="">Select Panchayat</option>';
        els.panchayat.disabled = true;
        if ($.fn.select2 && $(els.panchayat).data('select2')) {
            $(els.panchayat).select2('destroy');
        }
    }

    if (!districtId) return;

    showGlobalLoader();
    try {
        // 1) Vidhan Sabha options for this district
        const vsUrl = getUrl('vidhan-sabha') + '?district_id=' + districtId + '&page=1&page_size=1000';
        const vsRes = await fetch(vsUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const vsData = await vsRes.json();

        if (!els.vs) return;
        els.vs.innerHTML += (vsData.results || []).map(v =>
            `<option value="${v.id}">${escapeHtml(v.name)}</option>`
        ).join('');
        els.vs.disabled = false;

        if ($.fn.select2 && $(els.vs).data('select2')) {
            $(els.vs).select2('destroy');
        }
        if ($.fn.select2) {
            $(els.vs).select2(Object.assign({
                placeholder: 'Select Vidhan Sabha(s)',
                width: '100%',
                dropdownParent: $(els.vs).parent(),
                closeOnSelect: false
            }, multiSelectTemplates($(els.vs), 'data-vs-cb')));
            bindMultiCheckboxSync($(els.vs), 'data-vs-cb');
            applyCountSummary($(els.vs));
        }

        // 2) Panchayat options: ALL panchayats of the district (loaded once).
        //    Deliberately NOT filtered by the selected Vidhan Sabhas, so the option
        //    list is stable and existing selections can never be wiped.
        const panUrl = getUrl('panchayat') + '?district_id=' + districtId + '&page=1&page_size=2000';
        const panRes = await fetch(panUrl, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const panData = await panRes.json();

        if (!els.panchayat) return;
        els.panchayat.innerHTML += (panData.results || []).map(p =>
            `<option value="${p.id}">${escapeHtml(p.name)}</option>`
        ).join('');
        els.panchayat.disabled = false;

        if ($.fn.select2 && $(els.panchayat).data('select2')) {
            $(els.panchayat).select2('destroy');
        }
        if ($.fn.select2) {
            $(els.panchayat).select2(Object.assign({
                placeholder: 'Select Panchayat(s)',
                width: '100%',
                dropdownParent: $(els.panchayat).parent(),
                closeOnSelect: false
            }, multiSelectTemplates($(els.panchayat), 'data-pan-cb')));
            bindMultiCheckboxSync($(els.panchayat), 'data-pan-cb');
            applyCountSummary($(els.panchayat));
        }
    } catch (e) {
        console.error('Failed to load Vidhan Sabhas / Panchayats:', e);
        showToast('Failed to load dropdown options', 'error');
    } finally {
        hideGlobalLoader();
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
        const url = getUrl('regional-admin') + '?' + params.toString();
        const res = await fetch(url, { 
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();

        renderList(data.results || []);
        renderPaginationEl(data);
        if (els.countLabel) els.countLabel.textContent = `${data.count || 0} admins registered.`;
        if (els.total) els.total.textContent = data.count || 0;
        if (els.start) els.start.textContent = ((state.page - 1) * state.pageSize) + 1;
        if (els.end) els.end.textContent = Math.min(state.page * state.pageSize, data.count || 0);
    } catch (e) {
        console.error('Fetch failed:', e);
        showToast('Failed to load Regional Admins', 'error');
    } finally {
        hideGlobalLoader();
    }
}

function renderList(items) {
    if (!els.list) return;
    if (!items.length) {
        els.list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👤</div>
                <div class="empty-state-title">No Regional Admins found</div>
                <div class="empty-state-text">Add one using the form on the left.</div>
            </div>
        `;
        return;
    }
    els.list.innerHTML = items.map(ra => {
        const avatarHtml = ra.picture
            ? `<img src="${escapeHtml(ra.picture)}" alt="${escapeHtml(ra.name)}">`
            : getInitials(ra.name);
        const panchayatNames = (ra.panchayat_names && ra.panchayat_names.length)
            ? ra.panchayat_names.join(', ')
            : (ra.panchayat_name || '');
        const vsNames = (ra.vidhan_sabha_names && ra.vidhan_sabha_names.length)
            ? ra.vidhan_sabha_names.join(', ')
            : (ra.vidhan_sabha_name || '');

        return `
            <div class="user-list-item">
                <div class="avatar">${avatarHtml}</div>
                <div class="user-list-info">
                    <div class="user-list-name">${escapeHtml(ra.name || '')}</div>
                    <div class="user-list-meta">${escapeHtml(ra.email || '')} · ${escapeHtml(ra.phone_number || '')}</div>
                    <div class="user-list-meta">${escapeHtml(ra.district_name || '')} / ${escapeHtml(vsNames)} / ${escapeHtml(panchayatNames)}</div>
                </div>
                <div class="user-list-actions">
                    <button class="row-action-btn btn-edit" data-id="${ra.id}" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn btn-delete danger" data-id="${ra.id}" data-name="${escapeHtml(ra.name)}" title="Deactivate">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            </div>
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
        name: els.name.value.trim(),
        email: els.email.value.trim().toLowerCase(),
        age: els.age.value ? parseInt(els.age.value, 10) : null,
        gender: els.gender.value || null,
        date_of_birth: els.dob.value || null,
        enrollment_date: els.enrollment.value || null,
        phone_number: els.phone.value.trim(),
        whats_app: els.whatsapp.value.trim() || null,
        password: els.password.value,
        district_id: els.district.value ? parseInt(els.district.value, 10) : null,
        vidhan_sabha_ids: (els.vs ? ($(els.vs).val() || []) : []).map(v => parseInt(v, 10)),
        panchayat_ids: (els.panchayat ? ($(els.panchayat).val() || []) : []).map(v => parseInt(v, 10))
    };

    // Validation
    if (!payload.name || !payload.phone_number) {
        showToast('Please fill in all required fields.', 'error');
        return;
    }
    if (payload.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
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
    if (!payload.district_id || !payload.vidhan_sabha_ids.length || !payload.panchayat_ids.length) {
        showToast('Please select District, Vidhan Sabha(s), and Panchayat(s).', 'error');
        return;
    }

    if (els.imageData.value) {
        payload.picture = els.imageData.value;
    }

    showGlobalLoader();
    try {
        const url = getUrl('regional-admin');
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
            showToast(isEdit ? 'Regional Admin updated' : 'Regional Admin created', 'success');
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

// ── Edit / Delete ─────────────────────────────────────────────────
async function openEditForm(id) {
    showGlobalLoader();
    try {
        const url = getUrl('regional-admin') + '?id=' + id;
        const res = await fetch(url, { 
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to fetch');

        resetForm();
        if (els.formTitle) els.formTitle.textContent = 'Edit Regional Admin';
        els.editingId.value = data.id;

        els.name.value = data.name || '';
        els.email.value = data.email || '';
        els.age.value = data.age || '';
        els.gender.value = data.gender || '';
        els.dob.value = data.date_of_birth ? data.date_of_birth.split('T')[0] : '';
        els.enrollment.value = data.enrollment_date ? data.enrollment_date.split('T')[0] : '';
        els.phone.value = data.phone_number || '';
        els.whatsapp.value = data.whats_app || '';

        // Load cascading dropdowns with pre-selected values
        if (data.district_id) {
            await loadDistrictDropdown();
            els.district.value = data.district_id;
            if ($.fn.select2) $(els.district).val(data.district_id).trigger('change');
            await onDistrictChange();   // loads ALL VS + ALL panchayat options for the district

            if (data.vidhan_sabha_ids && data.vidhan_sabha_ids.length) {
                if ($.fn.select2) $(els.vs).val(data.vidhan_sabha_ids.map(String)).trigger('change');
            }
            if (data.panchayat_ids && data.panchayat_ids.length) {
                if ($.fn.select2) $(els.panchayat).val(data.panchayat_ids.map(String)).trigger('change');
            }
        }

        // Passwords not loaded - user must retype to change
        els.password.value = '';
        els.confirmPassword.value = '';
        els.password.required = false;
        els.confirmPassword.required = false;

        // Show existing profile image
        if (data.picture) {
            if (els.imagePreview) {
                els.imagePreview.innerHTML = `<img src="${escapeHtml(data.picture)}" alt="Profile">`;
            }
            els.imageData.value = data.picture;
        }

        if (els.name) els.name.focus();
    } catch (e) {
        console.error('Edit fetch failed:', e);
        showToast('Failed to load Regional Admin details', 'error');
    } finally {
        hideGlobalLoader();
    }
}

async function deleteRegionalAdmin(id) {
    showGlobalLoader();
    try {
        const url = getUrl('regional-admin');
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
            showToast('Regional Admin deactivated', 'success');
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
    if (els.formTitle) els.formTitle.textContent = 'Register Regional Admin';
    if (els.form) els.form.reset();
    if (els.editingId) els.editingId.value = '';
    if (els.imageData) els.imageData.value = '';

    // Reset dropdowns
    if (els.district) {
        els.district.value = '';
        if ($.fn.select2 && $(els.district).data('select2')) {
            $(els.district).val('').trigger('change');
        }
    }
    if (els.vs) {
        els.vs.innerHTML = '<option value="">Select Vidhan Sabha</option>';
        els.vs.disabled = true;
        if ($.fn.select2 && $(els.vs).data('select2')) {
            $(els.vs).select2('destroy');
        }
    }
    if (els.panchayat) {
        els.panchayat.innerHTML = '<option value="">Select Panchayat</option>';
        els.panchayat.disabled = true;
        if ($.fn.select2 && $(els.panchayat).data('select2')) {
            $(els.panchayat).select2('destroy');
        }
    }

    if (els.password) els.password.required = true;
    if (els.confirmPassword) els.confirmPassword.required = true;

    if (els.imagePreview) {
        els.imagePreview.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
    }
}

// Event delegation for edit/delete buttons
document.addEventListener('click', async (e) => {
    const editBtn = e.target.closest('.btn-edit');
    if (editBtn) {
        const id = parseInt(editBtn.dataset.id, 10);
        await openEditForm(id);
        return;
    }

    const deleteBtn = e.target.closest('.btn-delete');
    if (deleteBtn) {
        const id = parseInt(deleteBtn.dataset.id, 10);
        const name = deleteBtn.dataset.name;
        if (confirm(`Deactivate Regional Admin "${name}"? This will deactivate the account.`)) {
            await deleteRegionalAdmin(id);
        }
        return;
    }
});

// Export for template inline handlers
window.openEditForm = openEditForm;
window.deleteRegionalAdmin = deleteRegionalAdmin;