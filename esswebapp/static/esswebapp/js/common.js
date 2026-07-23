/* ================================================================
   EK SE SRESHTHA - COMMON JAVASCRIPT UTILITIES
   ----------------------------------------------------------------
   Shared helper functions used across all pages:
   - Toast notifications
   - Modal open/close
   - Local storage helpers (simulated data layer)
   - Formatters
   - Authentication guards
   ================================================================ */

/* ================================================================
   TOAST NOTIFICATION SYSTEM
   ----------------------------------------------------------------
   Shows temporary feedback messages at the top-right corner.
   Usage: showToast('Saved successfully', 'success')
   ================================================================ */

/**
 * Ensures a toast container exists on the page.
 * Creates one on first use so pages don't need to include it in HTML.
 */
function ensureToastContainer() {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}

/**
 * Displays a toast notification.
 * @param {string} message - The text to show
 * @param {string} type - One of: 'success', 'danger', 'warning', 'info'
 * @param {number} duration - How long the toast stays (ms)
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = ensureToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    // Icon prefix based on type
    const iconMap = {
        success: '✓',
        danger: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    toast.innerHTML = `
        <span class="toast-icon">${iconMap[type] || 'ℹ'}</span>
        <span class="toast-message">${message}</span>
    `;

    container.appendChild(toast);

    // Auto remove after duration
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ================================================================
   MODAL HELPERS
   ----------------------------------------------------------------
   Open and close modal dialogs by ID.
   ================================================================ */

/**
 * Shows a modal by adding the 'active' class.
 * @param {string} modalId - The DOM id of the modal-backdrop element
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

/**
 * Hides a modal.
 * @param {string} modalId - The DOM id of the modal-backdrop element
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/* ================================================================
   LOCAL STORAGE DATA LAYER
   ----------------------------------------------------------------
   Since this is a frontend demo, we simulate a database using
   localStorage. Each "table" is a JSON array under a specific key.
   In production, replace these with real API calls.
   ================================================================ */

/**
 * Fetches records from a simulated table.
 * @param {string} table - Table name (e.g., 'districts', 'students')
 * @returns {Array} - Array of records
 */
function getRecords(table) {
    try {
        const data = localStorage.getItem(`ess_${table}`);
        return data ? JSON.parse(data) : [];
    } catch (err) {
        console.error(`Failed to read ${table}:`, err);
        return [];
    }
}

/**
 * Saves the full record array back to storage.
 * @param {string} table - Table name
 * @param {Array} records - Full array to persist
 */
function saveRecords(table, records) {
    try {
        localStorage.setItem(`ess_${table}`, JSON.stringify(records));
    } catch (err) {
        console.error(`Failed to write ${table}:`, err);
        showToast('Storage error. Please try again.', 'danger');
    }
}

/**
 * Adds a new record with an auto-generated ID and timestamp.
 * @param {string} table - Table name
 * @param {Object} record - The record object to add
 * @returns {Object} - The saved record with id + createdAt
 */
function addRecord(table, record) {
    const records = getRecords(table);
    const newRecord = {
        id: Date.now().toString(),
        createdAt: new Date().toISOString(),
        ...record
    };
    records.push(newRecord);
    saveRecords(table, records);
    return newRecord;
}

/**
 * Updates a record by ID.
 * @param {string} table - Table name
 * @param {string} id - Record ID
 * @param {Object} updates - Fields to merge in
 */
function updateRecord(table, id, updates) {
    const records = getRecords(table);
    const index = records.findIndex(r => r.id === id);
    if (index !== -1) {
        records[index] = { ...records[index], ...updates };
        saveRecords(table, records);
        return records[index];
    }
    return null;
}

/**
 * Deletes a record by ID.
 * @param {string} table - Table name
 * @param {string} id - Record ID
 */
function deleteRecord(table, id) {
    const records = getRecords(table).filter(r => r.id !== id);
    saveRecords(table, records);
}

/**
 * Finds a single record by ID.
 * @param {string} table - Table name
 * @param {string} id - Record ID
 */
function findRecord(table, id) {
    return getRecords(table).find(r => r.id === id) || null;
}

/* ================================================================
   FORMATTERS
   ----------------------------------------------------------------
   Pure functions to format dates, numbers, etc. for display.
   ================================================================ */

/**
 * Formats an ISO date string as "DD MMM YYYY" (e.g. "22 Jul 2026").
 * @param {string} isoDate - ISO date string
 */
function formatDate(isoDate) {
    if (!isoDate) return '—';
    const date = new Date(isoDate);
    if (isNaN(date.getTime())) return '—';
    return date.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

/**
 * Returns just the initials of a full name, uppercase.
 * @param {string} name - Full name
 */
function getInitials(name) {
    if (!name) return '?';
    return name
        .trim()
        .split(/\s+/)
        .map(part => part[0])
        .slice(0, 2)
        .join('')
        .toUpperCase();
}

/**
 * Escapes HTML special characters to prevent XSS when injecting
 * user data into innerHTML.
 * @param {string} str - Raw string
 */
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* ================================================================
   AUTHENTICATION GUARD
   ----------------------------------------------------------------
   Redirect to login if the user isn't authenticated.
   ================================================================ */

/**
 * Checks if a user session exists. Redirects to login otherwise.
 * Call this at the top of every protected page's script.
 */
function requireAuth() {
    const session = localStorage.getItem('ess_session');
    if (!session) {
        window.location.href = '/index.html';
    }
    return session ? JSON.parse(session) : null;
}

/**
 * Ends the user session and returns to login.
 */
function logout() {
    localStorage.removeItem('ess_session');
    window.location.href = '/index.html';
}

/* ================================================================
   SEED DEMO DATA
   ----------------------------------------------------------------
   On first load, populate localStorage with sample records so the
   UI has content to display right away.
   ================================================================ */

/**
 * Loads sample data on first run. Idempotent - won't overwrite.
 */
function seedDemoData() {
    /* --------------------------------------------------------------
       SELF-HEALING SEED
       Instead of a single one-shot flag, each table is seeded
       individually and ONLY if its storage key is completely
       missing. This repairs partial/corrupted storage (e.g. from
       older builds) without ever overwriting user-entered data or
       resurrecting records the user deliberately deleted (a
       deleted-out table still exists as an empty array "[]").
       -------------------------------------------------------------- */
    function seedTable(key, records) {
        if (localStorage.getItem(key) === null) {
            localStorage.setItem(key, JSON.stringify(records));
        }
    }

    // Districts
    const districts = [
        { id: 'd1', name: 'Panipat', createdAt: new Date().toISOString() },
        { id: 'd2', name: 'Karnal', createdAt: new Date().toISOString() },
        { id: 'd3', name: 'Sonipat', createdAt: new Date().toISOString() }
    ];
    seedTable('ess_districts', districts);

    // Vidhan Sabha constituencies
    const vidhanSabhas = [
        { id: 'v1', name: 'Panipat Rural', districtId: 'd1', createdAt: new Date().toISOString() },
        { id: 'v2', name: 'Panipat City', districtId: 'd1', createdAt: new Date().toISOString() },
        { id: 'v3', name: 'Karnal', districtId: 'd2', createdAt: new Date().toISOString() },
        { id: 'v4', name: 'Sonipat', districtId: 'd3', createdAt: new Date().toISOString() }
    ];
    seedTable('ess_vidhanSabhas', vidhanSabhas);

    // Panchayats
    const panchayats = [
        { id: 'p1', name: 'Bapoli', districtId: 'd1', vidhanSabhaId: 'v1', createdAt: new Date().toISOString() },
        { id: 'p2', name: 'Nara', districtId: 'd1', vidhanSabhaId: 'v1', createdAt: new Date().toISOString() },
        { id: 'p3', name: 'Sanoli', districtId: 'd1', vidhanSabhaId: 'v2', createdAt: new Date().toISOString() },
        { id: 'p4', name: 'Nilokheri', districtId: 'd2', vidhanSabhaId: 'v3', createdAt: new Date().toISOString() }
    ];
    seedTable('ess_panchayats', panchayats);

    // Villages
    const villages = [
        { id: 'vl1', name: 'Ugra Kheri', districtId: 'd1', vidhanSabhaId: 'v1', panchayatId: 'p1', createdAt: new Date().toISOString() },
        { id: 'vl2', name: 'Bhalor', districtId: 'd1', vidhanSabhaId: 'v1', panchayatId: 'p2', createdAt: new Date().toISOString() },
        { id: 'vl3', name: 'Diwana', districtId: 'd1', vidhanSabhaId: 'v2', panchayatId: 'p3', createdAt: new Date().toISOString() }
    ];
    seedTable('ess_villages', villages);

    // Sample schools
    const schools = [
        { id: 's1', name: 'Govt. Primary School, Ugra Kheri', createdAt: new Date().toISOString() },
        { id: 's2', name: 'Govt. Middle School, Bhalor', createdAt: new Date().toISOString() },
        { id: 's3', name: 'Govt. High School, Diwana', createdAt: new Date().toISOString() }
    ];
    seedTable('ess_schools', schools);

    // Sample regional admin
    const regionalAdmins = [
        {
            id: 'ra1',
            name: 'Rajesh Kumar',
            email: 'rajesh@ekseshreshtha.org',
            phone: '9876543210',
            whatsapp: '9876543210',
            age: 34,
            gender: 'Male',
            dob: '1990-05-15',
            enrollmentDate: '2024-01-10',
            districtId: 'd1',
            vidhanSabhaId: 'v1',
            panchayatId: 'p1',
            createdAt: new Date().toISOString()
        }
    ];
    seedTable('ess_regionalAdmins', regionalAdmins);

    // Sample teacher
    const teachers = [
        {
            id: 't1',
            name: 'Priya Sharma',
            email: 'priya@ekseshreshtha.org',
            phone: '9876543211',
            whatsapp: '9876543211',
            age: 28,
            gender: 'Female',
            dob: '1996-08-22',
            enrollmentDate: '2024-03-15',
            qualification: 'B.Ed, M.A. Hindi',
            districtId: 'd1',
            vidhanSabhaId: 'v1',
            panchayatId: 'p1',
            villageId: 'vl1',
            guardianName: 'Ramesh Sharma',
            guardianNo: '9876543212',
            address: 'Village Ugra Kheri, Panipat',
            createdAt: new Date().toISOString()
        }
    ];
    seedTable('ess_teachers', teachers);

    // Sample educational centre
    const centres = [
        {
            id: 'c1',
            name: 'Ek Se Sreshtha Centre - Ugra Kheri',
            startDate: '2024-04-01',
            districtId: 'd1',
            vidhanSabhaId: 'v1',
            panchayatId: 'p1',
            villageId: 'vl1',
            regionalAdminId: 'ra1',
            teacherId: 't1',
            latitude: 29.3909,
            longitude: 76.9635,
            createdAt: new Date().toISOString()
        }
    ];
    seedTable('ess_centres', centres);

    // Sample students
    const students = [
        {
            id: 'st1',
            rollNo: '10850',
            name: 'Aarav Kumar',
            age: 8,
            gender: 'Male',
            dob: '2017-06-12',
            joiningDate: '2024-04-15',
            activeClass: 'Class 3',
            fatherName: 'Suresh Kumar',
            motherName: 'Sunita Devi',
            fatherMobile: '9812345670',
            motherMobile: '9812345671',
            fatherOccupation: 'Farmer',
            motherOccupation: 'Homemaker',
            contactNumber: '9812345670',
            whatsapp: '9812345670',
            category: 'OBC',
            bpl: 'Yes',
            address: 'Village Ugra Kheri, Panipat',
            schoolId: 's1',
            centreId: 'c1',
            active: true,
            createdAt: new Date().toISOString()
        },
        {
            id: 'st2',
            rollNo: '10851',
            name: 'Diya Verma',
            age: 7,
            gender: 'Female',
            dob: '2018-02-05',
            joiningDate: '2024-04-15',
            activeClass: 'Class 2',
            fatherName: 'Vinod Verma',
            motherName: 'Anita Verma',
            fatherMobile: '9812345672',
            motherMobile: '9812345673',
            fatherOccupation: 'Shopkeeper',
            motherOccupation: 'Homemaker',
            contactNumber: '9812345672',
            whatsapp: '9812345672',
            category: 'General',
            bpl: 'No',
            address: 'Village Ugra Kheri, Panipat',
            schoolId: 's1',
            centreId: 'c1',
            active: true,
            createdAt: new Date().toISOString()
        }
    ];
    seedTable('ess_students', students);

    // Default super admin login
    const superAdmins = [
        {
            id: 'sa1',
            name: 'Admin',
            email: 'admin@ekseshreshtha.org',
            password: 'admin123',
            age: 35,
            gender: 'Male',
            role: 'super_admin',
            createdAt: new Date().toISOString()
        }
    ];
    seedTable('ess_superAdmins', superAdmins);

    localStorage.setItem('ess_seeded', 'true');
}

// Seed data as soon as this script loads
seedDemoData();
