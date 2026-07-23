/* ================================================================
   EK SE SRESHTHA - SCHOOL LIST SCRIPT
   ----------------------------------------------------------------
   Simple master list of partner schools. Provides:
   - Add a school with a single input field
   - Edit / delete existing school rows
   - Live search filter over the table
   Storage table: ess_schools
   ================================================================ */

/* Render the shared sidebar/topbar/breadcrumbs for this page. */
renderShell({
    title: 'School List',
    active: 'school-list',
    breadcrumbs: [
        { label: 'Students' },
        { label: 'School List' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('school-form').addEventListener('submit', handleSchoolSubmit);
    renderSchoolTable();
});

/* ================================================================
   FORM SUBMIT (add / update)
   ----------------------------------------------------------------
   The same form handles both adding a new school and editing an
   existing one. When editing, the hidden `school-editing-id`
   field carries the record id.
   ================================================================ */

function handleSchoolSubmit(event) {
    event.preventDefault();

    const nameInput = document.getElementById('school-name');
    const name = nameInput.value.trim();
    const editingId = document.getElementById('school-editing-id').value;

    if (!name) {
        showToast('School name is required.', 'danger');
        return;
    }

    // Prevent duplicate school names (case-insensitive, excluding the row being edited)
    const existing = getRecords('schools').find(s =>
        s.name.toLowerCase() === name.toLowerCase() && s.id !== editingId
    );
    if (existing) {
        showToast('A school with this name already exists.', 'danger');
        return;
    }

    if (editingId) {
        updateRecord('schools', editingId, { name: name });
        showToast('School updated successfully.', 'success');
    } else {
        addRecord('schools', { name: name });
        showToast('School added successfully.', 'success');
    }

    resetSchoolForm();
    renderSchoolTable();
}

/* ================================================================
   RESET FORM
   Clears the input and switches the button back to "Add" mode.
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
    const school = findRecord('schools', id);
    if (!school) return;

    document.getElementById('school-editing-id').value = school.id;
    document.getElementById('school-name').value = school.name;
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

function deleteSchool(id) {
    const school = findRecord('schools', id);
    if (!school) return;

    if (!confirm(`Delete "${school.name}"? This action cannot be undone.`)) return;

    deleteRecord('schools', id);
    showToast('School deleted.', 'success');
    renderSchoolTable();
}

/* ================================================================
   RENDER TABLE
   ----------------------------------------------------------------
   Applies the search filter, updates the record count, and paints
   one row per matching school.
   ================================================================ */

function renderSchoolTable() {
    const tbody = document.getElementById('school-table-body');
    const searchTerm = document.getElementById('school-search').value.trim().toLowerCase();
    const all = getRecords('schools');

    // Filter by search term (matches on school name)
    const filtered = searchTerm
        ? all.filter(s => s.name.toLowerCase().includes(searchTerm))
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
    tbody.innerHTML = filtered.map((school, index) => `
        <tr>
            <td class="row-index">${index + 1}</td>
            <td>${escapeHtml(school.name)}</td>
            <td>${formatDate(school.createdAt)}</td>
            <td>
                <div class="table-actions">
                    <button class="btn-icon" title="Edit" onclick="editSchool('${school.id}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                        </svg>
                    </button>
                    <button class="btn-icon btn-icon-danger" title="Delete" onclick="deleteSchool('${school.id}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        </svg>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}
