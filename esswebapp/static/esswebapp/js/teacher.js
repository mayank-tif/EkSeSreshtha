/* ================================================================
   EK SE SRESHTHA - TEACHER REGISTRATION SCRIPT
   ----------------------------------------------------------------
   Full CRUD for Teacher entities. Teachers have the deepest area
   assignment (District → Vidhan Sabha → Panchayat → Village),
   plus guardian and qualification details.
   ================================================================ */

renderShell({
    title: 'Teachers',
    active: 'teacher',
    breadcrumbs: [
        { label: 'Users' },
        { label: 'Teacher' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    populateTeacherDistricts();
    renderTeacherList();

    document.getElementById('teacher-form').addEventListener('submit', handleTeacherSubmit);
    document.getElementById('teacher-image').addEventListener('change', handleTeacherImageChange);
});

/* ================================================================
   PROFILE IMAGE PREVIEW
   ================================================================ */

function handleTeacherImageChange(event) {
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
        document.getElementById('teacher-image-data').value = dataUrl;
        document.getElementById('teacher-image-preview').innerHTML =
            `<img src="${dataUrl}" alt="Profile preview">`;
    };
    reader.readAsDataURL(file);
}

/* ================================================================
   4-LEVEL CASCADING DROPDOWNS
   District → Vidhan Sabha → Panchayat → Village
   ================================================================ */

function populateTeacherDistricts() {
    const districts = getRecords('districts');
    const select = document.getElementById('teacher-district');
    select.innerHTML = '<option value="">Select district</option>' +
        districts.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
}

function onTeacherDistrictChange() {
    const districtId = document.getElementById('teacher-district').value;
    const vsSelect = document.getElementById('teacher-vs');
    const panchSelect = document.getElementById('teacher-panchayat');
    const villageSelect = document.getElementById('teacher-village');

    // Cascade reset
    vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';
    villageSelect.innerHTML = '<option value="">Select Village</option>';
    panchSelect.disabled = true;
    villageSelect.disabled = true;

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

function onTeacherVsChange() {
    const vsId = document.getElementById('teacher-vs').value;
    const panchSelect = document.getElementById('teacher-panchayat');
    const villageSelect = document.getElementById('teacher-village');

    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';
    villageSelect.innerHTML = '<option value="">Select Village</option>';
    villageSelect.disabled = true;

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

function onTeacherPanchayatChange() {
    const panchayatId = document.getElementById('teacher-panchayat').value;
    const villageSelect = document.getElementById('teacher-village');

    villageSelect.innerHTML = '<option value="">Select Village</option>';

    if (!panchayatId) {
        villageSelect.disabled = true;
        return;
    }

    const list = getRecords('villages').filter(v => v.panchayatId === panchayatId);
    villageSelect.innerHTML += list.map(v =>
        `<option value="${v.id}">${escapeHtml(v.name)}</option>`
    ).join('');
    villageSelect.disabled = false;
}

/* ================================================================
   LIST RENDERING
   ================================================================ */

function renderTeacherList() {
    let teachers = getRecords('teachers');
    const villages = getRecords('villages');
    const villageMap = Object.fromEntries(villages.map(v => [v.id, v.name]));

    document.getElementById('teacher-count-label').textContent =
        `${teachers.length} teacher${teachers.length === 1 ? '' : 's'} registered.`;

    // Apply search filter (matches name / email / phone / village / qualification)
    const searchEl = document.getElementById('teacher-search');
    const term = searchEl ? searchEl.value.trim().toLowerCase() : '';
    if (term) {
        teachers = teachers.filter(t =>
            (t.name && t.name.toLowerCase().includes(term)) ||
            (t.email && t.email.toLowerCase().includes(term)) ||
            (t.phone && String(t.phone).includes(term)) ||
            (t.qualification && t.qualification.toLowerCase().includes(term)) ||
            (villageMap[t.villageId] && villageMap[t.villageId].toLowerCase().includes(term))
        );
    }

    const list = document.getElementById('teacher-list');

    if (teachers.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👩‍🏫</div>
                <div class="empty-state-title">No teachers yet</div>
                <div class="empty-state-text">Register the first teacher using the form.</div>
            </div>
        `;
        return;
    }

    list.innerHTML = teachers.map(teacher => {
        const avatarHtml = teacher.image
            ? `<img src="${teacher.image}" alt="${escapeHtml(teacher.name)}">`
            : getInitials(teacher.name);

        const villageName = villageMap[teacher.villageId] || 'Unassigned';

        return `
            <div class="user-list-item">
                <div class="avatar">${avatarHtml}</div>
                <div class="user-list-info">
                    <div class="user-list-name">${escapeHtml(teacher.name)}</div>
                    <div class="user-list-meta">${escapeHtml(teacher.qualification || 'No qualification')} · ${escapeHtml(villageName)}</div>
                </div>
                <div class="user-list-actions">
                    <button class="row-action-btn" onclick="editTeacher('${teacher.id}')" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn danger" onclick="deleteTeacher('${teacher.id}')" title="Delete">
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

function handleTeacherSubmit(event) {
    event.preventDefault();

    const editingId = document.getElementById('teacher-editing-id').value;

    const payload = {
        name: document.getElementById('teacher-name').value.trim(),
        email: document.getElementById('teacher-email').value.trim(),
        age: parseInt(document.getElementById('teacher-age').value) || null,
        gender: document.getElementById('teacher-gender').value,
        dob: document.getElementById('teacher-dob').value,
        enrollmentDate: document.getElementById('teacher-enrollment').value,
        qualification: document.getElementById('teacher-qualification').value.trim(),
        phone: document.getElementById('teacher-phone').value.trim(),
        whatsapp: document.getElementById('teacher-whatsapp').value.trim() ||
                  document.getElementById('teacher-phone').value.trim(),
        guardianName: document.getElementById('teacher-guardian-name').value.trim(),
        guardianNo: document.getElementById('teacher-guardian-no').value.trim(),
        address: document.getElementById('teacher-address').value.trim(),
        districtId: document.getElementById('teacher-district').value,
        vidhanSabhaId: document.getElementById('teacher-vs').value,
        panchayatId: document.getElementById('teacher-panchayat').value,
        villageId: document.getElementById('teacher-village').value,
        image: document.getElementById('teacher-image-data').value || null,
        role: 'teacher'
    };

    const password = document.getElementById('teacher-password').value;
    const confirmPassword = document.getElementById('teacher-confirm-password').value;

    // Validation
    if (!payload.name || !payload.email || !payload.phone ||
        !payload.districtId || !payload.vidhanSabhaId ||
        !payload.panchayatId || !payload.villageId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
        showToast('Please enter a valid email.', 'danger');
        return;
    }

    // Password rules - required for new, optional for edit
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

    if (editingId) {
        updateRecord('teachers', editingId, payload);
        showToast('Teacher updated', 'success');
    } else {
        addRecord('teachers', payload);
        showToast('Teacher created', 'success');
    }

    resetTeacherForm();
    renderTeacherList();
}

/* ================================================================
   EDIT & DELETE
   ================================================================ */

function editTeacher(id) {
    const teacher = findRecord('teachers', id);
    if (!teacher) return;

    document.getElementById('teacher-form-title').textContent = 'Edit Teacher';
    document.getElementById('teacher-editing-id').value = id;

    // Fill each field
    document.getElementById('teacher-name').value = teacher.name || '';
    document.getElementById('teacher-email').value = teacher.email || '';
    document.getElementById('teacher-age').value = teacher.age || '';
    document.getElementById('teacher-gender').value = teacher.gender || '';
    document.getElementById('teacher-dob').value = teacher.dob || '';
    document.getElementById('teacher-enrollment').value = teacher.enrollmentDate || '';
    document.getElementById('teacher-qualification').value = teacher.qualification || '';
    document.getElementById('teacher-phone').value = teacher.phone || '';
    document.getElementById('teacher-whatsapp').value = teacher.whatsapp || '';
    document.getElementById('teacher-guardian-name').value = teacher.guardianName || '';
    document.getElementById('teacher-guardian-no').value = teacher.guardianNo || '';
    document.getElementById('teacher-address').value = teacher.address || '';
    document.getElementById('teacher-district').value = teacher.districtId || '';

    // Cascade dropdown states
    onTeacherDistrictChange();
    document.getElementById('teacher-vs').value = teacher.vidhanSabhaId || '';
    onTeacherVsChange();
    document.getElementById('teacher-panchayat').value = teacher.panchayatId || '';
    onTeacherPanchayatChange();
    document.getElementById('teacher-village').value = teacher.villageId || '';

    // Passwords empty on edit; user retypes to change
    document.getElementById('teacher-password').value = '';
    document.getElementById('teacher-confirm-password').value = '';
    document.getElementById('teacher-password').required = false;
    document.getElementById('teacher-confirm-password').required = false;

    // Existing image preview
    const preview = document.getElementById('teacher-image-preview');
    if (teacher.image) {
        preview.innerHTML = `<img src="${teacher.image}" alt="Profile">`;
        document.getElementById('teacher-image-data').value = teacher.image;
    } else {
        preview.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
        document.getElementById('teacher-image-data').value = '';
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function deleteTeacher(id) {
    const teacher = findRecord('teachers', id);
    if (!teacher) return;

    // Warn about centres this teacher is assigned to
    const assignedCentres = getRecords('centres').filter(c => c.teacherId === id).length;
    let msg = `Delete teacher "${teacher.name}"?`;
    if (assignedCentres > 0) {
        msg += `\n\n${assignedCentres} centre(s) will lose their assigned teacher.`;
    }

    if (!confirm(msg)) return;

    deleteRecord('teachers', id);
    showToast('Teacher deleted', 'success');
    renderTeacherList();
}

function resetTeacherForm() {
    document.getElementById('teacher-form-title').textContent = 'Register Teacher';
    document.getElementById('teacher-form').reset();
    document.getElementById('teacher-editing-id').value = '';
    document.getElementById('teacher-image-data').value = '';
    document.getElementById('teacher-vs').disabled = true;
    document.getElementById('teacher-panchayat').disabled = true;
    document.getElementById('teacher-village').disabled = true;
    document.getElementById('teacher-password').required = true;
    document.getElementById('teacher-confirm-password').required = true;
    document.getElementById('teacher-image-preview').innerHTML =
        `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
}
