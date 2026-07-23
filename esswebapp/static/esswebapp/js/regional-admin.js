/* ================================================================
   EK SE SRESHTHA - REGIONAL ADMIN SCRIPT
   ----------------------------------------------------------------
   Manages Regional Admin accounts. Similar to Super Admin, but
   with additional area-assignment fields (District → Vidhan Sabha
   → Panchayat) using cascading dropdowns.
   ================================================================ */

renderShell({
    title: 'Regional Admin',
    active: 'regional-admin',
    breadcrumbs: [
        { label: 'Users' },
        { label: 'Regional Admin' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    populateRaDistricts();
    renderRegionalAdminList();

    document.getElementById('ra-form').addEventListener('submit', handleRaSubmit);
    document.getElementById('ra-image').addEventListener('change', handleRaImageChange);
});

/* ================================================================
   PROFILE IMAGE PREVIEW
   ================================================================ */

function handleRaImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be under 2 MB.', 'danger');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        document.getElementById('ra-image-data').value = dataUrl;
        document.getElementById('ra-image-preview').innerHTML =
            `<img src="${dataUrl}" alt="Profile preview">`;
    };
    reader.readAsDataURL(file);
}

/* ================================================================
   CASCADING DROPDOWNS FOR AREA ASSIGNMENT
   ================================================================ */

function populateRaDistricts() {
    const districts = getRecords('districts');
    const select = document.getElementById('ra-district');
    select.innerHTML = '<option value="">Select district</option>' +
        districts.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
}

function onRaDistrictChange() {
    const districtId = document.getElementById('ra-district').value;
    const vsSelect = document.getElementById('ra-vs');
    const panchSelect = document.getElementById('ra-panchayat');

    // Reset children whenever the parent changes
    vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';
    panchSelect.disabled = true;

    if (!districtId) {
        vsSelect.disabled = true;
        return;
    }

    const list = getRecords('vidhanSabhas').filter(v => v.districtId === districtId);
    vsSelect.innerHTML += list.map(v =>
        `<option value="${v.id}">${escapeHtml(v.name)}</option>`
    ).join('');
    vsSelect.disabled = false;
}

function onRaVsChange() {
    const vsId = document.getElementById('ra-vs').value;
    const panchSelect = document.getElementById('ra-panchayat');
    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';

    if (!vsId) {
        panchSelect.disabled = true;
        return;
    }

    const list = getRecords('panchayats').filter(p => p.vidhanSabhaId === vsId);
    panchSelect.innerHTML += list.map(p =>
        `<option value="${p.id}">${escapeHtml(p.name)}</option>`
    ).join('');
    panchSelect.disabled = false;
}

/* ================================================================
   LIST RENDERING
   ================================================================ */

function renderRegionalAdminList() {
    let admins = getRecords('regionalAdmins');
    const districts = getRecords('districts');
    const districtMap = Object.fromEntries(districts.map(d => [d.id, d.name]));

    document.getElementById('ra-count-label').textContent =
        `${admins.length} admin${admins.length === 1 ? '' : 's'} registered.`;

    // Apply search filter (matches name / email / phone / district)
    const searchEl = document.getElementById('ra-search');
    const term = searchEl ? searchEl.value.trim().toLowerCase() : '';
    if (term) {
        admins = admins.filter(a =>
            (a.name && a.name.toLowerCase().includes(term)) ||
            (a.email && a.email.toLowerCase().includes(term)) ||
            (a.phone && String(a.phone).includes(term)) ||
            (districtMap[a.districtId] && districtMap[a.districtId].toLowerCase().includes(term))
        );
    }

    const list = document.getElementById('ra-list');

    if (admins.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👨‍💼</div>
                <div class="empty-state-title">No Regional Admins yet</div>
                <div class="empty-state-text">Add one using the form on the left.</div>
            </div>
        `;
        return;
    }

    list.innerHTML = admins.map(admin => {
        const avatarHtml = admin.image
            ? `<img src="${admin.image}" alt="${escapeHtml(admin.name)}">`
            : getInitials(admin.name);

        const districtName = districtMap[admin.districtId] || 'Unassigned';

        return `
            <div class="user-list-item">
                <div class="avatar">${avatarHtml}</div>
                <div class="user-list-info">
                    <div class="user-list-name">${escapeHtml(admin.name)}</div>
                    <div class="user-list-meta">${escapeHtml(admin.email)} · ${escapeHtml(districtName)}</div>
                </div>
                <div class="user-list-actions">
                    <button class="row-action-btn" onclick="editRegionalAdmin('${admin.id}')" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn danger" onclick="deleteRegionalAdmin('${admin.id}')" title="Delete">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

function handleRaSubmit(event) {
    event.preventDefault();

    const editingId = document.getElementById('ra-editing-id').value;

    const payload = {
        name: document.getElementById('ra-name').value.trim(),
        email: document.getElementById('ra-email').value.trim(),
        age: parseInt(document.getElementById('ra-age').value) || null,
        gender: document.getElementById('ra-gender').value,
        dob: document.getElementById('ra-dob').value,
        enrollmentDate: document.getElementById('ra-enrollment').value,
        phone: document.getElementById('ra-phone').value.trim(),
        whatsapp: document.getElementById('ra-whatsapp').value.trim() ||
                  document.getElementById('ra-phone').value.trim(),
        districtId: document.getElementById('ra-district').value,
        vidhanSabhaId: document.getElementById('ra-vs').value,
        panchayatId: document.getElementById('ra-panchayat').value,
        image: document.getElementById('ra-image-data').value || null,
        role: 'regional_admin'
    };

    const password = document.getElementById('ra-password').value;
    const confirmPassword = document.getElementById('ra-confirm-password').value;

    // Validation
    if (!payload.name || !payload.email || !payload.phone ||
        !payload.districtId || !payload.vidhanSabhaId || !payload.panchayatId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
        showToast('Please enter a valid email.', 'danger');
        return;
    }

    // Password logic - required for new, optional for edit
    if (!editingId) {
        if (!password || password.length < 8) {
            showToast('Password must be at least 8 characters.', 'danger');
            return;
        }
        if (password !== confirmPassword) {
            showToast('Passwords do not match.', 'danger');
            return;
        }
        payload.password = password;
    } else if (password) {
        if (password !== confirmPassword) {
            showToast('Passwords do not match.', 'danger');
            return;
        }
        payload.password = password;
    }

    // Persist
    if (editingId) {
        updateRecord('regionalAdmins', editingId, payload);
        showToast('Regional Admin updated', 'success');
    } else {
        addRecord('regionalAdmins', payload);
        showToast('Regional Admin created', 'success');
    }

    resetRegionalAdminForm();
    renderRegionalAdminList();
}

/* ================================================================
   EDIT & DELETE
   ================================================================ */

function editRegionalAdmin(id) {
    const admin = findRecord('regionalAdmins', id);
    if (!admin) return;

    document.getElementById('ra-form-title').textContent = 'Edit Regional Admin';
    document.getElementById('ra-editing-id').value = id;

    document.getElementById('ra-name').value = admin.name || '';
    document.getElementById('ra-email').value = admin.email || '';
    document.getElementById('ra-age').value = admin.age || '';
    document.getElementById('ra-gender').value = admin.gender || '';
    document.getElementById('ra-dob').value = admin.dob || '';
    document.getElementById('ra-enrollment').value = admin.enrollmentDate || '';
    document.getElementById('ra-phone').value = admin.phone || '';
    document.getElementById('ra-whatsapp').value = admin.whatsapp || '';
    document.getElementById('ra-district').value = admin.districtId || '';

    // Cascade the dropdowns so children populate correctly
    onRaDistrictChange();
    document.getElementById('ra-vs').value = admin.vidhanSabhaId || '';
    onRaVsChange();
    document.getElementById('ra-panchayat').value = admin.panchayatId || '';

    // Password not loaded - user has to retype to change
    document.getElementById('ra-password').value = '';
    document.getElementById('ra-confirm-password').value = '';
    document.getElementById('ra-password').required = false;
    document.getElementById('ra-confirm-password').required = false;

    // Show existing image
    const preview = document.getElementById('ra-image-preview');
    if (admin.image) {
        preview.innerHTML = `<img src="${admin.image}" alt="Profile">`;
        document.getElementById('ra-image-data').value = admin.image;
    } else {
        preview.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
        document.getElementById('ra-image-data').value = '';
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function deleteRegionalAdmin(id) {
    const admin = findRecord('regionalAdmins', id);
    if (!admin) return;

    // Warn if this admin is assigned to any centres
    const assignedCentres = getRecords('centres').filter(c => c.regionalAdminId === id).length;
    let msg = `Delete Regional Admin "${admin.name}"?`;
    if (assignedCentres > 0) {
        msg += `\n\n${assignedCentres} centre(s) will lose their assigned admin.`;
    }

    if (!confirm(msg)) return;

    deleteRecord('regionalAdmins', id);
    showToast('Regional Admin deleted', 'success');
    renderRegionalAdminList();
}

function resetRegionalAdminForm() {
    document.getElementById('ra-form-title').textContent = 'Register Regional Admin';
    document.getElementById('ra-form').reset();
    document.getElementById('ra-editing-id').value = '';
    document.getElementById('ra-image-data').value = '';
    document.getElementById('ra-vs').disabled = true;
    document.getElementById('ra-panchayat').disabled = true;
    document.getElementById('ra-password').required = true;
    document.getElementById('ra-confirm-password').required = true;
    document.getElementById('ra-image-preview').innerHTML =
        `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
}
