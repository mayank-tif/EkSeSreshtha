/* ================================================================
   EK SE SRESHTHA - LOCATION FILTER COMPONENT
   ----------------------------------------------------------------
   Reusable cascading filter: District -> Vidhan Sabha ->
   Panchayat -> Village. Used on the Student List and Center
   Attendance pages (and any future list screen).

   Usage:
     1. Page HTML includes four <select> elements with ids:
          #filter-district, #filter-vs, #filter-panchayat, #filter-village
     2. Page script calls initLocationFilter(onChangeCallback)
     3. Read the current selection at any time with getLocationFilter()
     4. Check if a record's location matches with matchesLocationFilter()
   ================================================================ */

/* ================================================================
   INITIALIZATION
   Populates the district dropdown and wires cascade behavior.
   ================================================================ */

function initLocationFilter(onChange) {
    const districtSel  = document.getElementById('filter-district');
    const vsSel        = document.getElementById('filter-vs');
    const panchayatSel = document.getElementById('filter-panchayat');
    const villageSel   = document.getElementById('filter-village');

    if (!districtSel) return; // Page has no filter bar

    // Fill the district list once at startup
    fillFilterSelect(districtSel, getRecords('districts'), 'All Districts');
    resetFilterSelect(vsSel, 'All Vidhan Sabhas');
    resetFilterSelect(panchayatSel, 'All Panchayats');
    resetFilterSelect(villageSel, 'All Villages');

    /* District change -> repopulate VS, clear the two below */
    districtSel.addEventListener('change', () => {
        const districtId = districtSel.value;
        const vsList = districtId
            ? getRecords('vidhanSabhas').filter(v => v.districtId === districtId)
            : [];
        fillFilterSelect(vsSel, vsList, 'All Vidhan Sabhas');
        resetFilterSelect(panchayatSel, 'All Panchayats');
        resetFilterSelect(villageSel, 'All Villages');
        if (onChange) onChange();
    });

    /* Vidhan Sabha change -> repopulate Panchayat, clear Village */
    vsSel.addEventListener('change', () => {
        const vsId = vsSel.value;
        const pList = vsId
            ? getRecords('panchayats').filter(p => p.vidhanSabhaId === vsId)
            : [];
        fillFilterSelect(panchayatSel, pList, 'All Panchayats');
        resetFilterSelect(villageSel, 'All Villages');
        if (onChange) onChange();
    });

    /* Panchayat change -> repopulate Village */
    panchayatSel.addEventListener('change', () => {
        const pId = panchayatSel.value;
        const vList = pId
            ? getRecords('villages').filter(v => v.panchayatId === pId)
            : [];
        fillFilterSelect(villageSel, vList, 'All Villages');
        if (onChange) onChange();
    });

    /* Village change -> just re-render */
    villageSel.addEventListener('change', () => {
        if (onChange) onChange();
    });
}

/* Replace a select's options with a placeholder + record list. */
function fillFilterSelect(select, records, placeholder) {
    if (!select) return;
    select.innerHTML = `<option value="">${placeholder}</option>` +
        records.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');
    select.value = '';
}

/* Clear a select down to only its placeholder option. */
function resetFilterSelect(select, placeholder) {
    if (!select) return;
    select.innerHTML = `<option value="">${placeholder}</option>`;
    select.value = '';
}

/* ================================================================
   READING THE FILTER
   ================================================================ */

/**
 * Returns the currently selected filter ids.
 * Empty string means "no filter at that level".
 */
function getLocationFilter() {
    const val = id => {
        const el = document.getElementById(id);
        return el ? el.value : '';
    };
    return {
        districtId:  val('filter-district'),
        vsId:        val('filter-vs'),
        panchayatId: val('filter-panchayat'),
        villageId:   val('filter-village')
    };
}

/**
 * Tests whether a record carrying location ids matches the current
 * filter selection. The record must expose districtId,
 * vidhanSabhaId, panchayatId, and villageId fields (centres do).
 */
function matchesLocationFilter(record, filter) {
    if (filter.districtId  && record.districtId    !== filter.districtId)  return false;
    if (filter.vsId        && record.vidhanSabhaId !== filter.vsId)        return false;
    if (filter.panchayatId && record.panchayatId   !== filter.panchayatId) return false;
    if (filter.villageId   && record.villageId     !== filter.villageId)   return false;
    return true;
}
