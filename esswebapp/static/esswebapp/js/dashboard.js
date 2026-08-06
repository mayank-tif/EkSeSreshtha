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
    fetchStats();
    fetchAttendanceData();
    fetchActivityFeed();
    
    // Attendance range dropdown handler
    const rangeSelect = document.getElementById('attendance-range');
    if (rangeSelect) {
        rangeSelect.addEventListener('change', () => {
            fetchAttendanceData(rangeSelect.value);
        });
    }
});

/* ================================================================
   STAT CARD VALUES - fetch from API
   ----------------------------------------------------------------
   Pulls counts from API endpoint and injects them into the UI.
   ================================================================ */

async function fetchStats() {
    try {
        const response = await fetch(`${getApiBaseUrl()}?action=stats`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            window.location.href = window.DATA_URLS?.login || '/login/';
            return;
        }
        
        if (!response.ok) throw new Error('Failed to fetch stats');
        
        const data = await response.json();
        
        document.getElementById('stat-centres').textContent = data.centres || 0;
        document.getElementById('stat-students').textContent = (data.students || 0).toLocaleString('en-IN');
        document.getElementById('stat-teachers').textContent = data.teachers || 0;
        document.getElementById('stat-districts').textContent = data.districts || 0;
        
        // Update 'this month' trend values
        const centresThisMonth = data.centres_this_month || 0;
        const studentsThisMonth = data.students_this_month || 0;
        const teachersThisMonth = data.teachers_this_month || 0;
        const districtsThisMonth = data.districts_this_month || 0;
        
        document.getElementById('stat-centres-trend').textContent = `+${centresThisMonth} this month`;
        document.getElementById('stat-students-trend').textContent = `+${studentsThisMonth.toLocaleString('en-IN')} this month`;
        document.getElementById('stat-teachers-trend').textContent = `+${teachersThisMonth} this month`;
        document.getElementById('stat-districts-trend').textContent = `+${districtsThisMonth} this month`;
        
        // Update trend classes based on whether there are new items
        document.getElementById('stat-centres-trend').className = centresThisMonth > 0 ? 'stat-card-trend positive' : 'stat-card-trend neutral';
        document.getElementById('stat-students-trend').className = studentsThisMonth > 0 ? 'stat-card-trend positive' : 'stat-card-trend neutral';
        document.getElementById('stat-teachers-trend').className = teachersThisMonth > 0 ? 'stat-card-trend positive' : 'stat-card-trend neutral';
        document.getElementById('stat-districts-trend').className = districtsThisMonth > 0 ? 'stat-card-trend positive' : 'stat-card-trend neutral';
    } catch (error) {
        console.error('Error fetching stats:', error);
        // Set fallback values
        document.getElementById('stat-centres').textContent = '0';
        document.getElementById('stat-students').textContent = '0';
        document.getElementById('stat-teachers').textContent = '0';
        document.getElementById('stat-districts').textContent = '0';
    }
}

/* ================================================================
   ATTENDANCE CHART - fetch from API
   ----------------------------------------------------------------
   Renders a bar chart for the last 7 days attendance percentages.
   ================================================================ */

async function fetchAttendanceData(range = '7') {
    const container = document.getElementById('attendance-chart');
    
    try {
        showGlobalLoader('Loading attendance data...');
        
        const response = await fetch(`${getApiBaseUrl()}?action=attendance&range=${range}`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            window.location.href = window.DATA_URLS?.login || '/login/';
            return;
        }
        
        if (!response.ok) throw new Error('Failed to fetch attendance');
        
        const data = await response.json();
        renderAttendanceChart(data.results || []);
    } catch (error) {
        console.error('Error fetching attendance:', error);
        // Fallback to empty chart
        renderAttendanceChart([]);
    } finally {
        hideGlobalLoader();
    }
}

function renderAttendanceChart(dailyData) {
    const container = document.getElementById('attendance-chart');
    if (!container) return;

    // Default empty data if none provided
    if (!dailyData || dailyData.length === 0) {
        container.innerHTML = '<div class="chart-empty">No attendance data available</div>';
        return;
    }

    // Build each bar as a group with the bar + label
    const barsHtml = dailyData.map(item => {
        const value = item.percentage || 0;
        return `
            <div class="chart-bar-group">
                <div class="chart-bar" style="height: ${value}%">
                    <span class="chart-bar-value">${value}%</span>
                </div>
                <div class="chart-bar-label">${item.day}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = barsHtml;
}

/* ================================================================
   ACTIVITY FEED - fetch from API
   ----------------------------------------------------------------
   Displays recent operations across the platform from ActivityLog.
   ================================================================ */

async function fetchActivityFeed() {
    const container = document.getElementById('activity-feed');
    if (!container) return;

    try {
        const response = await fetch(`${getApiBaseUrl()}?action=activity&limit=4`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 401) {
            window.location.href = window.DATA_URLS?.login || '/login/';
            return;
        }
        
        if (!response.ok) throw new Error('Failed to fetch activity');
        
        const data = await response.json();
        renderActivityFeed(data.results || []);
    } catch (error) {
        console.error('Error fetching activity:', error);
        container.innerHTML = `
            <div class="table-empty">Failed to load recent activity.</div>
        `;
    }
}

function renderActivityFeed(activities) {
    const container = document.getElementById('activity-feed');
    if (!container) return;

    // Fallback if there's nothing yet
    if (!activities || activities.length === 0) {
        container.innerHTML = `
            <div class="table-empty">No recent activity yet.</div>
        `;
        return;
    }

    // Render top 10
    container.innerHTML = activities.slice(0, 4).map(a => {
        // Determine activity type for styling
        let typeClass = 'default';
        if (a.action === 'CREATE') typeClass = 'success';
        else if (a.action === 'DELETE' || a.action === 'DEACTIVATE') typeClass = 'danger';
        else if (a.action === 'UPDATE') typeClass = 'warning';
        else if (a.action === 'ACTIVATE') typeClass = 'success';
        else if (a.action === 'LOGIN') typeClass = 'info';
        else if (a.action === 'LOGOUT') typeClass = 'default';

        return `
            <div class="activity-item">
                <div class="activity-dot ${typeClass}"></div>
                <div class="activity-content">
                    <div class="activity-text">${escapeHtml(a.message || '')}</div>
                    <div class="activity-time">${formatRelative(a.created_on)}</div>
                </div>
            </div>
        `;
    }).join('');
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

/* ================================================================
   UTILITY FUNCTIONS
   ================================================================ */

function getApiBaseUrl() {
    // Uses the base URL from the page (set in base.html)
    // dashboardApi is the dashboard URL, we need to use it as-is with query params
    return window.DATA_URLS?.dashboardApi || '/dashboard/';
}

function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    };
    
    // Add CSRF token if available
    const csrfToken = getCsrfToken();
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }
    
    return headers;
}

function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}