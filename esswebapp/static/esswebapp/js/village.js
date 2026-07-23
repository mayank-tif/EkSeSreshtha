/* ================================================================
   EK SE SRESHTHA - VILLAGE MANAGEMENT SCRIPT
   ----------------------------------------------------------------
   CRUD for the Village entity, which sits at the deepest level
   of the constituency hierarchy:
       District → Vidhan Sabha → Panchayat → Village
   The add/edit modal uses three cascading dropdowns that filter
   each other in order.
   ================================================================ */

renderShell({
    title: 'Villages',
    active: 'village',
    breadcrumbs: [
        { label: 'Constituency' },
        { label: 'Village' }
    ]
});

document.addEventListener('DOMContentLoaded', () => {
    populateVillageDistricts();
    renderVillageTable();

    document.getElementById('village-form').addEventListener('submit', handleVillageSubmit);
    document.getElementById('village-search').addEventListener('input', renderVillageTable);
});

/* ================================================================
   CASCADING DROPDOWNS
   ----------------------------------------------------------------
   District picks -> filter Vidhan Sabha options
   Vidhan Sabha picks -> filter Panchayat options
   ================================================================ */

function populateVillageDistricts() {
    const districts = getRecords('districts');
    const select = document.getElementById('village-district');
    select.innerHTML = '<option value="">Select district</option>' +
        districts.map(d =>
            `<option value="${d.id}">${escapeHtml(d.name)}</option>`
        ).join('');
}

/**
 * When the district changes, refresh the VS dropdown and
 * disable the Panchayat one until a VS is picked.
 */
function onVillageDistrictChange() {
    const districtId = document.getElementById('village-district').value;
    const vsSelect = document.getElementById('village-vs');
    const panchSelect = document.getElementById('village-panchayat');

    // Reset downstream selects
    vsSelect.innerHTML = '<option value="">Select Vidhan Sabha</option>';
    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';
    panchSelect.disabled = true;

    if (!districtId) {
        vsSelect.disabled = true;
        return;
    }

    // Filter VSs for the chosen district
    const vsList = getRecords('vidhanSabhas').filter(v => v.districtId === districtId);
    vsSelect.innerHTML += vsList.map(v =>
        `<option value="${v.id}">${escapeHtml(v.name)}</option>`
    ).join('');
    vsSelect.disabled = false;
}

/**
 * When the Vidhan Sabha changes, refresh the Panchayat dropdown.
 */
function onVillageVsChange() {
    const vsId = document.getElementById('village-vs').value;
    const panchSelect = document.getElementById('village-panchayat');

    panchSelect.innerHTML = '<option value="">Select Panchayat</option>';

    if (!vsId) {
        panchSelect.disabled = true;
        return;
    }

    const panchayats = getRecords('panchayats').filter(p => p.vidhanSabhaId === vsId);
    panchSelect.innerHTML += panchayats.map(p =>
        `<option value="${p.id}">${escapeHtml(p.name)}</option>`
    ).join('');
    panchSelect.disabled = false;
}

/* ================================================================
   TABLE RENDERING
   ================================================================ */

function renderVillageTable() {
    const villages = getRecords('villages');
    const districts = getRecords('districts');
    const vidhanSabhas = getRecords('vidhanSabhas');
    const panchayats = getRecords('panchayats');

    // Lookup maps
    const districtMap = Object.fromEntries(districts.map(d => [d.id, d.name]));
    const vsMap = Object.fromEntries(vidhanSabhas.map(v => [v.id, v.name]));
    const panchMap = Object.fromEntries(panchayats.map(p => [p.id, p.name]));

    const query = (document.getElementById('village-search').value || '').toLowerCase().trim();
    const filtered = villages.filter(v => {
        if (!query) return true;
        const panchName = panchMap[v.panchayatId] || '';
        return v.name.toLowerCase().includes(query) ||
               panchName.toLowerCase().includes(query);
    });

    document.getElementById('record-count').textContent = filtered.length;

    const tbody = document.getElementById('village-tbody');

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-state-icon">🏡</div>
                        <div class="empty-state-title">No villages found</div>
                        <div class="empty-state-text">
                            ${query ? 'Try a different search.' : 'Click "Add Village" to create one.'}
                        </div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((v, index) => `
        <tr>
            <td class="row-index">${index + 1}</td>
            <td><strong>${escapeHtml(v.name)}</strong></td>
            <td>${escapeHtml(panchMap[v.panchayatId] || '—')}</td>
            <td>${escapeHtml(vsMap[v.vidhanSabhaId] || '—')}</td>
            <td>${escapeHtml(districtMap[v.districtId] || '—')}</td>
            <td>${formatDate(v.createdAt)}</td>
            <td>
                <div class="table-actions">
                    <button class="row-action-btn" onclick="editVillage('${v.id}')" title="Edit">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                    </button>
                    <button class="row-action-btn danger" onclick="deleteVillage('${v.id}')" title="Delete">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

function handleVillageSubmit(event) {
    event.preventDefault();

    const name = document.getElementById('village-name').value.trim();
    const districtId = document.getElementById('village-district').value;
    const vidhanSabhaId = document.getElementById('village-vs').value;
    const panchayatId = document.getElementById('village-panchayat').value;
    const editingId = document.getElementById('village-editing-id').value;

    if (!name || !districtId || !vidhanSabhaId || !panchayatId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    const payload = { name, districtId, vidhanSabhaId, panchayatId };

    if (editingId) {
        updateRecord('villages', editingId, payload);
        showToast('Village updated', 'success');
    } else {
        addRecord('villages', payload);
        showToast('Village added', 'success');
    }

    closeModal('village-modal');
    resetVillageForm();
    renderVillageTable();
}

function editVillage(id) {
    const v = findRecord('villages', id);
    if (!v) return;

    document.getElementById('village-modal-title').textContent = 'Edit Village';
    document.getElementById('village-name').value = v.name;
    document.getElementById('village-district').value = v.districtId;

    // Cascade dropdowns to populate them with the correct filtered lists
    onVillageDistrictChange();
    document.getElementById('village-vs').value = v.vidhanSabhaId;
    onVillageVsChange();
    document.getElementById('village-panchayat').value = v.panchayatId;

    document.getElementById('village-editing-id').value = id;
    openModal('village-modal');
}

function deleteVillage(id) {
    const v = findRecord('villages', id);
    if (!v) return;
    if (!confirm(`Delete village "${v.name}"?`)) return;

    deleteRecord('villages', id);
    showToast('Village deleted', 'success');
    renderVillageTable();
}

function resetVillageForm() {
    document.getElementById('village-modal-title').textContent = 'Add Village';
    document.getElementById('village-form').reset();
    document.getElementById('village-vs').disabled = true;
    document.getElementById('village-panchayat').disabled = true;
    document.getElementById('village-editing-id').value = '';
}

document.getElementById('village-modal').addEventListener('click', (e) => {
    if (e.target.id === 'village-modal') {
        closeModal('village-modal');
        resetVillageForm();
    }
});
