/* ================================================================
   EK SE SRESHTHA - COMMON JAVASCRIPT UTILITIES
   ----------------------------------------------------------------
   Shared helper functions used across all pages:
   - Toast notifications
   - Modal open/close
   - Formatters
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
   DATE FORMATTING FOR INPUTS
   ================================================================ */

/**
 * Formats date for HTML input[type="date"] (YYYY-MM-DD)
 * @param {string|Date} date - Date to format
 */
function formatDateForInput(date) {
    if (!date) return '';
    const d = new Date(date);
    if (isNaN(d.getTime())) return '';
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * Parses a date from various formats
 * @param {string} dateStr - Date string
 */
function parseDate(dateStr) {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return isNaN(date.getTime()) ? null : date;
}

/* ================================================================
   NUMBER FORMATTERS
   ================================================================ */

/**
 * Formats number with Indian numbering system (lakhs, crores)
 * @param {number} num - Number to format
 */
function formatIndianNumber(num) {
    if (num == null) return '—';
    return new Intl.NumberFormat('en-IN').format(num);
}

/**
 * Formats currency in INR
 * @param {number} amount - Amount
 */
function formatCurrency(amount) {
    if (amount == null) return '—';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

/* ================================================================
   DEBOUNCE HELPER
   ================================================================ */

/**
 * Debounce function to limit rate of execution
 * @param {Function} fn - Function to debounce
 * @param {number} delay - Delay in ms
 */
function debounce(fn, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/* ================================================================
   CLASS NAME HELPERS
   ================================================================ */

/**
 * Conditionally join class names
 * @param {...(string|Object|Array)} args - Class names or objects
 */
function classNames(...args) {
    return args
        .flat()
        .filter(Boolean)
        .map(arg => {
            if (typeof arg === 'string') return arg;
            if (Array.isArray(arg)) return classNames(...arg);
            if (typeof arg === 'object') {
                return Object.entries(arg)
                    .filter(([, v]) => v)
                    .map(([k]) => k)
                    .join(' ');
            }
            return '';
        })
        .join(' ');
}

/* ================================================================
   DASHBOARD RECORD HELPERS
   ----------------------------------------------------------------
   Returns mock/demo data for demonstration purposes.
   In production, these would fetch from the API.
   ================================================================ */

/**
 * Get records based on page type and user role.
 * Returns appropriate data structure for demo/testing.
 * @param {string} type - Record type: 'centres', 'students', 'teachers', etc.
 * @returns {Array} - Array of record objects
 */
function getRecords(type) {
    // Get user session from body attribute
    const session = JSON.parse(document.body.dataset.userSession || '{}');
    const isSuperAdmin = session.is_super_admin || false;
    const isRegionalAdmin = session.is_regional_admin || false;
    const districtId = session.district_id;
    
    // Base mock records
    const mockRecords = {
        centres: [
            { id: 1, name: 'Rural School Centre', status: 'Active', studentCount: 150, attendancePercent: 85 },
            { id: 2, name: 'Urban Learning Hub', status: 'Active', studentCount: 200, attendancePercent: 92 },
            { id: 3, name: 'District HQ Centre', status: 'Active', studentCount: 350, attendancePercent: 78 }
        ],
        students: [
            { id: 1, name: 'Rahul Sharma', class: '5', section: 'A', attendance: 95 },
            { id: 2, name: 'Priya Patel', class: '6', section: 'B', attendance: 88 },
            { id: 3, name: 'Amit Kumar', class: '5', section: 'A', attendance: 92 },
            { id: 4, name: 'Sneha Das', class: '7', section: 'C', attendance: 78 },
            { id: 5, name: 'Rohit Verma', class: '6', section: 'B', attendance: 96 }
        ],
        teachers: [
            { id: 1, name: 'Sarita Devi', subject: 'Mathematics', experience: 8 },
            { id: 2, name: 'Mahesh Prasad', subject: 'Science', experience: 12 },
            { id: 3, name: 'Lakshmi Naidu', subject: 'English', experience: 6 }
        ],
        districts: [
            { id: 1, name: 'Patna', code: 'PAT' },
            { id: 2, name: 'Varanasi', code: 'VAR' },
            { id: 3, name: 'Gaya', code: 'GAY' }
        ],
        vidhanSabhas: [
            { id: 1, name: 'Patna Sagul', code: 'PS-1' },
            { id: 2, name: 'Varanasi Nagar', code: 'VN-1' }
        ],
        panchayats: [
            { id: 1, name: 'Bara Bara', code: 'BB-001' },
            { id: 2, name: 'Dhumarpur', code: 'DP-002' }
        ],
        villages: [
            { id: 1, name: 'Khusraupur', code: 'KHS-01' },
            { id: 2, name: 'Bhagwanpur', code: 'BHG-02' }
        ],
        regionalAdmins: [
            { id: 1, name: 'Regional Admin 1', district: 'Patna' }
        ],
        attendance: [
            { date: '2026-07-20', percentage: 85 },
            { date: '2026-07-21', percentage: 88 },
            { date: '2026-07-22', percentage: 92 },
            { date: '2026-07-23', percentage: 87 },
            { date: '2026-07-24', percentage: 91 }
        ]
    };
    
    // Return records or filtered based on role
    const records = mockRecords[type] || [];
    
    // Filter for regional admin - only show records for their district
    if (isRegionalAdmin && type === 'students') {
        return records.filter(s => s.districtId === districtId);
    }
    
    return records;
}

// Export for module systems (optional)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showToast,
        openModal,
        closeModal,
        formatDate,
        getInitials,
        escapeHtml,
        formatDateForInput,
        parseDate,
        formatIndianNumber,
        formatCurrency,
        debounce,
        classNames,
        getRecords
    };
}