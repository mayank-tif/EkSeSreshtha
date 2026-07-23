/* ================================================================
   EK SE SRESHTHA - EDUCATIONAL CENTRE SCRIPT
   ----------------------------------------------------------------
   CRUD for Educational Centres.
   Features:
   - Click-to-drop pin map location picker (simulates Google Maps)
   - 4-level cascading dropdowns (District→VS→Panchayat→Village)
   - Regional Admin / Teacher assignment
   - Rich view modal showing centre + student stats
   ================================================================ */

renderShell({
    title: 'Educational Centres',
    active: 'centres',
    breadcrumbs: [{ label: 'Educational Centre' }]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    populateCentreDistricts();
    populateStaffDropdowns();
    renderCentreTable();

    document.getElementById('centre-form').addEventListener('submit', handleCentreSubmit);
    document.getElementById('centre-search').addEventListener('input', renderCentreTable);

    // Map click to drop pin
    document.getElementById('map-canvas').addEventListener('click', handleMapClick);
});

/* ================================================================
   MAP INTERACTION
   ----------------------------------------------------------------
   When user clicks the map canvas, drop a pin at that location
   and translate the click position into fake lat/lng coordinates.
   In production this would call the Google Maps API.
   ================================================================ */

function handleMapClick(event) {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();

    // Position within the map (0 to canvas width/height)
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Position the pin visually
    const pin = document.getElementById('map-pin');
    pin.style.left = `${x}px`;
    pin.style.top = `${y}px`;
    pin.hidden = false;

    // Hide the initial hint
    const hint = canvas.querySelector('.map-picker-hint');
    if (hint) hint.style.display = 'none';

    // Fake conversion of pixel offsets into lat/lng
    // (roughly centered around Panipat: 29.39°N, 76.96°E)
    const lat = (29.5 - (y / rect.height) * 0.5).toFixed(6);
    const lng = (76.7 + (x / rect.width) * 0.5).toFixed(6);

    document.getElementById('centre-lat').value = lat;
    document.getElementById('centre-lng').value = lng;
}

/**
 * Restores a pin position from stored lat/lng when editing.
 */
function restorePin(lat, lng) {
    const canvas = document.getElementById('map-canvas');
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0) return; // Canvas not yet visible

    // Reverse the transformation used in handleMapClick
    const x = ((lng - 76.7) / 0.5) * rect.width;
    const y = ((29.5 - lat) / 0.5) * rect.height;

    const pin = document.getElementById('map-pin');
    pin.style.left = `${x}px`;
    pin.style.top = `${y}px`;
    pin.hidden = false;

    const hint = canvas.querySelector('.map-picker-hint');
    if (hint) hint.style.display = 'none';
}

/* ================================================================
   DROPDOWN POPULATION
   ================================================================ */

function populateCentreDistricts() {
    const districts = getRecords('districts');
    const select = document.getElementById('centre-district');
    select.innerHTML = '<option value="">Select district</option>' +
        districts.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('');
}

function onCentreDistrictChange() {
    const districtId = document.getElementById('centre-district').value;
    const vsSelect = document.getElementById('centre-vs');
    const panchSelect = document.getElementById('centre-panchayat');
    const villageSelect = document.getElementById('centre-village');

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

function onCentreVsChange() {
    const vsId = document.getElementById('centre-vs').value;
    const panchSelect = document.getElementById('centre-panchayat');
    const villageSelect = document.getElementById('centre-village');

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

function onCentrePanchayatChange() {
    const panchayatId = document.getElementById('centre-panchayat').value;
    const villageSelect = document.getElementById('centre-village');

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

/**
 * Loads all Regional Admins and Teachers into their assignment dropdowns.
 */
function populateStaffDropdowns() {
    const raSelect = document.getElementById('centre-ra');
    const teacherSelect = document.getElementById('centre-teacher');

    const regionalAdmins = getRecords('regionalAdmins');
    const teachers = getRecords('teachers');

    raSelect.innerHTML = '<option value="">Select Regional Admin</option>' +
        regionalAdmins.map(ra =>
            `<option value="${ra.id}">${escapeHtml(ra.name)}</option>`
        ).join('');

    teacherSelect.innerHTML = '<option value="">Select Teacher</option>' +
        teachers.map(t =>
            `<option value="${t.id}">${escapeHtml(t.name)}</option>`
        ).join('');
}

/* ================================================================
   TABLE RENDERING
   ================================================================ */

function renderCentreTable() {
    const centres = getRecords('centres');
    const villages = getRecords('villages');
    const teachers = getRecords('teachers');
    const students = getRecords('students');
    const regionalAdmins = getRecords('regionalAdmins');

    const villageMap = Object.fromEntries(villages.map(v => [v.id, v.name]));
    const teacherMap = Object.fromEntries(teachers.map(t => [t.id, t.name]));
    const adminMap = Object.fromEntries(regionalAdmins.map(a => [a.id, a.name]));

    const query = (document.getElementById('centre-search').value || '').toLowerCase().trim();
    const filtered = centres.filter(c => {
        if (!query) return true;
        const villageName = villageMap[c.villageId] || '';
        return c.name.toLowerCase().includes(query) ||
               villageName.toLowerCase().includes(query);
    });

    document.getElementById('record-count').textContent = filtered.length;

    const tbody = document.getElementById('centre-tbody');

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8">
                    <div class="empty-state">
                        <div class="empty-state-icon">🏫</div>
                        <div class="empty-state-title">No centres yet</div>
                        <div class="empty-state-text">
                            ${query ? 'Try a different search.' : 'Click "Add Centre" to get started.'}
                        </div>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((centre, index) => {
        // Count students enrolled at this centre
        const studentCount = students.filter(s => s.centreId === centre.id).length;
        const villageName = villageMap[centre.villageId] || '—';
        const teacherName = teacherMap[centre.teacherId] || 'Unassigned';
        const adminName = adminMap[centre.regionalAdminId] || 'Unassigned';

        return `
            <tr>
                <td class="row-index">${index + 1}</td>
                <td><strong>${escapeHtml(centre.name)}</strong></td>
                <td>${escapeHtml(villageName)}</td>
                <td>${escapeHtml(adminName)}</td>
                <td>${escapeHtml(teacherName)}</td>
                <td><span class="count-pill">${studentCount}</span></td>
                <td>${formatDate(centre.startDate)}</td>
                <td>
                    <div class="table-actions">
                        <button class="row-action-btn view" onclick="viewCentre('${centre.id}')" title="View details">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                        <button class="row-action-btn" onclick="editCentre('${centre.id}')" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="row-action-btn danger" onclick="deleteCentre('${centre.id}')" title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/* ================================================================
   VIEW CENTRE - Rich details modal
   ================================================================ */

function viewCentre(id) {
    const centre = findRecord('centres', id);
    if (!centre) return;

    // Resolve related record labels
    const districts = getRecords('districts');
    const vidhanSabhas = getRecords('vidhanSabhas');
    const panchayats = getRecords('panchayats');
    const villages = getRecords('villages');
    const regionalAdmins = getRecords('regionalAdmins');
    const teachers = getRecords('teachers');
    const students = getRecords('students');

    const district = districts.find(d => d.id === centre.districtId);
    const vs = vidhanSabhas.find(v => v.id === centre.vidhanSabhaId);
    const panchayat = panchayats.find(p => p.id === centre.panchayatId);
    const village = villages.find(v => v.id === centre.villageId);
    const ra = regionalAdmins.find(r => r.id === centre.regionalAdminId);
    const teacher = teachers.find(t => t.id === centre.teacherId);
    const studentCount = students.filter(s => s.centreId === id).length;

    const html = `
        <div class="centre-details">

            <!-- Header banner -->
            <div class="centre-details-hero">
                <div class="centre-details-hero-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M3 21h18M5 21V7l7-4 7 4v14"/></svg>
                </div>
                <div class="centre-details-hero-info">
                    <h2>${escapeHtml(centre.name)}</h2>
                    <p>Started ${formatDate(centre.startDate)}</p>
                </div>
                <div class="centre-details-hero-stat">
                    <div class="centre-details-hero-stat-number">${studentCount}</div>
                    <div class="centre-details-hero-stat-label">Students</div>
                </div>
            </div>

            <!-- Location grid -->
            <div class="centre-details-section">
                <h4>Location</h4>
                <div class="centre-info-grid">
                    <div class="centre-info-item">
                        <div class="centre-info-label">District</div>
                        <div class="centre-info-value">${escapeHtml(district?.name || '—')}</div>
                    </div>
                    <div class="centre-info-item">
                        <div class="centre-info-label">Vidhan Sabha</div>
                        <div class="centre-info-value">${escapeHtml(vs?.name || '—')}</div>
                    </div>
                    <div class="centre-info-item">
                        <div class="centre-info-label">Panchayat</div>
                        <div class="centre-info-value">${escapeHtml(panchayat?.name || '—')}</div>
                    </div>
                    <div class="centre-info-item">
                        <div class="centre-info-label">Village</div>
                        <div class="centre-info-value">${escapeHtml(village?.name || '—')}</div>
                    </div>
                    <div class="centre-info-item">
                        <div class="centre-info-label">Coordinates</div>
                        <div class="centre-info-value">${centre.latitude}°, ${centre.longitude}°</div>
                    </div>
                </div>
            </div>

            <!-- Staff assignments -->
            <div class="centre-details-section">
                <h4>Assigned Staff</h4>
                <div class="centre-info-grid">
                    <div class="centre-info-item">
                        <div class="centre-info-label">Regional Admin</div>
                        <div class="centre-info-value">${escapeHtml(ra?.name || 'Unassigned')}</div>
                    </div>
                    <div class="centre-info-item">
                        <div class="centre-info-label">Teacher</div>
                        <div class="centre-info-value">${escapeHtml(teacher?.name || 'Unassigned')}</div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('centre-view-body').innerHTML = html;
    openModal('centre-view-modal');
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

function handleCentreSubmit(event) {
    event.preventDefault();

    const editingId = document.getElementById('centre-editing-id').value;

    const payload = {
        name: document.getElementById('centre-name').value.trim(),
        startDate: document.getElementById('centre-start-date').value,
        districtId: document.getElementById('centre-district').value,
        vidhanSabhaId: document.getElementById('centre-vs').value,
        panchayatId: document.getElementById('centre-panchayat').value,
        villageId: document.getElementById('centre-village').value,
        regionalAdminId: document.getElementById('centre-ra').value,
        teacherId: document.getElementById('centre-teacher').value,
        latitude: parseFloat(document.getElementById('centre-lat').value),
        longitude: parseFloat(document.getElementById('centre-lng').value)
    };

    if (!payload.name || !payload.startDate || !payload.villageId ||
        isNaN(payload.latitude) || isNaN(payload.longitude)) {
        showToast('Please fill in all required fields including the map pin.', 'danger');
        return;
    }

    if (editingId) {
        updateRecord('centres', editingId, payload);
        showToast('Centre updated', 'success');
    } else {
        addRecord('centres', payload);
        showToast('Centre added', 'success');
    }

    closeModal('centre-modal');
    resetCentreForm();
    renderCentreTable();
}

function editCentre(id) {
    const centre = findRecord('centres', id);
    if (!centre) return;

    document.getElementById('centre-modal-title').textContent = 'Edit Centre';
    document.getElementById('centre-editing-id').value = id;

    document.getElementById('centre-name').value = centre.name;
    document.getElementById('centre-start-date').value = centre.startDate;
    document.getElementById('centre-lat').value = centre.latitude;
    document.getElementById('centre-lng').value = centre.longitude;
    document.getElementById('centre-district').value = centre.districtId;

    // Cascade the dropdowns
    onCentreDistrictChange();
    document.getElementById('centre-vs').value = centre.vidhanSabhaId;
    onCentreVsChange();
    document.getElementById('centre-panchayat').value = centre.panchayatId;
    onCentrePanchayatChange();
    document.getElementById('centre-village').value = centre.villageId;

    document.getElementById('centre-ra').value = centre.regionalAdminId || '';
    document.getElementById('centre-teacher').value = centre.teacherId || '';

    openModal('centre-modal');

    // Restore the pin after modal is visible
    setTimeout(() => restorePin(centre.latitude, centre.longitude), 200);
}

function deleteCentre(id) {
    const centre = findRecord('centres', id);
    if (!centre) return;

    const studentCount = getRecords('students').filter(s => s.centreId === id).length;
    let msg = `Delete centre "${centre.name}"?`;
    if (studentCount > 0) {
        msg += `\n\n${studentCount} student(s) will lose their centre assignment.`;
    }

    if (!confirm(msg)) return;

    deleteRecord('centres', id);
    showToast('Centre deleted', 'success');
    renderCentreTable();
}

function resetCentreForm() {
    document.getElementById('centre-modal-title').textContent = 'Add Educational Centre';
    document.getElementById('centre-form').reset();
    document.getElementById('centre-editing-id').value = '';
    document.getElementById('centre-vs').disabled = true;
    document.getElementById('centre-panchayat').disabled = true;
    document.getElementById('centre-village').disabled = true;
    document.getElementById('map-pin').hidden = true;

    const hint = document.querySelector('.map-picker-hint');
    if (hint) hint.style.display = '';
}

document.getElementById('centre-modal').addEventListener('click', (e) => {
    if (e.target.id === 'centre-modal') {
        closeModal('centre-modal');
        resetCentreForm();
    }
});
