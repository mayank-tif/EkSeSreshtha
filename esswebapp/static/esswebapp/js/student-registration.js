/* ================================================================
   EK SE SRESHTHA - STUDENT REGISTRATION SCRIPT
   ----------------------------------------------------------------
   Handles new student registration, including:
   - Photo upload with preview
   - All personal, family, contact, and category fields
   - Searchable centre dropdown
   - Auto-display of the selected centre's details
   ================================================================ */

/* ================================================================
   INITIALIZATION
   ================================================================ */

let state = {
    centres: [],
    schools: []
};

document.addEventListener('DOMContentLoaded', async () => {
    await loadSchools();
    await loadCentres();

    // Initialize Select2 on form dropdowns
    initSelect2(document.getElementById('student-gender'), { placeholder: 'Select gender' });
    initSelect2(document.getElementById('student-class'), { placeholder: 'Select class' });
    initSelect2(document.getElementById('student-category'), { placeholder: 'Select category' });
    initSelect2(document.getElementById('student-bpl'), { placeholder: 'Select' });
    initSelect2(document.getElementById('student-school'), { placeholder: 'Select school' });

    document.getElementById('student-form').addEventListener('submit', handleStudentSubmit);
    document.getElementById('student-image').addEventListener('change', handleStudentImageChange);

    // Close the searchable dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#centre-searchable')) {
            document.getElementById('centre-dropdown').hidden = true;
        }
    });

    // Real-time validation for mobile fields
    const mobileFields = [
        'student-contact',
        'student-whatsapp',
        'student-father-mobile',
        'student-mother-mobile'
    ];
    mobileFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('blur', () => {
                const val = el.value.trim();
                if (val && !isValidMobile(val)) {
                    showToast(`${el.labels[0]?.textContent?.replace('*','').trim() || 'Mobile'} must be 10 digits starting with 6/7/8/9`, 'danger');
                    el.focus();
                }
            });
        }
    });

    // Load an editing student if passed via URL query (?id=...)
    const params = new URLSearchParams(window.location.search);
    const editId = params.get('id');
    if (editId) {
        await editStudent(editId);
    }
});

/* ================================================================
   STUDENT PHOTO PREVIEW
   ================================================================ */

function handleStudentImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be under 2 MB.', 'danger');
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        document.getElementById('student-image-data').value = dataUrl;
        document.getElementById('student-image-preview').innerHTML =
            `<img src="${dataUrl}" alt="Student preview">`;
    };
    reader.readAsDataURL(file);
}

/* ================================================================
   LOAD SCHOOLS & CENTRES FROM API
   ================================================================ */

async function loadSchools() {
    try {
        const data = await fetchSchools({ page: 1, page_size: 1000 }, true);
        state.schools = data.results || data || [];
        const select = document.getElementById('student-school');
        select.innerHTML = '<option value="">Select school</option>' +
            state.schools.map(s => `<option value="${s.id}">${escapeHtml(s.name || s.school_name)}</option>`).join('');
    } catch (error) {
        console.error('Failed to load schools:', error);
    }
}

async function loadCentres() {
    try {
        const data = await fetchCentresForDropdown(true);
        state.centres = data;

        const optionsContainer = document.getElementById('centre-options');
        if (!optionsContainer) return;

        if (state.centres.length === 0) {
            optionsContainer.innerHTML = `
                <div class="searchable-select-option-empty">
                    No centres available. Please create a centre first.
                </div>
            `;
            return;
        }

        optionsContainer.innerHTML = state.centres.map(c => `
            <div class="searchable-select-option"
                 data-id="${c.id}"
                 data-name="${escapeHtml(c.name || c.center_name || '').toLowerCase()}"
                 onclick="selectCentre('${c.id}', '${escapeHtml(c.name || c.center_name || '').replace(/'/g, "\\'")}')"
            >
                <div style="font-weight: 500;">${escapeHtml(c.name || c.center_name)}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load centres:', error);
        showToast('Failed to load centres', 'warning');
    }
}

/* ================================================================
   SEARCHABLE CENTRE DROPDOWN
   ----------------------------------------------------------------
   Custom widget so users can type to filter the centre list.
   ================================================================ */

/**
 * Toggle the centre dropdown visibility
 */
function toggleCentreDropdown() {
    const dropdown = document.getElementById('centre-dropdown');
    const filterInput = document.getElementById('centre-filter');
    dropdown.hidden = !dropdown.hidden;
    if (!dropdown.hidden && filterInput) {
        filterInput.value = '';
        filterInput.focus();
        populateCentreOptions();
    }
}

/**
 * Filter centre options based on search input (inside dropdown)
 */
function filterCentres() {
    const search = document.getElementById('centre-filter').value.toLowerCase();
    const options = document.querySelectorAll('.searchable-select-option');
    options.forEach(opt => {
        const name = opt.dataset.name || '';
        opt.hidden = !name.includes(search);
    });
}

/**
 * Populates the options list from all centres in state.
 * The filter input searches this same list.
 */
function populateCentreOptions() {
    const centres = state.centres;
    const optionsContainer = document.getElementById('centre-options');

    if (centres.length === 0) {
        optionsContainer.innerHTML = `
            <div class="searchable-select-option-empty">
                No centres available. Please create a centre first.
            </div>
        `;
        return;
    }

    optionsContainer.innerHTML = centres.map(c => `
        <div class="searchable-select-option"
             data-id="${c.id}"
             data-name="${escapeHtml(c.name || c.center_name || '').toLowerCase()}"
             onclick="selectCentre('${c.id}', '${escapeHtml(c.name || c.center_name || '').replace(/'/g, "\\'")}')"
        >
            <div style="font-weight: 500;">${escapeHtml(c.name || c.center_name)}</div>
        </div>
    `).join('');
}

function selectCentre(centreId, centreName) {
    document.getElementById('student-centre').value = centreId;
    document.getElementById('centre-search-input').value = centreName;
    document.getElementById('centre-dropdown').hidden = true;

    // Highlight the picked option
    document.querySelectorAll('.searchable-select-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.id === centreId);
    });

    // Find the full centre object from loaded API data (not mock cache)
    const centre = state.centres.find(c => c.id == centreId);
    if (centre) {
        showCentreInfoPanel(centre);
    }
}

/**
 * Populates the info panel below the centre dropdown with
 * the centre's district/VS/Panchayat/Village/staff details.
 * @param {Object} centre - Centre object from API (already loaded in state.centres)
 */
function showCentreInfoPanel(centre) {
    if (!centre) return;

    // Centre API already returns district_name, vidhan_sabha_name, panchayat_name, village_name
    // and assigned_teacher_name, assigned_regional_admin_name
    const grid = document.getElementById('centre-info-grid');
    grid.innerHTML = `
        <div class="centre-info-item">
            <div class="centre-info-label">District</div>
            <div class="centre-info-value">${escapeHtml(centre.district_name || '—')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Vidhan Sabha</div>
            <div class="centre-info-value">${escapeHtml(centre.vidhan_sabha_name || '—')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Panchayat</div>
            <div class="centre-info-value">${escapeHtml(centre.panchayat_name || '—')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Village</div>
            <div class="centre-info-value">${escapeHtml(centre.village_name || '—')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Teacher</div>
            <div class="centre-info-value">${escapeHtml(centre.assigned_teacher_name || 'Unassigned')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Regional Admin</div>
            <div class="centre-info-value">${escapeHtml(centre.assigned_regional_admin_name || 'Unassigned')}</div>
        </div>
    `;

    document.getElementById('centre-info-panel').hidden = false;
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

async function handleStudentSubmit(event) {
    event.preventDefault();

    const editingId = document.getElementById('student-editing-id').value;

    const payload = {
        rollNo: document.getElementById('student-roll').value.trim(),
        name: document.getElementById('student-name').value.trim(),
        age: parseInt(document.getElementById('student-age').value) || null,
        gender: document.getElementById('student-gender').value,
        dob: document.getElementById('student-dob').value,
        joiningDate: document.getElementById('student-joining').value,
        activeClass: document.getElementById('student-class').value,
        fatherName: document.getElementById('student-father').value.trim(),
        motherName: document.getElementById('student-mother').value.trim(),
        fatherMobile: document.getElementById('student-father-mobile').value.trim(),
        motherMobile: document.getElementById('student-mother-mobile').value.trim(),
        fatherOccupation: document.getElementById('student-father-occ').value.trim(),
        motherOccupation: document.getElementById('student-mother-occ').value.trim(),
        contactNumber: document.getElementById('student-contact').value.trim(),
        whatsapp: document.getElementById('student-whatsapp').value.trim() ||
                  document.getElementById('student-contact').value.trim(),
        address: document.getElementById('student-address').value.trim(),
        category: document.getElementById('student-category').value,
        bpl: document.getElementById('student-bpl').value,
        schoolId: document.getElementById('student-school').value,
        centreId: document.getElementById('student-centre').value,
        image: document.getElementById('student-image-data').value || null,
        email: document.getElementById('student-email').value.trim()
    };

    // Validation
    if (!payload.rollNo || !payload.name || !payload.age ||
        !payload.activeClass || !payload.contactNumber ||
        !payload.category || !payload.centreId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    // Duplicate roll number check (excluding self on edit)
    const duplicate = state.centres.find(s =>
        s.rollNo === payload.rollNo && s.id !== editingId
    );
    if (duplicate) {
        showToast(`Roll number ${payload.rollNo} is already taken.`, 'danger');
        return;
    }

    try {
        showGlobalLoader();

        if (editingId) {
            await apiFetch(getUrl('students'), {
                method: 'PUT',
                body: JSON.stringify({ id: editingId, ...payload })
            });
            showToast('Student updated', 'success');
        } else {
            await apiFetch(getUrl('students'), {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            showToast('Student registered successfully', 'success');
        }

        resetStudentForm();

        // Return to the student list so the new/updated record is visible
        setTimeout(() => { window.location.href = '/students/'; }, 900);
    } catch (error) {
        console.error('Student save failed:', error);
        showToast('Failed to save student: ' + error.message, 'danger');
    } finally {
        hideGlobalLoader();
    }
}

/* ================================================================
   EDIT MODE (called from student list via URL param)
   ================================================================ */

async function editStudent(id) {
    showGlobalLoader();
    try {
        // Fetch student from API (not mock cache)
        const student = await apiFetch(getUrl('students') + '?id=' + id);
        if (!student) {
            showToast('Student not found', 'danger');
            return;
        }

        document.getElementById('student-form-title').textContent = 'Edit Student';
        document.getElementById('student-editing-id').value = id;

        // Map API response fields to form fields
        document.getElementById('student-roll').value = student.roll_number || student.rollNo || '';
        document.getElementById('student-name').value = student.full_name || student.name || '';
        document.getElementById('student-age').value = student.age || '';
        document.getElementById('student-gender').value = student.gender || '';

        // Format date for HTML input (yyyy-MM-dd)
        const dob = student.date_of_birth || student.dob || '';
        document.getElementById('student-dob').value = dob.split('T')[0];

        const joiningDate = student.joining_date || student.joiningDate || '';
        document.getElementById('student-joining').value = joiningDate.split('T')[0];

        document.getElementById('student-class').value = student.grade || student.active_class || student.activeClass || '';
        document.getElementById('student-father').value = student.father_name || student.fatherName || '';
        document.getElementById('student-mother').value = student.mother_name || student.motherName || '';
        document.getElementById('student-father-mobile').value = student.father_mobile_number || student.fatherMobile || '';
        document.getElementById('student-mother-mobile').value = student.mother_mobile_number || student.motherMobile || '';
        document.getElementById('student-father-occ').value = student.father_occupation || student.fatherOccupation || '';
        document.getElementById('student-mother-occ').value = student.mother_occupation || student.motherOccupation || '';
        document.getElementById('student-contact').value = student.phone_number || student.contact || student.contactNumber || '';
        document.getElementById('student-whatsapp').value = student.whatsapp || '';
        document.getElementById('student-email').value = student.email || '';
        document.getElementById('student-address').value = student.full_address || student.address || '';
        document.getElementById('student-category').value = student.category || '';

        // BPL dropdown expects 'true' or 'false'
        const bplVal = student.bpl;
        if (bplVal === true || bplVal === 'true' || bplVal === 1 || bplVal === '1') {
            setSelect2Value(document.getElementById('student-bpl'), 'true');
        } else if (bplVal === false || bplVal === 'false' || bplVal === 0 || bplVal === '0') {
            setSelect2Value(document.getElementById('student-bpl'), 'false');
        } else {
            setSelect2Value(document.getElementById('student-bpl'), '');
        }

        setSelect2Value(document.getElementById('student-school'), student.school_id || student.schoolId || '');

        // Set simple select dropdowns using setSelect2Value
        setSelect2Value(document.getElementById('student-gender'), student.gender || '');
        setSelect2Value(document.getElementById('student-class'), student.grade || student.active_class || student.activeClass || '');
        setSelect2Value(document.getElementById('student-category'), student.category || '');

        // Set centre and show info panel
        if (student.center_id || student.centreId) {
            const centreId = student.center_id || student.centreId;
            const centre = state.centres.find(c => c.id == centreId);
            if (centre) {
                selectCentre(centre.id, centre.name || centre.center_name);
            }
        }

        // Show existing photo
        const preview = document.getElementById('student-image-preview');
        if (student.image) {
            preview.innerHTML = `<img src="${student.image}" alt="Student">`;
            document.getElementById('student-image-data').value = student.image;
        }
    } catch (error) {
        console.error('Failed to load student for editing:', error);
        showToast('Failed to load student data', 'danger');
    } finally {
        hideGlobalLoader();
    }
}

function resetStudentForm() {
    document.getElementById('student-form-title').textContent = 'Register Student';
    document.getElementById('student-form').reset();
    document.getElementById('student-editing-id').value = '';
    document.getElementById('student-image-data').value = '';
    document.getElementById('centre-search-input').value = '';
    document.getElementById('centre-info-panel').hidden = true;
    document.getElementById('student-image-preview').innerHTML =
        `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

    // Reset Select2 dropdowns
    resetSelect2(document.getElementById('student-gender'), 'Select gender');
    resetSelect2(document.getElementById('student-class'), 'Select class');
    resetSelect2(document.getElementById('student-category'), 'Select category');
    resetSelect2(document.getElementById('student-bpl'), 'Select');
    resetSelect2(document.getElementById('student-school'), 'Select school');

    // Reset selected highlight in the dropdown
    document.querySelectorAll('.searchable-select-option').forEach(el =>
        el.classList.remove('selected')
    );
}