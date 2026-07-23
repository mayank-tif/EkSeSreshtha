/* ================================================================
   EK SE SRESHTHA - DISTRICT MANAGEMENT SCRIPT
   ----------------------------------------------------------------
   CRUD operations for the District entity.
   - Lists all districts in a searchable table
   - Add new district via modal
   - Edit existing district
   - Delete with confirmation
   ================================================================ */

// Render the sidebar + top header around the page content
renderShell({
    title: 'Districts',
    active: 'district',
    breadcrumbs: [
        { label: 'Constituency' },
        { label: 'District' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    // Do the initial render of the table
    renderDistrictTable();

    // Wire up the add/edit form submission
    document.getElementById('district-form').addEventListener('submit', handleDistrictSubmit);

    // Wire up live search
    document.getElementById('district-search').addEventListener('input', renderDistrictTable);
});

/* ================================================================
   RENDER THE DISTRICT TABLE
   ----------------------------------------------------------------
   Reads all districts, applies the search filter, and injects
   HTML into the table body. Also updates the count label.
   ================================================================ */

function renderDistrictTable() {
    const districts = getRecords('districts');
    const vidhanSabhas = getRecords('vidhanSabhas');
    const panchayats = getRecords('panchayats');

    // Get current search query, normalized
    const query = (document.getElementById('district-search').value || '').toLowerCase().trim();

    // Apply the search filter
    const filtered = districts.filter(d =>
        !query || d.name.toLowerCase().includes(query)
    );

    // Update record count in header
    document.getElementById('record-count').textContent = filtered.length;

    const tbody = document.getElementById('district-tbody');

    // Empty state
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-state-icon">🗺️</div>
                        <div class="empty-state-title">No districts found</div>
                        <div class="empty-state-text">
                            ${query ? 'Try a different search term.' : 'Click "Add District" to get started.'}
                        </div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    // Build a row for each district
    tbody.innerHTML = filtered.map((district, index) => {
        // Count how many child records belong to this district
        const vsCount = vidhanSabhas.filter(v => v.districtId === district.id).length;
        const panchayatCount = panchayats.filter(p => p.districtId === district.id).length;

        return `
            <tr>
                <td class="row-index">${index + 1}</td>
                <td><strong>${escapeHtml(district.name)}</strong></td>
                <td><span class="count-pill">${vsCount}</span></td>
                <td><span class="count-pill">${panchayatCount}</span></td>
                <td>${formatDate(district.createdAt)}</td>
                <td>
                    <div class="table-actions">
                        <button class="row-action-btn" onclick="editDistrict('${district.id}')" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="row-action-btn danger" onclick="deleteDistrict('${district.id}')" title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/* ================================================================
   ADD / EDIT DISTRICT
   ================================================================ */

/**
 * Handles the modal form submission for both create and edit.
 */
function handleDistrictSubmit(event) {
    event.preventDefault();

    const nameInput = document.getElementById('district-name');
    const editingId = document.getElementById('district-editing-id').value;
    const name = nameInput.value.trim();

    // Basic validation
    if (!name) {
        showToast('Please enter a district name.', 'danger');
        return;
    }

    // Check for duplicate name (case insensitive), excluding self on edit
    const existing = getRecords('districts').find(d =>
        d.name.toLowerCase() === name.toLowerCase() && d.id !== editingId
    );
    if (existing) {
        showToast('A district with this name already exists.', 'danger');
        return;
    }

    // Save - either update or create
    if (editingId) {
        updateRecord('districts', editingId, { name });
        showToast('District updated', 'success');
    } else {
        addRecord('districts', { name });
        showToast('District added', 'success');
    }

    // Reset UI
    closeModal('district-modal');
    resetDistrictForm();
    renderDistrictTable();
}

/**
 * Opens the modal in edit mode, pre-filled with the district's data.
 */
function editDistrict(id) {
    const district = findRecord('districts', id);
    if (!district) return;

    document.getElementById('district-modal-title').textContent = 'Edit District';
    document.getElementById('district-name').value = district.name;
    document.getElementById('district-editing-id').value = id;

    openModal('district-modal');
}

/**
 * Prompts to confirm, then deletes the district.
 * Warns about cascading impact on child records.
 */
function deleteDistrict(id) {
    const district = findRecord('districts', id);
    if (!district) return;

    // Warn if there are dependent records
    const dependentVS = getRecords('vidhanSabhas').filter(v => v.districtId === id).length;
    const dependentPanchayats = getRecords('panchayats').filter(p => p.districtId === id).length;

    let confirmMessage = `Delete "${district.name}"?`;
    if (dependentVS > 0 || dependentPanchayats > 0) {
        confirmMessage += `\n\nThis district has ${dependentVS} Vidhan Sabha(s) and ${dependentPanchayats} Panchayat(s) linked to it. They will become orphaned.`;
    }

    if (!confirm(confirmMessage)) return;

    deleteRecord('districts', id);
    showToast('District deleted', 'success');
    renderDistrictTable();
}

/**
 * Resets the modal form to the "add new" state.
 */
function resetDistrictForm() {
    document.getElementById('district-modal-title').textContent = 'Add District';
    document.getElementById('district-name').value = '';
    document.getElementById('district-editing-id').value = '';
}

/* ================================================================
   Modal close behavior - clear the form when the user
   dismisses without saving.
   ================================================================ */

document.getElementById('district-modal').addEventListener('click', (e) => {
    // Close when clicking the backdrop (but not the modal itself)
    if (e.target.id === 'district-modal') {
        closeModal('district-modal');
        resetDistrictForm();
    }
});
