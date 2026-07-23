/* ================================================================
   EK SE SRESHTHA - VIDHAN SABHA MANAGEMENT SCRIPT
   ----------------------------------------------------------------
   CRUD for Vidhan Sabha (assembly constituency) entities.
   Each Vidhan Sabha is linked to one District.
   ================================================================ */

// Render the shared shell around the page
renderShell({
    title: 'Vidhan Sabha',
    active: 'vidhan-sabha',
    breadcrumbs: [
        { label: 'Constituency' },
        { label: 'Vidhan Sabha' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    populateDistrictDropdown();
    renderVidhanSabhaTable();

    document.getElementById('vs-form').addEventListener('submit', handleVsSubmit);
    document.getElementById('vs-search').addEventListener('input', renderVidhanSabhaTable);
});

/* ================================================================
   DISTRICT DROPDOWN
   ----------------------------------------------------------------
   Populate the district <select> with all stored districts.
   ================================================================ */

function populateDistrictDropdown() {
    const districts = getRecords('districts');
    const select = document.getElementById('vs-district');

    // Build option list - starts with placeholder
    select.innerHTML = '<option value="">Select a district</option>' +
        districts.map(d =>
            `<option value="${d.id}">${escapeHtml(d.name)}</option>`
        ).join('');

    // If no districts exist, warn the user
    if (districts.length === 0) {
        select.innerHTML = '<option value="">Please add a district first</option>';
    }
}

/* ================================================================
   TABLE RENDERING
   ================================================================ */

function renderVidhanSabhaTable() {
    const vidhanSabhas = getRecords('vidhanSabhas');
    const districts = getRecords('districts');
    const panchayats = getRecords('panchayats');

    // Build a quick lookup map for districts (id -> name)
    const districtMap = Object.fromEntries(districts.map(d => [d.id, d.name]));

    // Apply search filter (against VS name or its district name)
    const query = (document.getElementById('vs-search').value || '').toLowerCase().trim();
    const filtered = vidhanSabhas.filter(v => {
        if (!query) return true;
        const districtName = districtMap[v.districtId] || '';
        return v.name.toLowerCase().includes(query) ||
               districtName.toLowerCase().includes(query);
    });

    // Update record count
    document.getElementById('record-count').textContent = filtered.length;

    const tbody = document.getElementById('vs-tbody');

    // Empty state
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <div class="empty-state-icon">🏛️</div>
                        <div class="empty-state-title">No Vidhan Sabhas found</div>
                        <div class="empty-state-text">
                            ${query ? 'Try a different search term.' : 'Click "Add Vidhan Sabha" to create one.'}
                        </div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    // Render rows
    tbody.innerHTML = filtered.map((vs, index) => {
        // Count child panchayats
        const panchayatCount = panchayats.filter(p => p.vidhanSabhaId === vs.id).length;
        const districtName = districtMap[vs.districtId] || '—';

        return `
            <tr>
                <td class="row-index">${index + 1}</td>
                <td><strong>${escapeHtml(vs.name)}</strong></td>
                <td>${escapeHtml(districtName)}</td>
                <td><span class="count-pill">${panchayatCount}</span></td>
                <td>${formatDate(vs.createdAt)}</td>
                <td>
                    <div class="table-actions">
                        <button class="row-action-btn" onclick="editVidhanSabha('${vs.id}')" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="row-action-btn danger" onclick="deleteVidhanSabha('${vs.id}')" title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

function handleVsSubmit(event) {
    event.preventDefault();

    const name = document.getElementById('vs-name').value.trim();
    const districtId = document.getElementById('vs-district').value;
    const editingId = document.getElementById('vs-editing-id').value;

    // Validation
    if (!name || !districtId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    // Save
    if (editingId) {
        updateRecord('vidhanSabhas', editingId, { name, districtId });
        showToast('Vidhan Sabha updated', 'success');
    } else {
        addRecord('vidhanSabhas', { name, districtId });
        showToast('Vidhan Sabha added', 'success');
    }

    closeModal('vs-modal');
    resetVsForm();
    renderVidhanSabhaTable();
}

/**
 * Populates the modal with an existing VS's data.
 */
function editVidhanSabha(id) {
    const vs = findRecord('vidhanSabhas', id);
    if (!vs) return;

    document.getElementById('vs-modal-title').textContent = 'Edit Vidhan Sabha';
    document.getElementById('vs-name').value = vs.name;
    document.getElementById('vs-district').value = vs.districtId;
    document.getElementById('vs-editing-id').value = id;

    openModal('vs-modal');
}

/**
 * Deletes with confirmation.
 */
function deleteVidhanSabha(id) {
    const vs = findRecord('vidhanSabhas', id);
    if (!vs) return;

    const dependentCount = getRecords('panchayats').filter(p => p.vidhanSabhaId === id).length;
    let msg = `Delete "${vs.name}"?`;
    if (dependentCount > 0) {
        msg += `\n\n${dependentCount} Panchayat(s) will become orphaned.`;
    }

    if (!confirm(msg)) return;

    deleteRecord('vidhanSabhas', id);
    showToast('Vidhan Sabha deleted', 'success');
    renderVidhanSabhaTable();
}

/**
 * Resets modal for a fresh entry.
 */
function resetVsForm() {
    document.getElementById('vs-modal-title').textContent = 'Add Vidhan Sabha';
    document.getElementById('vs-form').reset();
    document.getElementById('vs-editing-id').value = '';
}

// Backdrop click closes the modal + resets form
document.getElementById('vs-modal').addEventListener('click', (e) => {
    if (e.target.id === 'vs-modal') {
        closeModal('vs-modal');
        resetVsForm();
    }
});
