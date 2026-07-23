/* ================================================================
   EK SE SRESHTHA - CENTER ATTENDANCE (LIST PAGE)
   ----------------------------------------------------------------
   Table list view of every educational centre. Each row shows:
     - Center name + location chain (District > VS > Panchayat > Village)
     - Assigned Teacher
     - Assigned Regional Admin
     - Total number of students
     - Average attendance (with mini progress bar)
   Toolbar: free-text search (left) + cascading location filters
   (right, see location-filter.js) + a live count badge.
   Clicking a row opens center-detail.html?id=<centreId>.
   ================================================================ */

/* Shared shell */
renderShell({
    title: 'Center Attendance',
    active: 'attendance',
    breadcrumbs: [{ label: 'Center Attendance' }]
});

/* Initialize once DOM is ready. */
document.addEventListener('DOMContentLoaded', () => {
    // Cascading District -> VS -> Panchayat -> Village filter;
    // every change re-renders the table and the live count.
    initLocationFilter(renderCentreTable);
    renderCentreTable();
});

/* ================================================================
   RENDER CENTRE TABLE
   Applies the location filter + search, then paints one row
   per matching centre.
   ================================================================ */

function renderCentreTable() {
    const tbody = document.getElementById('centre-table-body');
    const searchTerm = document.getElementById('centre-search').value.trim().toLowerCase();

    const centres    = getRecords('centres');
    const students   = getRecords('students');
    const teachers   = getRecords('teachers');
    const admins     = getRecords('regionalAdmins');
    const districts  = getRecords('districts');
    const vsList     = getRecords('vidhanSabhas');
    const panchayats = getRecords('panchayats');
    const villages   = getRecords('villages');

    // Quick lookup maps id -> name
    const teacherMap   = Object.fromEntries(teachers.map(t => [t.id, t.name]));
    const adminMap     = Object.fromEntries(admins.map(a => [a.id, a.name]));
    const districtMap  = Object.fromEntries(districts.map(d => [d.id, d.name]));
    const vsMap        = Object.fromEntries(vsList.map(v => [v.id, v.name]));
    const panchayatMap = Object.fromEntries(panchayats.map(p => [p.id, p.name]));
    const villageMap   = Object.fromEntries(villages.map(v => [v.id, v.name]));

    // ------------------------------------------------------------
    // Filter chain: location cascade, then free-text search
    // (search matches centre / teacher / admin / village names)
    // ------------------------------------------------------------
    const locFilter = getLocationFilter();
    let filtered = centres.filter(c => matchesLocationFilter(c, locFilter));

    if (searchTerm) {
        filtered = filtered.filter(c =>
            c.name.toLowerCase().includes(searchTerm) ||
            (teacherMap[c.teacherId] || '').toLowerCase().includes(searchTerm) ||
            (adminMap[c.regionalAdminId] || '').toLowerCase().includes(searchTerm) ||
            (villageMap[c.villageId] || '').toLowerCase().includes(searchTerm)
        );
    }

    // Live count badge reflects the current filter selection
    const anyFilter = searchTerm ||
        locFilter.districtId || locFilter.vsId || locFilter.panchayatId || locFilter.villageId;
    document.getElementById('centre-count').textContent = anyFilter
        ? `${filtered.length} / ${centres.length} centres`
        : `${centres.length} centre${centres.length === 1 ? '' : 's'}`;

    // Empty state
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="table-empty">
                ${anyFilter
                    ? 'No centres match your filters.'
                    : 'No centres yet. Add one from Educational Centre.'}
            </td></tr>
        `;
        return;
    }

    // Paint one row per centre. The whole row navigates to the
    // detail page (plus an explicit eye button for clarity).
    tbody.innerHTML = filtered.map(centre => {
        const studentCount  = students.filter(s => s.centreId === centre.id).length;
        const attendancePct = computeCentreAveragePct(centre.id);
        const teacherName   = teacherMap[centre.teacherId] || 'Unassigned';
        const adminName     = adminMap[centre.regionalAdminId] || 'Unassigned';

        // Location chain with graceful fallbacks
        const chainParts = [
            districtMap[centre.districtId],
            vsMap[centre.vidhanSabhaId],
            panchayatMap[centre.panchayatId],
            villageMap[centre.villageId]
        ].map(n => n || '—');

        const barClass = attendancePct < 60 ? 'low' : attendancePct < 80 ? 'medium' : '';

        return `
            <tr class="centre-row" onclick="openCentreDetail('${centre.id}')">
                <td>
                    <div class="centre-row-name">${escapeHtml(centre.name)}</div>
                    <div class="centre-row-chain">
                        ${chainParts.map((name, i) => `
                            <span class="centre-row-chain-part">${escapeHtml(name)}</span>
                            ${i < 3 ? '<span class="centre-row-chain-sep">&rsaquo;</span>' : ''}
                        `).join('')}
                    </div>
                </td>
                <td>${escapeHtml(teacherName)}</td>
                <td>${escapeHtml(adminName)}</td>
                <td><span class="count-pill">${studentCount}</span></td>
                <td>
                    <div class="attendance-pct">
                        <div class="attendance-pct-bar">
                            <div class="attendance-pct-fill ${barClass}" style="width:${attendancePct}%;"></div>
                        </div>
                        <span>${attendancePct}%</span>
                    </div>
                </td>
                <td>
                    <button class="btn-icon" title="View attendance"
                            onclick="event.stopPropagation(); openCentreDetail('${centre.id}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                             stroke="currentColor" stroke-width="2"
                             stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

/* Navigate to the 4-tab centre detail page. */
function openCentreDetail(centreId) {
    window.location.href = `center-detail.html?id=${centreId}`;
}

/* ================================================================
   FAKE ATTENDANCE AVERAGE
   ----------------------------------------------------------------
   Stable pseudo-random percentage per centre so the value doesn't
   jump between page loads. Real values come from the mobile app.
   ================================================================ */

function computeCentreAveragePct(centreId) {
    // Simple deterministic hash from the centre id
    let hash = 0;
    for (let i = 0; i < centreId.length; i++) {
        hash = ((hash << 5) - hash + centreId.charCodeAt(i)) | 0;
    }
    // Range 72 - 96
    return 72 + (Math.abs(hash) % 25);
}
