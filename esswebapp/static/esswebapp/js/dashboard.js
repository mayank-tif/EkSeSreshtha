/* ================================================================
   EK SE SRESHTHA - DASHBOARD PAGE SCRIPT
   ----------------------------------------------------------------
   Wires up the dashboard: renders the app shell, populates
   the stat cards, draws the attendance chart, and lists recent
   activity.
   ================================================================ */

// Render the shared shell (sidebar + topbar) around the page content
renderShell({
    title: 'Dashboard',
    active: 'dashboard',
    breadcrumbs: [{ label: 'Home' }, { label: 'Dashboard' }]
});

/* ================================================================
   ON LOAD - initialize each dashboard section
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {
    renderStats();
    renderAttendanceChart();
    renderActivityFeed();
});

/* ================================================================
   STAT CARD VALUES
   ----------------------------------------------------------------
   Pulls counts from localStorage and injects them into the UI.
   ================================================================ */

function renderStats() {
    const centres = getRecords('centres').length;
    const students = getRecords('students').length;
    const teachers = getRecords('teachers').length;
    const districts = getRecords('districts').length;

    document.getElementById('stat-centres').textContent = centres;
    document.getElementById('stat-students').textContent = students.toLocaleString('en-IN');
    document.getElementById('stat-teachers').textContent = teachers;
    document.getElementById('stat-districts').textContent = districts;
}

/* ================================================================
   ATTENDANCE CHART
   ----------------------------------------------------------------
   Renders a simple bar chart for the last 7 days.
   Data is faked here for demo purposes - in production this would
   come from an aggregation endpoint.
   ================================================================ */

function renderAttendanceChart() {
    const container = document.getElementById('attendance-chart');
    if (!container) return;

    // Sample attendance percentages for the last 7 days
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const values = [82, 78, 85, 91, 88, 76, 65];

    // Build each bar as a group with the bar + label
    const barsHtml = days.map((day, idx) => {
        const value = values[idx];
        return `
            <div class="chart-bar-group">
                <div class="chart-bar" style="height: ${value}%">
                    <span class="chart-bar-value">${value}%</span>
                </div>
                <div class="chart-bar-label">${day}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = barsHtml;
}

/* ================================================================
   ACTIVITY FEED
   ----------------------------------------------------------------
   Displays recent operations across the platform.
   Real implementation would fetch from an audit log; here we
   generate a mixed feed from the most recent records.
   ================================================================ */

function renderActivityFeed() {
    const container = document.getElementById('activity-feed');
    if (!container) return;

    // Collect recent records from various tables and label them
    const activities = [];

    getRecords('students').slice(-3).forEach(s => {
        activities.push({
            type: 'success',
            text: `New student <strong>${escapeHtml(s.name)}</strong> registered`,
            date: s.createdAt
        });
    });

    getRecords('teachers').slice(-2).forEach(t => {
        activities.push({
            type: 'default',
            text: `Teacher <strong>${escapeHtml(t.name)}</strong> added to the system`,
            date: t.createdAt
        });
    });

    getRecords('centres').slice(-2).forEach(c => {
        activities.push({
            type: 'warning',
            text: `Centre <strong>${escapeHtml(c.name)}</strong> was created`,
            date: c.createdAt
        });
    });

    // Sort by most recent first
    activities.sort((a, b) => new Date(b.date) - new Date(a.date));

    // Fallback if there's nothing yet
    if (activities.length === 0) {
        container.innerHTML = `
            <div class="table-empty">No recent activity yet.</div>
        `;
        return;
    }

    // Render top 6
    container.innerHTML = activities.slice(0, 6).map(a => `
        <div class="activity-item">
            <div class="activity-dot ${a.type}"></div>
            <div class="activity-content">
                <div class="activity-text">${a.text}</div>
                <div class="activity-time">${formatRelative(a.date)}</div>
            </div>
        </div>
    `).join('');
}

/**
 * Turns an ISO date into a friendly relative string like
 * "2 hours ago" or "yesterday".
 */
function formatRelative(iso) {
    if (!iso) return '';
    const now = new Date();
    const then = new Date(iso);
    const diffMs = now - then;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin} min ago`;
    if (diffHr < 24) return `${diffHr} hour${diffHr > 1 ? 's' : ''} ago`;
    if (diffDay < 30) return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
    return formatDate(iso);
}
