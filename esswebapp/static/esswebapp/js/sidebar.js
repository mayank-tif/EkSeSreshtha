/* ================================================================
   EK SE SRESHTHA - SIDEBAR & LAYOUT SCRIPT
   ----------------------------------------------------------------
   Renders the shared sidebar navigation and top header.
   Every internal page includes this script so navigation stays
   in one place instead of being duplicated across HTML files.

   Usage in each page:
       <div id="app-shell"></div>
       <script src="../js/common.js"></script>
       <script src="../js/sidebar.js"></script>
       <script>
           renderShell({
               title: 'Page Title',
               active: 'district',   // matches nav item id
               breadcrumbs: [{label: 'Constituency'}, {label: 'District'}]
           });
       </script>
   ================================================================ */

/* ================================================================
   NAVIGATION STRUCTURE
   ----------------------------------------------------------------
   Central definition of the whole navigation tree.
   Add/remove menu items here and they'll appear on every page.
   ================================================================ */

const NAV_ITEMS = [
    {
        id: 'dashboard',
        label: 'Dashboard',
        icon: 'grid',
        href: '/pages/dashboard.html'
    },
    {
        id: 'constituency',
        label: 'Constituency',
        icon: 'map',
        children: [
            { id: 'district', label: 'District', href: '/pages/constituency/district.html' },
            { id: 'vidhan-sabha', label: 'Vidhan Sabha', href: '/pages/constituency/vidhan-sabha.html' },
            { id: 'panchayat', label: 'Panchayat', href: '/pages/constituency/panchayat.html' },
            { id: 'village', label: 'Village', href: '/pages/constituency/village.html' }
        ]
    },
    {
        id: 'users',
        label: 'Users',
        icon: 'users',
        children: [
            { id: 'super-admin', label: 'Super Admin', href: '/pages/users/super-admin.html' },
            { id: 'regional-admin', label: 'Regional Admin', href: '/pages/users/regional-admin.html' },
            { id: 'teacher', label: 'Teacher', href: '/pages/users/teacher.html' }
        ]
    },
    {
        id: 'centres',
        label: 'Educational Centre',
        icon: 'building',
        href: '/pages/centres/educational-centre.html'
    },
    {
        id: 'students',
        label: 'Students',
        icon: 'user-graduate',
        children: [
            { id: 'student-registration', label: 'Student Registration', href: '/pages/students/student-list.html' },
            { id: 'school-list', label: 'School List', href: '/pages/students/school-list.html' }
        ]
    },
    {
        id: 'attendance',
        label: 'Center Attendance',
        icon: 'clipboard',
        href: '/pages/attendance/center-attendance.html'
    }
];

/* ================================================================
   ICON LIBRARY
   ----------------------------------------------------------------
   Inline SVG icons used in the sidebar. Keeping them here avoids
   depending on an icon font.
   ================================================================ */

const ICONS = {
    grid: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    map: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>',
    users: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    building: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l7-4 7 4v14"/><path d="M9 9h1"/><path d="M9 13h1"/><path d="M9 17h1"/><path d="M14 9h1"/><path d="M14 13h1"/><path d="M14 17h1"/></svg>',
    'user-graduate': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>',
    clipboard: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6"/><path d="M9 16h6"/></svg>',
    chevron: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    menu: '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
    bell: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    logout: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>'
};

/* ================================================================
   PATH RESOLUTION
   ----------------------------------------------------------------
   Convert absolute paths like "/pages/foo.html" to relative paths
   that work regardless of hosting depth.
   ================================================================ */

/**
 * Rewrites a leading "/" path so it resolves from the current page.
 * When the site is served from a subfolder or opened via file://,
 * absolute paths break. This converts them to relative.
 */
function resolvePath(path) {
    // Detect how many levels deep the current page is
    const pathname = window.location.pathname;
    const depth = (pathname.match(/\//g) || []).length - 1;
    const prefix = depth > 0 ? '../'.repeat(depth) : './';
    return prefix + path.replace(/^\//, '');
}

/* ================================================================
   SIDEBAR RENDERER
   ----------------------------------------------------------------
   Builds the entire sidebar DOM from NAV_ITEMS.
   ================================================================ */

/**
 * Builds the sidebar HTML for a given active item id.
 * @param {string} activeId - Which nav item should be highlighted
 * @returns {string} - HTML string
 */
function buildSidebar(activeId) {
    // Which parent group should be expanded because it contains
    // the active child?
    const activeParent = NAV_ITEMS.find(item =>
        item.children && item.children.some(c => c.id === activeId)
    );

    // Build each nav item
    const itemsHtml = NAV_ITEMS.map(item => {
        // Simple item (no submenu)
        if (!item.children) {
            const isActive = item.id === activeId;
            return `
                <div class="sidebar-item">
                    <a href="${resolvePath(item.href)}" class="sidebar-link ${isActive ? 'active' : ''}">
                        <span class="sidebar-link-icon">${ICONS[item.icon] || ''}</span>
                        <span>${item.label}</span>
                    </a>
                </div>
            `;
        }

        // Item with expandable submenu
        const isOpen = activeParent && activeParent.id === item.id;
        const subItems = item.children.map(child => {
            const isChildActive = child.id === activeId;
            return `
                <a href="${resolvePath(child.href)}" class="sidebar-sublink ${isChildActive ? 'active' : ''}">
                    ${child.label}
                </a>
            `;
        }).join('');

        return `
            <div class="sidebar-item ${isOpen ? 'open' : ''}" data-parent="${item.id}">
                <button class="sidebar-link" type="button" onclick="toggleSubmenu(this)">
                    <span class="sidebar-link-icon">${ICONS[item.icon] || ''}</span>
                    <span>${item.label}</span>
                    <span class="sidebar-chevron">${ICONS.chevron}</span>
                </button>
                <div class="sidebar-submenu">
                    ${subItems}
                </div>
            </div>
        `;
    }).join('');

    // Grab current user session for the profile at the bottom
    const session = JSON.parse(localStorage.getItem('ess_session') || '{}');
    const userName = session.name || 'Admin User';
    const userRole = session.role === 'super_admin' ? 'Super Admin' : 'Admin';
    const userInitials = getInitials(userName);

    // Full sidebar markup
    return `
        <aside class="sidebar">
            <!-- Brand block at top -->
            <div class="sidebar-brand">
                <!-- White rounded card keeps the colorful logo readable
                     against the dark blue sidebar background -->
                <div class="sidebar-brand-logo-card">
                    <img src="${resolvePath('/assets/logo.png')}" alt="Ek Se Sreshtha">
                </div>
            </div>

            <!-- Navigation list -->
            <nav class="sidebar-nav">
                <div class="sidebar-section-label">Main</div>
                ${itemsHtml}
            </nav>

            <!-- User profile block at bottom -->
            <div class="sidebar-user">
                <div class="avatar">${userInitials}</div>
                <div class="sidebar-user-info">
                    <div class="sidebar-user-name">${escapeHtml(userName)}</div>
                    <div class="sidebar-user-role">${escapeHtml(userRole)}</div>
                </div>
                <button class="btn-ghost btn-icon" onclick="logout()" title="Log out">
                    ${ICONS.logout}
                </button>
            </div>
        </aside>

        <!-- Backdrop overlay for mobile sidebar -->
        <div class="sidebar-overlay" onclick="closeSidebar()"></div>
    `;
}

/* ================================================================
   TOP HEADER RENDERER
   ================================================================ */

/**
 * Builds the top header bar with title + breadcrumbs.
 * @param {Object} config
 * @param {string} config.title
 * @param {Array} config.breadcrumbs - [{label, href?}]
 */
function buildTopbar({ title, breadcrumbs = [] }) {
    const crumbsHtml = breadcrumbs.map((crumb, idx) => {
        const isLast = idx === breadcrumbs.length - 1;
        const linkOrText = crumb.href && !isLast
            ? `<a href="${resolvePath(crumb.href)}">${escapeHtml(crumb.label)}</a>`
            : `<span>${escapeHtml(crumb.label)}</span>`;
        const separator = isLast ? '' : '<span class="breadcrumbs-separator">/</span>';
        return `${linkOrText}${separator}`;
    }).join('');

    return `
        <header class="topbar">
            <div class="topbar-left">
                <!-- Mobile menu toggle - only shows on small screens -->
                <button class="topbar-toggle" onclick="openSidebar()" aria-label="Open menu">
                    ${ICONS.menu}
                </button>
                <div>
                    ${breadcrumbs.length ? `<div class="breadcrumbs">${crumbsHtml}</div>` : ''}
                    <div class="topbar-title">${escapeHtml(title)}</div>
                </div>
            </div>
            <div class="topbar-right">
                <button class="topbar-icon-btn" aria-label="Notifications">
                    ${ICONS.bell}
                    <span class="notification-dot"></span>
                </button>
            </div>
        </header>
    `;
}

/* ================================================================
   SHELL ORCHESTRATOR
   ----------------------------------------------------------------
   The main function each page calls to render its layout.
   ================================================================ */

/**
 * Renders the entire app shell (sidebar + topbar + content wrapper).
 * The page's actual content should live inside an element with
 * id "page-body" that this function creates.
 *
 * @param {Object} config
 * @param {string} config.title - Page title shown in topbar
 * @param {string} config.active - Nav item ID to highlight
 * @param {Array}  config.breadcrumbs - Optional breadcrumb trail
 */
function renderShell({ title, active, breadcrumbs = [] }) {
    // Ensure a user is logged in
    requireAuth();

    // The root element the page provides
    const root = document.getElementById('app-shell');
    if (!root) {
        console.error('Element #app-shell not found');
        return;
    }

    // Save the page's original inner content (what the page author wrote)
    const pageMarkup = root.innerHTML;

    // Compose the full shell around that content
    root.className = 'app-shell';
    root.innerHTML = `
        ${buildSidebar(active)}
        <main class="main-area">
            ${buildTopbar({ title, breadcrumbs })}
            <div class="page-content" id="page-body">
                ${pageMarkup}
            </div>
        </main>
    `;
}

/* ================================================================
   SIDEBAR INTERACTIONS
   ================================================================ */

/**
 * Toggles an expandable submenu open/closed.
 * Called from the button's inline onclick.
 * @param {HTMLElement} btn - The clicked link button
 */
function toggleSubmenu(btn) {
    const item = btn.closest('.sidebar-item');
    if (item) {
        item.classList.toggle('open');
    }
}

/**
 * Opens the sidebar on mobile.
 */
function openSidebar() {
    const shell = document.querySelector('.app-shell');
    if (shell) shell.classList.add('sidebar-open');
}

/**
 * Closes the sidebar on mobile.
 */
function closeSidebar() {
    const shell = document.querySelector('.app-shell');
    if (shell) shell.classList.remove('sidebar-open');
}
