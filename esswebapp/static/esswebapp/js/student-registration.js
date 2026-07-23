/* ================================================================
   EK SE SRESHTHA - STUDENT REGISTRATION SCRIPT
   ----------------------------------------------------------------
   Handles new student registration, including:
   - Photo upload with preview
   - All personal, family, contact, and category fields
   - Searchable centre dropdown
   - Auto-display of the selected centre's details
   ================================================================ */

renderShell({
    title: 'Student Registration',
    active: 'student-registration',
    breadcrumbs: [
        { label: 'Students' },
        { label: 'Student Registration' }
    ]
});

/* ================================================================
   INITIALIZATION
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    populateSchoolDropdown();
    populateCentreOptions();

    document.getElementById('student-form').addEventListener('submit', handleStudentSubmit);
    document.getElementById('student-image').addEventListener('change', handleStudentImageChange);

    // Close the searchable dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#centre-searchable')) {
            document.getElementById('centre-dropdown').hidden = true;
        }
    });

    // Load an editing student if passed via URL query (?id=...)
    const params = new URLSearchParams(window.location.search);
    const editId = params.get('id');
    if (editId) {
        editStudent(editId);
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
   SCHOOL DROPDOWN
   ================================================================ */

function populateSchoolDropdown() {
    const schools = getRecords('schools');
    const select = document.getElementById('student-school');
    select.innerHTML = '<option value="">Select school</option>' +
        schools.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
}

/* ================================================================
   SEARCHABLE CENTRE DROPDOWN
   ----------------------------------------------------------------
   Custom widget so users can type to filter the centre list.
   ================================================================ */

/**
 * Populates the options list from all centres in storage.
 * The filter input searches this same list.
 */
function populateCentreOptions() {
    const centres = getRecords('centres');
    const villages = getRecords('villages');
    const villageMap = Object.fromEntries(villages.map(v => [v.id, v.name]));

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
             data-name="${escapeHtml(c.name).toLowerCase()}"
             onclick="selectCentre('${c.id}', '${escapeHtml(c.name).replace(/'/g, "\\'")}')"
        >
            <div style="font-weight: 500;">${escapeHtml(c.name)}</div>
            <div style="font-size: var(--text-xs); color: var(--gray-500); margin-top: 2px;">
                ${escapeHtml(villageMap[c.villageId] || 'Location unknown')}
            </div>
        </div>
    `).join('');
}

/**
 * Toggles the dropdown open/closed.
 */
function toggleCentreDropdown() {
    const dropdown = document.getElementById('centre-dropdown');
    dropdown.hidden = !dropdown.hidden;
    if (!dropdown.hidden) {
        document.getElementById('centre-filter').focus();
    }
}

/* Close the dropdown when the user clicks anywhere outside the
   searchable select, so it never lingers over the info panel. */
document.addEventListener('click', (event) => {
    const dropdown = document.getElementById('centre-dropdown');
    if (!dropdown || dropdown.hidden) return;
    const wrapper = event.target.closest('.searchable-select');
    if (!wrapper) dropdown.hidden = true;
});

/* Escape key also dismisses the dropdown. */
document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const dropdown = document.getElementById('centre-dropdown');
    if (dropdown && !dropdown.hidden) dropdown.hidden = true;
});

/**
 * Filters visible options based on typed text.
 */
function filterCentres() {
    const filter = document.getElementById('centre-filter').value.toLowerCase().trim();
    const options = document.querySelectorAll('.searchable-select-option');

    let visibleCount = 0;
    options.forEach(opt => {
        const name = opt.dataset.name || '';
        const matches = !filter || name.includes(filter);
        opt.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
    });

    // Show a "no results" message if nothing matches
    const container = document.getElementById('centre-options');
    let emptyMsg = container.querySelector('.searchable-select-option-empty[data-dynamic]');
    if (visibleCount === 0 && filter) {
        if (!emptyMsg) {
            const el = document.createElement('div');
            el.className = 'searchable-select-option-empty';
            el.dataset.dynamic = 'true';
            el.textContent = `No centres matching "${filter}"`;
            container.appendChild(el);
        } else {
            emptyMsg.textContent = `No centres matching "${filter}"`;
        }
    } else if (emptyMsg) {
        emptyMsg.remove();
    }
}

/**
 * Called when the user picks a centre from the dropdown.
 * Stores the ID, shows the name in the input, and reveals the
 * details panel below.
 */
function selectCentre(centreId, centreName) {
    document.getElementById('student-centre').value = centreId;
    document.getElementById('centre-search-input').value = centreName;
    document.getElementById('centre-dropdown').hidden = true;

    // Highlight the picked option
    document.querySelectorAll('.searchable-select-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.id === centreId);
    });

    showCentreInfoPanel(centreId);
}

/**
 * Populates the info panel below the centre dropdown with
 * the centre's district/VS/Panchayat/Village/staff details.
 */
function showCentreInfoPanel(centreId) {
    const centre = findRecord('centres', centreId);
    if (!centre) return;

    const district = findRecord('districts', centre.districtId);
    const vs = findRecord('vidhanSabhas', centre.vidhanSabhaId);
    const panchayat = findRecord('panchayats', centre.panchayatId);
    const village = findRecord('villages', centre.villageId);
    const ra = findRecord('regionalAdmins', centre.regionalAdminId);
    const teacher = findRecord('teachers', centre.teacherId);

    const grid = document.getElementById('centre-info-grid');
    grid.innerHTML = `
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
            <div class="centre-info-label">Regional Admin</div>
            <div class="centre-info-value">${escapeHtml(ra?.name || 'Unassigned')}</div>
        </div>
        <div class="centre-info-item">
            <div class="centre-info-label">Teacher</div>
            <div class="centre-info-value">${escapeHtml(teacher?.name || 'Unassigned')}</div>
        </div>
    `;

    document.getElementById('centre-info-panel').hidden = false;
}

/* ================================================================
   FORM SUBMISSION
   ================================================================ */

function handleStudentSubmit(event) {
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
        active: true
    };

    // Validation
    if (!payload.rollNo || !payload.name || !payload.age ||
        !payload.activeClass || !payload.contactNumber ||
        !payload.category || !payload.centreId) {
        showToast('Please fill in all required fields.', 'danger');
        return;
    }

    // Duplicate roll number check (excluding self on edit)
    const duplicate = getRecords('students').find(s =>
        s.rollNo === payload.rollNo && s.id !== editingId
    );
    if (duplicate) {
        showToast(`Roll number ${payload.rollNo} is already taken.`, 'danger');
        return;
    }

    if (editingId) {
        updateRecord('students', editingId, payload);
        showToast('Student updated', 'success');
    } else {
        addRecord('students', payload);
        showToast('Student registered successfully', 'success');
    }

    resetStudentForm();

    // Return to the student list so the new/updated record is visible
    setTimeout(() => { window.location.href = 'student-list.html'; }, 900);
}

/* ================================================================
   EDIT MODE (called from attendance page via URL param)
   ================================================================ */

function editStudent(id) {
    const student = findRecord('students', id);
    if (!student) return;

    document.getElementById('student-form-title').textContent = 'Edit Student';
    document.getElementById('student-editing-id').value = id;

    document.getElementById('student-roll').value = student.rollNo || '';
    document.getElementById('student-name').value = student.name || '';
    document.getElementById('student-age').value = student.age || '';
    document.getElementById('student-gender').value = student.gender || '';
    document.getElementById('student-dob').value = student.dob || '';
    document.getElementById('student-joining').value = student.joiningDate || '';
    document.getElementById('student-class').value = student.activeClass || '';
    document.getElementById('student-father').value = student.fatherName || '';
    document.getElementById('student-mother').value = student.motherName || '';
    document.getElementById('student-father-mobile').value = student.fatherMobile || '';
    document.getElementById('student-mother-mobile').value = student.motherMobile || '';
    document.getElementById('student-father-occ').value = student.fatherOccupation || '';
    document.getElementById('student-mother-occ').value = student.motherOccupation || '';
    document.getElementById('student-contact').value = student.contactNumber || '';
    document.getElementById('student-whatsapp').value = student.whatsapp || '';
    document.getElementById('student-address').value = student.address || '';
    document.getElementById('student-category').value = student.category || '';
    document.getElementById('student-bpl').value = student.bpl || '';
    document.getElementById('student-school').value = student.schoolId || '';

    // Set centre and show info panel
    if (student.centreId) {
        const centre = findRecord('centres', student.centreId);
        if (centre) {
            selectCentre(centre.id, centre.name);
        }
    }

    // Show existing photo
    const preview = document.getElementById('student-image-preview');
    if (student.image) {
        preview.innerHTML = `<img src="${student.image}" alt="Student">`;
        document.getElementById('student-image-data').value = student.image;
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

    // Reset selected highlight in the dropdown
    document.querySelectorAll('.searchable-select-option').forEach(el =>
        el.classList.remove('selected')
    );
}
