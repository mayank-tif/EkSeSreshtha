/* ================================================================
   EK SE SRESHTHA - PANCHAYAT MANAGEMENT SCRIPT
   ----------------------------------------------------------------
   CRUD for the Panchayat entity, which sits under Vidhan Sabha,
   which sits under District. The form uses cascading dropdowns:
   selecting a district filters the Vidhan Sabha options.
   ================================================================ */

renderShell({
    title: 'Panchayat',
    active: 'panchayat',
    breadcrumbs: [
        { label: 'Constituency' },
        { label: 'Panchayat' }
    ]
});

document.addEventListener('DOMContentLoaded', () => {
    populatePanchayatDistricts();
    renderPanchayatTable();

    document.getElementById('panchayat-form').addEventListener('submit', handlePanchayatSubmit);
    document.getElementById('panchayat-search').addEventListener('input', renderPanchayatTable);
});

/* ================================================================
   DROPDOWN POPULATION
   ================================================================ */

/**
 * Fill the district dropdown with all stored districts.
 */
function populatePanchayatDistricts() {
    const districts = getRecords('districts');
    const select = document.getElementById('panchayat-district');

    select.innerHTML = '<option value="">Select district</option>' +
        districts.map(d =>
            `<option value="${d.id}">${escapeHtml(d.name)}</option>`
        ).join('');
}

/**
 * When the user picks a district, filter the Vidhan Sabha dropdown
 * to show only VSs belonging to that district.
 */
function onPanchayatDistrictChange() {
    const districtId = document.getElementById('panchayat-district').value;
    const vsSelect = document.getElementById('panchayat-vs');

    if (!districtId) {
        vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
        vsSelect.disabled = true;
        return;
    }

    // Filter VSs by chosen district
    const vsList = getRecords('vidhanSabhas').filter(v => v.districtId === districtId);

    if (vsList.length === 0) {
        vsSelect.innerHTML = '<option value="">No Vidhan Sabhas in this district</option>';
        vsSelect.disabled = true;
        return;
    }

    vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>' +
        vsList.map(v =>
            `<option value="${v.id}">${escapeHtml(v.name)}</option>`
        ).join('');
    vsSelect.disabled = false;
}

/* ================================================================
   TABLE RENDERING
   ================================================================ */

function renderPanchayatTable() {
    const panchayats = getRecords('panchayats');
    const districts = getRecords('districts');
    const vidhanSabhas = getRecords('vidhanSabhas');
    const villages = getRecords('villages');

    // Lookup maps for fast label rendering
    const districtMap = Object.fromEntries(districts.map(d => [d.id, d.name]));
    const vsMap = Object.fromEntries(vidhanSabhas.map(v => [v.id, v.name]));

    // Apply search filter
    const query = (document.getElementById('panchayat-search').value || '').toLowerCase().trim();
    const filtered = panchayats.filter(p => {
        if (!query) return true;
        const vsName = vsMap[p.vidhanSabhaId] || '';
        const districtName = districtMap[p.districtId] || '';
        return p.name.toLowerCase().includes(query) ||
               vsName.toLowerCase().includes(query) ||
               districtName.toLowerCase().includes(query);
    });

    document.getElementById('record-count').textContent = filtered.length;

    const tbody = document.getElementById('panchayat-tbody');

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-state-icon">🏘️</div>
                        <div class="empty-state-title">No panchayats found</div>
                        <div class="empty-state-text">
                            ${query ? 'Try a different search.' : 'Click "Add Panchayat" to create one.'}
                        </div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((p, index) => {
        const villageCount = villages.filter(v => v.panchayatId === p.id).length;

        return `
            <tr>
                <td class="row-index">${index + 1}</td>
                <td><strong>${escapeHtml(p.name)}</strong></td>
                <td>${escapeHtml(vsMap[p.vidhanSabhaId] || '—')}</td>
                <td>${escapeHtml(districtMap[p.districtId] || '—')}</td>
                <td><span class="count-pill">${villageCount}</span></td>
                <td>${formatDate(p.createdAt)}</td>
                <td>
                    <div class="table-actions">
                        <button class="row-action-btn" onclick="editPanchayat('${p.id}')" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="row-action-btn danger" onclick="deletePanchayat('${p.id}')" title="Delete">
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

function handlePanchayatSubmit(event) {
    event.preventDefault();

    const name = document.getElementById('panchayat-name').value.trim();
    const districtId = document.getElementById('panchayat-district').value;
    const vidhanSabhaId = document.getElementById('panchayat-vs').value;
    const editingId = document.getElementById('panchayat-editing-id').value;

    if (!name || !districtId || !vidhanSabhaId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    const payload = { name, districtId, vidhanSabhaId };

    if (editingId) {
        updateRecord('panchayats', editingId, payload);
        showToast('Panchayat updated', 'success');
    } else {
        addRecord('panchayats', payload);
        showToast('Panchayat added', 'success');
    }

    closeModal('panchayat-modal');
    resetPanchayatForm();
    renderPanchayatTable();
}

/**
 * Populates the form with an existing record's data.
 * Also cascades the dropdowns so the VS list is filtered correctly.
 */
function editPanchayat(id) {
    const p = findRecord('panchayats', id);
    if (!p) return;

    document.getElementById('panchayat-modal-title').textContent = 'Edit Panchayat';
    document.getElementById('panchayat-name').value = p.name;
    document.getElementById('panchayat-district').value = p.districtId;

    // Populate VS dropdown for the current district, then pick the value
    onPanchayatDistrictChange();
    document.getElementById('panchayat-vs').value = p.vidhanSabhaId;

    document.getElementById('panchayat-editing-id').value = id;
    openModal('panchayat-modal');
}

function deletePanchayat(id) {
    const p = findRecord('panchayats', id);
    if (!p) return;

    const dependentCount = getRecords('villages').filter(v => v.panchayatId === id).length;
    let msg = `Delete "${p.name}"?`;
    if (dependentCount > 0) {
        msg += `\n\n${dependentCount} village(s) will become orphaned.`;
    }

    if (!confirm(msg)) return;

    deleteRecord('panchayats', id);
    showToast('Panchayat deleted', 'success');
    renderPanchayatTable();
}

function resetPanchayatForm() {
    document.getElementById('panchayat-modal-title').textContent = 'Add Panchayat';
    document.getElementById('panchayat-form').reset();
    document.getElementById('panchayat-vs').disabled = true;
    document.getElementById('panchayat-editing-id').value = '';
}

document.getElementById('panchayat-modal').addEventListener('click', (e) => {
    if (e.target.id === 'panchayat-modal') {
        closeModal('panchayat-modal');
        resetPanchayatForm();
    }
});
