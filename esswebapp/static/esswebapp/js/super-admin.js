/* ================================================================
   EK SE SRESHTHA - SUPER ADMIN REGISTRATION SCRIPT
   ----------------------------------------------------------------
   Manages Super Admin accounts.
   Left column: form for create/edit.
   Right column: list of existing admins with edit/delete.
   ================================================================ */

renderShell({
    title: 'Super Admin',
    active: 'super-admin',
    breadcrumbs: [
        { label: 'Users' },
        { label: 'Super Admin' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    renderSuperAdminList();

    document.getElementById('sa-form').addEventListener('submit', handleSuperAdminSubmit);

    // Live image preview when user picks a file
    document.getElementById('sa-image').addEventListener('change', handleImageChange);
});

/* ================================================================
   IMAGE PREVIEW
   ----------------------------------------------------------------
   Converts the chosen image to a base64 data URL and shows it
   in the preview circle. The data URL is stored in a hidden
   input so it can be saved with the record.
   ================================================================ */

function handleImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Guard against oversized uploads (2 MB)
    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be under 2 MB.', 'danger');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        document.getElementById('sa-image-data').value = dataUrl;
        document.getElementById('sa-image-preview').innerHTML =
            `<img src="${dataUrl}" alt="Profile preview">`;
    };
    reader.readAsDataURL(file);
}

/* ================================================================
   USER LIST RENDERING
   ================================================================ */

function renderSuperAdminList() {
    let admins = getRecords('superAdmins');
    const list = document.getElementById('sa-list');

    // Apply search filter (matches name / email / phone)
    const searchEl = document.getElementById('sa-search');
    const term = searchEl ? searchEl.value.trim().toLowerCase() : '';
    if (term) {
        admins = admins.filter(a =>
            (a.name && a.name.toLowerCase().includes(term)) ||
            (a.email && a.email.toLowerCase().includes(term)) ||
            (a.phone && String(a.phone).includes(term))
        );
    }

    if (admins.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👤</div>
                <div class="empty-state-title">No Super Admins yet</div>
                <div class="empty-state-text">Add one using the form on the left.</div>
            </div>
        `;
        return;
    }

    list.innerHTML = admins.map(admin => {
        // Build avatar: show image if provided, otherwise initials
        const avatarHtml = admin.image
            ? `<img src="${admin.image}" alt="${escapeHtml(admin.name)}">`
            : getInitials(admin.name);

        return `
            <div class="user-list-item">
                <div class="avatar">${avatarHtml}</div>
                <div class="user-list-info">
                    <div class="user-list-name">${escapeHtml(admin.name)}</div>
                    <div class="user-list-meta">${escapeHtml(admin.email)}</div>
                </div>
                <div class="user-list-actions">
                    <button class="row-action-btn" onclick="editSuperAdmin('${admin.id}')" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn danger" onclick="deleteSuperAdmin('${admin.id}')" title="Delete">
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

function handleSuperAdminSubmit(event) {
    event.preventDefault();

    const editingId = document.getElementById('sa-editing-id').value;

    // Collect all field values
    const payload = {
        name: document.getElementById('sa-name').value.trim(),
        email: document.getElementById('sa-email').value.trim(),
        age: parseInt(document.getElementById('sa-age').value) || null,
        gender: document.getElementById('sa-gender').value,
        dob: document.getElementById('sa-dob').value,
        enrollmentDate: document.getElementById('sa-enrollment').value,
        phone: document.getElementById('sa-phone').value.trim(),
        whatsapp: document.getElementById('sa-whatsapp').value.trim() ||
                  document.getElementById('sa-phone').value.trim(),
        image: document.getElementById('sa-image-data').value || null,
        role: 'super_admin'
    };

    const password = document.getElementById('sa-password').value;
    const confirmPassword = document.getElementById('sa-confirm-password').value;

    // ------------------------------------------------------------
    // Validation
    // ------------------------------------------------------------
    if (!payload.name || !payload.email || !payload.phone) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
        showToast('Please enter a valid email.', 'danger');
        return;
    }

    // Password required only for new accounts, optional when editing
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
        // If password field filled during edit, treat as password change
        if (password.length < 8) {
            showToast('New password must be at least 8 characters.', 'danger');
            return;
        }
        if (password !== confirmPassword) {
            showToast('Passwords do not match.', 'danger');
            return;
        }
        payload.password = password;
    }

    // Check email uniqueness (excluding self on edit)
    const existing = getRecords('superAdmins').find(a =>
        a.email.toLowerCase() === payload.email.toLowerCase() && a.id !== editingId
    );
    if (existing) {
        showToast('An account with this email already exists.', 'danger');
        return;
    }

    // ------------------------------------------------------------
    // Persist
    // ------------------------------------------------------------
    if (editingId) {
        updateRecord('superAdmins', editingId, payload);
        showToast('Super Admin updated', 'success');
    } else {
        addRecord('superAdmins', payload);
        showToast('Super Admin created', 'success');
    }

    resetSuperAdminForm();
    renderSuperAdminList();
}

/* ================================================================
   EDIT & DELETE
   ================================================================ */

/**
 * Loads the admin's data into the form for editing.
 */
function editSuperAdmin(id) {
    const admin = findRecord('superAdmins', id);
    if (!admin) return;

    document.getElementById('sa-form-title').textContent = 'Edit Super Admin';
    document.getElementById('sa-editing-id').value = id;

    document.getElementById('sa-name').value = admin.name || '';
    document.getElementById('sa-email').value = admin.email || '';
    document.getElementById('sa-age').value = admin.age || '';
    document.getElementById('sa-gender').value = admin.gender || '';
    document.getElementById('sa-dob').value = admin.dob || '';
    document.getElementById('sa-enrollment').value = admin.enrollmentDate || '';
    document.getElementById('sa-phone').value = admin.phone || '';
    document.getElementById('sa-whatsapp').value = admin.whatsapp || '';

    // Passwords aren't loaded - user must retype to change
    document.getElementById('sa-password').value = '';
    document.getElementById('sa-confirm-password').value = '';
    document.getElementById('sa-password').required = false;
    document.getElementById('sa-confirm-password').required = false;

    // Show existing profile image if any
    const preview = document.getElementById('sa-image-preview');
    if (admin.image) {
        preview.innerHTML = `<img src="${admin.image}" alt="Profile">`;
        document.getElementById('sa-image-data').value = admin.image;
    } else {
        preview.innerHTML = `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
        document.getElementById('sa-image-data').value = '';
    }

    // Scroll to top so the user sees the form
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Deletes an admin after confirmation. Won't delete the currently
 * signed-in account.
 */
function deleteSuperAdmin(id) {
    const admin = findRecord('superAdmins', id);
    if (!admin) return;

    const session = JSON.parse(localStorage.getItem('ess_session') || '{}');
    if (session.id === id) {
        showToast('You cannot delete your own account while signed in.', 'warning');
        return;
    }

    if (!confirm(`Delete Super Admin "${admin.name}"?`)) return;

    deleteRecord('superAdmins', id);
    showToast('Super Admin deleted', 'success');
    renderSuperAdminList();
}

/**
 * Clears the form back to blank/create state.
 */
function resetSuperAdminForm() {
    document.getElementById('sa-form-title').textContent = 'Register Super Admin';
    document.getElementById('sa-form').reset();
    document.getElementById('sa-editing-id').value = '';
    document.getElementById('sa-image-data').value = '';
    document.getElementById('sa-password').required = true;
    document.getElementById('sa-confirm-password').required = true;
    document.getElementById('sa-image-preview').innerHTML =
        `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
}
