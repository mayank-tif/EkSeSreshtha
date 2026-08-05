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
   API HELPERS
   ================================================================ */

async function fetchDistricts() {
    console.log('fetchDistricts called');
    try {
        const data = await apiFetch(getUrl('district'));
        console.log('fetchDistricts result:', data);
        return data.results || data;
    } catch (e) {
        console.error('Failed to fetch districts:', e);
        return [];
    }
}

async function fetchVidhanSabhas(districtId) {
    if (!districtId) return [];
    try {
        const data = await apiFetch(getUrl('vidhan-sabha') + '?district_id=' + districtId);
        return data.results || data;
    } catch (e) {
        console.error('Failed to fetch vidhan sabhas:', e);
        return [];
    }
}

async function fetchPanchayats(vidhanSabhaId) {
    if (!vidhanSabhaId) return [];
    try {
        const data = await apiFetch(getUrl('panchayat') + '?vidhan_sabha_id=' + vidhanSabhaId);
        return data.results || data;
    } catch (e) {
        console.error('Failed to fetch panchayats:', e);
        return [];
    }
}

async function fetchVillages(panchayatId) {
    if (!panchayatId) return [];
    try {
        const data = await apiFetch(getUrl('village') + '?panchayat_id=' + panchayatId);
        return data.results || data;
    } catch (e) {
        console.error('Failed to fetch villages:', e);
        return [];
    }
}

/* ================================================================
   CACHE FOR LOCATION DATA
   ================================================================ */

const locationCache = {
    districts: null,
    vidhanSabhas: {},
    panchayats: {},
    villages: {}
};

/* ================================================================
   INITIALIZATION
   Populates the district dropdown and wires cascade behavior.
   ================================================================ */

function initLocationFilter(onChange) {
    console.log('initLocationFilter called');
    const districtSel  = document.getElementById('filter-district');
    const vsSel        = document.getElementById('filter-vs');
    const panchayatSel = document.getElementById('filter-panchayat');
    const villageSel   = document.getElementById('filter-village');

    if (!districtSel) return; // Page has no filter bar

    // Load districts from API
    loadDistricts();
    resetFilterSelect(vsSel, 'All Vidhan Sabhas');
    resetFilterSelect(panchayatSel, 'All Panchayats');
    resetFilterSelect(villageSel, 'All Villages');

    /* District change -> repopulate VS, clear the two below */
    districtSel.addEventListener('change', async () => {
        const districtId = districtSel.value;
        if (districtId) {
            const vsList = await fetchVidhanSabhas(districtId);
            locationCache.vidhanSabhas[districtId] = vsList;
            fillFilterSelect(vsSel, vsList, 'All Vidhan Sabhas');
        } else {
            // If no district selected, clear VS and below
            resetFilterSelect(vsSel, 'All Vidhan Sabhas');
            resetFilterSelect(panchayatSel, 'All Panchayats');
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Vidhan Sabha change -> repopulate Panchayat, clear Village */
    vsSel.addEventListener('change', async () => {
        const vsId = vsSel.value;
        if (vsId) {
            const pList = await fetchPanchayats(vsId);
            locationCache.panchayats[vsId] = pList;
            fillFilterSelect(panchayatSel, pList, 'All Panchayats');
        } else {
            resetFilterSelect(panchayatSel, 'All Panchayats');
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Panchayat change -> repopulate Village */
    panchayatSel.addEventListener('change', async () => {
        const pId = panchayatSel.value;
        if (pId) {
            const vList = await fetchVillages(pId);
            locationCache.villages[pId] = vList;
            fillFilterSelect(villageSel, vList, 'All Villages');
        } else {
            resetFilterSelect(villageSel, 'All Villages');
        }
        if (onChange) onChange();
    });

    /* Village change -> just re-render */
    villageSel.addEventListener('change', () => {
        if (onChange) onChange();
    });
}

async function loadDistricts() {
    console.log('loadDistricts called');
    const districtSel = document.getElementById('filter-district');
    if (!districtSel) {
        console.error('filter-district element not found');
        return;
    }
    
    if (locationCache.districts) {
        fillFilterSelect(districtSel, locationCache.districts, 'All Districts');
        return;
    }
    
    try {
        const districts = await fetchDistricts();
        console.log('loadDistricts got districts:', districts);
        locationCache.districts = districts;
        fillFilterSelect(districtSel, districts, 'All Districts');
    } catch (e) {
        console.error('loadDistricts error:', e);
    }
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
