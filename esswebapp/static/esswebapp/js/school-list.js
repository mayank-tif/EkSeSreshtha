/* ================================================================
   EK SE SRESHTHA - SCHOOL LIST SCRIPT
   ----------------------------------------------------------------
   Master list of partner schools with full CRUD via API.
   - Add a school with a single input field
   - Edit / delete existing school rows
   - Live search filter over the table
   ================================================================ */

let state = {
    schools: []
};

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('school-form').addEventListener('submit', handleSchoolSubmit);
    await loadSchools();
    renderSchoolTable();
});

/* ================================================================
   LOAD SCHOOLS FROM API
   ================================================================ */

async function loadSchools() {
    try {
        const response = await apiFetch(getUrl('school-details-list'));
        state.schools = response?.results || response || [];
        console.log('Loaded schools:', state.schools.length);
    } catch (error) {
        console.error('Failed to load schools:', error);
        showToast('Failed to load schools', 'danger');
        state.schools = [];
    }
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
            return;
        }

        showToast('School deleted.', 'success');
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
    const searchTerm = document.getElementById('school-search').value.trim().toLowerCase();
    const all = state.schools;

    // Filter by search term (matches on school name)
    const filtered = searchTerm
        ? all.filter(s =>
            (s.schoolName || s.name || '').toLowerCase().includes(searchTerm)
        )
        : all;

    // Update the record count pill
    document.getElementById('school-count').textContent =
        `${all.length} school${all.length === 1 ? '' : 's'}`;

    // Empty state
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="table-empty">
                    ${searchTerm ? 'No schools match your search.' : 'No schools yet. Add your first one above.'}
                </td>
            </tr>
        `;
        return;
    }

    // Render rows (index numbering resets with each filter)
    tbody.innerHTML = filtered.map((school, index) => {
        const schoolId = school.id;
        const schoolName = school.schoolName || school.name || '';
        const createdOn = school.created_on || school.createdOn || '';
        return `
        <tr>
            <td class="row-index">${index + 1}</td>
            <td>${escapeHtml(schoolName)}</td>
            <td>${formatDate(createdOn)}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-icon" title="Edit" onclick="editSchool('${schoolId}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                        </svg>
                    </button>
                    <button class="btn-icon btn-icon-danger" title="Delete" onclick="deleteSchool('${schoolId}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    `}).join('');
}