/**
 * Class Activity Report JavaScript
 * Handles filtering, pagination, and map modal
 */

(function() {
    'use strict';

    // Get URL from data attribute on body (set by sidebar.js)
    // Uses sidebar's global getUrl if available, otherwise falls back to local implementation
    function getUrl(urlName) {
        // Try sidebar's global function first (exposed as window.sidebarGetUrl)
        if (typeof window.sidebarGetUrl === 'function') {
            const url = window.sidebarGetUrl(urlName);
            if (url) return url;
        }
        // Fallback: read directly from body data attributes
        const attr = `data-url-${urlName}`;
        const value = document.body.getAttribute(attr);
        if (value && value.trim()) return value.trim();
        // Known URL mappings (fallback if data attribute missing)
        const urlMap = {
            'class-activity-report': '/attendance/class-activity-report/',
            'class-attendance-logs': '/attendance/class-logs/',
            'center-dropdown-list': '/centres/dropdown-list/',
            'teacher-dropdown-list': '/teacher/dropdown-list/',
            'logout': '/logout/',
            'logo': '/static/esswebapp/assets/logo.png'
        };
        if (urlMap[urlName]) return urlMap[urlName];
        // Last resort
        return `/${urlName}/`;
    }

    // State
    const state = {
        currentPage: 1,
        pageSize: 25,
        totalCount: 0,
        totalPages: 0,
        filters: {
            start_date: '',
            end_date: '',
            center_id: '',
            teacher_id: '',
            search: '',
            status: ''
        },
        centers: [],
        teachers: [],
        map: null,
        mapMarkers: [],
        infoWindow: null
    };

    // DOM Elements
    const elements = {
        tbody: null,
        pagination: null,
        startDate: null,
        endDate: null,
        centerFilter: null,
        teacherFilter: null,
        statusFilter: null,
        search: null,
        prevPage: null,
        nextPage: null,
        pageNumbers: null,
        paginationStart: null,
        paginationEnd: null,
        totalLogs: null,
        
        mapModal: null,
        mapCanvas: null,
        mapModalEventInfo: null,
        mapModalTeacherInfo: null,
        mapModalCenterInfo: null,
        mapModalCoordinates: null
    };

    // Action display mapping
    const actionDisplay = {
        'CLASS_STARTED': { label: 'Class Started', class: 'action-class_started', icon: 'play' },
        'ATTENDANCE_MARKED': { label: 'Attendance Marked', class: 'action-attendance_marked', icon: 'check' },
        'CLASS_ENDED': { label: 'Class Ended', class: 'action-class_ended', icon: 'stop' }
    };

    // SVG Icons
    const icons = {
        play: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
        check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polyline points="20 6 9 17 4 12"/></svg>',
        stop: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
        pin: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
    };

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        cacheElements();
        setupEventListeners();
        loadDropdowns();
        loadLogs();
    });

    function cacheElements() {
        elements.tbody = document.getElementById('report-tbody');
        elements.pagination = document.getElementById('report-pagination');
        elements.startDate = document.getElementById('report-start-date');
        elements.endDate = document.getElementById('report-end-date');
        elements.centerFilter = document.getElementById('report-center-filter');
        elements.teacherFilter = document.getElementById('report-teacher-filter');
        elements.statusFilter = document.getElementById('report-status-filter');
        elements.search = document.getElementById('report-search');
        elements.prevPage = document.getElementById('report-prev-page');
        elements.nextPage = document.getElementById('report-next-page');
        elements.pageNumbers = document.getElementById('report-page-numbers');
        elements.paginationStart = document.getElementById('report-pagination-start');
        elements.paginationEnd = document.getElementById('report-pagination-end');
        elements.totalLogs = document.getElementById('report-total-logs');
    }

    function setupEventListeners() {
        // Filter change handlers
        const filterInputs = [elements.startDate, elements.endDate, elements.centerFilter, elements.teacherFilter, elements.statusFilter, elements.search];
        filterInputs.forEach(input => {
            if (input) {
                input.addEventListener('change', () => {
                    updateFilters();
                    state.currentPage = 1;
                    loadLogs();
                });
            }
        });

        // Search with debounce
        if (elements.search) {
            let searchTimeout;
            elements.search.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    updateFilters();
                    state.currentPage = 1;
                    loadLogs();
                }, 300);
            });
        }

        // Pagination buttons
        if (elements.prevPage) {
            elements.prevPage.addEventListener('click', () => {
                if (state.currentPage > 1) {
                    state.currentPage--;
                    loadLogs();
                }
            });
        }
        if (elements.nextPage) {
            elements.nextPage.addEventListener('click', () => {
                if (state.currentPage < state.totalPages) {
                    state.currentPage++;
                    loadLogs();
                }
            });
        }

        // Map modal close
        if (elements.mapModal) {
            elements.mapModal.addEventListener('click', (e) => {
                if (e.target === elements.mapModal || e.target.closest('[data-close-modal]')) {
                    closeMapModal();
                }
            });
        }
    }

    function updateFilters() {
        state.filters.start_date = elements.startDate?.value || '';
        state.filters.end_date = elements.endDate?.value || '';
        state.filters.center_id = elements.centerFilter?.value || '';
        state.filters.teacher_id = elements.teacherFilter?.value || '';
        state.filters.status = elements.statusFilter?.value || '';
        state.filters.search = elements.search?.value || '';
    }

    function loadDropdowns() {
        // Load centers - use existing center dropdown API
        apiFetch(getUrl('center-dropdown-list'))
            .then(data => {
                state.centers = data.results || [];
                populateSelect(elements.centerFilter, state.centers, 'name');
            })
            .catch(console.error);

        // Load teachers - use existing teacher dropdown API
        apiFetch(getUrl('teacher-dropdown-list'))
            .then(data => {
                state.teachers = data.results || [];
                populateSelect(elements.teacherFilter, state.teachers, 'name');
            })
            .catch(console.error);
    }

    function populateSelect(selectEl, items, labelField) {
        if (!selectEl) return;
        const currentValue = selectEl.value;
        selectEl.innerHTML = selectEl.options[0] ? selectEl.options[0].outerHTML : '<option value="">All</option>';
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item[labelField] || item.center_name || item['user__name'] || 'Unknown';
            selectEl.appendChild(option);
        });
        selectEl.value = currentValue;
    }

    function loadLogs() {
        showLoading();

        const params = new URLSearchParams({
            action: 'list',
            page: state.currentPage,
            page_size: state.pageSize,
            start_date: state.filters.start_date,
            end_date: state.filters.end_date,
            center_id: state.filters.center_id,
            teacher_id: state.filters.teacher_id,
            status: state.filters.status,
            search: state.filters.search
        });

        const url = `${getUrl('class-activity-report')}?` + params.toString();
        apiFetch(url)
            .then(data => {
                state.totalCount = data.pagination?.total_count || 0;
                state.totalPages = data.pagination?.total_pages || 0;
                renderLogs(data.results || []);
                updatePagination();
            })
            .catch(err => {
                console.error('Error loading logs:', err);
                showError('Failed to load activity logs');
            });
    }

    function showLoading() {
        if (elements.tbody) {
            elements.tbody.innerHTML = `
                <tr>
                    <td colspan="12" class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="spin">
                            <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                            <path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="1" stroke-linecap="round"/>
                        </svg>
                        <p>Loading activity logs...</p>
                    </td>
                </tr>
            `;
        }
        if (elements.pagination) {
            elements.pagination.style.display = 'none';
        }
    }

    function showError(message) {
        if (elements.tbody) {
            elements.tbody.innerHTML = `
                <tr>
                    <td colspan="12" class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="8" x2="12" y2="12"/>
                            <line x1="12" y1="16" x2="12.01" y2="16"/>
                        </svg>
                        <p>${message}</p>
                    </td>
                </tr>
            `;
        }
        if (elements.pagination) {
            elements.pagination.style.display = 'none';
        }
    }

    function renderLogs(logs) {
        if (!elements.tbody) return;

        if (!logs || logs.length === 0) {
            elements.tbody.innerHTML = `
                <tr>
                    <td colspan="12" class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <p>No activity logs found</p>
                    </td>
                </tr>
            `;
            if (elements.pagination) elements.pagination.style.display = 'none';
            return;
        }

        let html = '';
        const startNum = (state.currentPage - 1) * state.pageSize + 1;

        logs.forEach((log, index) => {
            const rowNum = startNum + index;
            const actionInfo = actionDisplay[log.action] || { label: log.action, class: '', icon: 'play' };
            const createdOn = log.created_on ? new Date(log.created_on) : null;
            const dateStr = createdOn ? createdOn.toLocaleDateString('en-GB') : '-';
            
            // Status badge
            const statusClass = log.status === 'SUCCESS' ? 'status-success' : (log.status === 'FAILED' ? 'status-failed' : '');
            const statusBadge = log.status ? `<span class="status-badge ${statusClass}">${log.status}</span>` : '<span class="text-muted">—</span>';
            const timeStr = createdOn ? createdOn.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-';

            // Teacher coordinates
            const teacherLat = log.user_latitude ? `<span class="coord-display">${log.user_latitude}</span>` : '<span class="text-muted">—</span>';
            const teacherLng = log.user_longitude ? `<span class="coord-display">${log.user_longitude}</span>` : '<span class="text-muted">—</span>';
            
            // Center coordinates
            const centerLat = log.center_latitude ? `<span class="coord-display">${log.center_latitude}</span>` : '<span class="text-muted">—</span>';
            const centerLng = log.center_longitude ? `<span class="coord-display">${log.center_longitude}</span>` : '<span class="text-muted">—</span>';

            html += `
                <tr data-log='${JSON.stringify(log).replace(/'/g, '&apos;')}'>
                    <td class="text-center">${rowNum}</td>
                    <td>${escapeHtml(log.center_name || '—')}</td>
                    <td>
                        <div style="font-weight: 500;">${escapeHtml(log.user_name || '—')}</div>
                        <div class="text-muted" style="font-size: 12px;">${escapeHtml(log.user_mobile || '—')}</div>
                        ${log.user_role ? `<div class="text-muted" style="font-size: 11px;">${escapeHtml(log.user_role)}</div>` : ''}
                    </td>
                    <td>
                        <div class="datetime-cell">
                            <div class="datetime-stack">
                                <span class="datetime-time">${timeStr}</span>
                                <span class="datetime-date">${dateStr}</span>
                            </div>
                        </div>
                    </td>
                    <td class="text-center">${statusBadge}</td>
                    <td>
                        <span class="action-badge ${actionInfo.class}">
                            <span class="action-icon">${icons[actionInfo.icon]}</span>
                            <span class="action-text">${actionInfo.label}</span>
                        </span>
                    </td>
                    <td class="text-center">${teacherLat}</td>
                    <td class="text-center">${teacherLng}</td>
                    <td class="text-center">${centerLat}</td>
                    <td class="text-center">${centerLng}</td>
                    <td class="reason-cell" title="${escapeHtml(log.reason || '')}">${escapeHtml(log.reason || '—')}</td>
                </tr>
            `;
        });

        elements.tbody.innerHTML = html;

        // Add click handlers for location links
        elements.tbody.querySelectorAll('.location-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                openMapModal(link.dataset);
            });
        });

        if (elements.pagination) {
            elements.pagination.style.display = 'flex';
        }
    }

    function updatePagination() {
        if (!elements.pagination) return;

        const start = (state.currentPage - 1) * state.pageSize + 1;
        const end = Math.min(state.currentPage * state.pageSize, state.totalCount);

        if (elements.paginationStart) elements.paginationStart.textContent = state.totalCount > 0 ? start : 0;
        if (elements.paginationEnd) elements.paginationEnd.textContent = end;
        if (elements.totalLogs) elements.totalLogs.textContent = state.totalCount;

        // Prev/Next buttons
        if (elements.prevPage) {
            elements.prevPage.disabled = state.currentPage <= 1;
        }
        if (elements.nextPage) {
            elements.nextPage.disabled = state.currentPage >= state.totalPages;
        }

        // Page numbers
        if (elements.pageNumbers) {
            elements.pageNumbers.innerHTML = renderPageNumbers();
        }
    }

    function renderPageNumbers() {
        const maxPages = 7;
        let html = '';

        if (state.totalPages <= maxPages) {
            for (let i = 1; i <= state.totalPages; i++) {
                html += `<button class="btn btn-sm ${i === state.currentPage ? 'btn-primary' : 'btn-secondary'}" data-page="${i}">${i}</button>`;
            }
        } else {
            // Always show first page
            html += `<button class="btn btn-sm ${1 === state.currentPage ? 'btn-primary' : 'btn-secondary'}" data-page="1">1</button>`;

            let startPage = Math.max(2, state.currentPage - 2);
            let endPage = Math.min(state.totalPages - 1, state.currentPage + 2);

            if (startPage > 2) {
                html += `<span class="btn btn-sm btn-secondary disabled">...</span>`;
            }

            for (let i = startPage; i <= endPage; i++) {
                html += `<button class="btn btn-sm ${i === state.currentPage ? 'btn-primary' : 'btn-secondary'}" data-page="${i}">${i}</button>`;
            }

            if (endPage < state.totalPages - 1) {
                html += `<span class="btn btn-sm btn-secondary disabled">...</span>`;
            }

            // Always show last page
            html += `<button class="btn btn-sm ${state.totalPages === state.currentPage ? 'btn-primary' : 'btn-secondary'}" data-page="${state.totalPages}">${state.totalPages}</button>`;
        }

        return html;
    }

    // Event delegation for page numbers
    document.addEventListener('click', (e) => {
        const pageBtn = e.target.closest('[data-page]');
        if (pageBtn && elements.pageNumbers && elements.pageNumbers.contains(pageBtn)) {
            const page = parseInt(pageBtn.dataset.page);
            if (page !== state.currentPage) {
                state.currentPage = page;
                loadLogs();
            }
        }
    });


    // Map Modal
    function openMapModal(data) {
        if (!elements.mapModal) return;

        // Update info
        if (elements.mapModalEventInfo) {
            const actionInfo = actionDisplay[data.type === 'teacher' ? 'CLASS_STARTED' : 'CLASS_STARTED'];
            elements.mapModalEventInfo.textContent = data.type === 'teacher' ? 'Teacher Location' : 'Centre Location';
        }
        if (elements.mapModalTeacherInfo) {
            elements.mapModalTeacherInfo.textContent = data.name ? `Teacher: ${data.name}` : '';
        }
        if (elements.mapModalCenterInfo) {
            elements.mapModalCenterInfo.textContent = data.center ? `Centre: ${data.center}` : (data.teacher ? `Teacher: ${data.teacher}` : '');
        }
        if (elements.mapModalCoordinates) {
            elements.mapModalCoordinates.textContent = `Coordinates: ${data.lat}, ${data.lng}`;
        }

        elements.mapModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Initialize map after modal is visible
        setTimeout(() => initMap(parseFloat(data.lat), parseFloat(data.lng), data.type, data.name), 100);
    }

    function closeMapModal() {
        if (elements.mapModal) {
            elements.mapModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    function initMap(lat, lng, type, name) {
        if (!elements.mapCanvas) return;

        // Check if Google Maps is loaded
        if (typeof google === 'undefined' || !google.maps) {
            elements.mapCanvas.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#6b7280;">Google Maps not loaded. Check API key.</div>';
            return;
        }

        // Clear previous map
        if (state.map) {
            state.mapMarkers.forEach(m => m.setMap(null));
            state.mapMarkers = [];
        }

        const center = new google.maps.LatLng(lat, lng);

        state.map = new google.maps.Map(elements.mapCanvas, {
            center: center,
            zoom: 16,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true
        });

        // Add marker
        const marker = new google.maps.Marker({
            position: center,
            map: state.map,
            title: name || (type === 'teacher' ? 'Teacher Location' : 'Centre Location'),
            icon: {
                url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
                    <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="${type === 'teacher' ? '#3b82f6' : '#f59e0b'}" stroke-width="2.5">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                        <circle cx="12" cy="10" r="3" fill="${type === 'teacher' ? '#3b82f6' : '#f59e0b'}"/>
                    </svg>
                `),
                scaledSize: new google.maps.Size(40, 40),
                anchor: new google.maps.Point(20, 40)
            }
        });

        state.mapMarkers.push(marker);

        // Add info window
        if (!state.infoWindow) {
            state.infoWindow = new google.maps.InfoWindow();
        }

        const content = `
            <div style="padding:8px;min-width:180px;">
                <strong>${escapeHtml(name || (type === 'teacher' ? 'Teacher' : 'Centre'))}</strong><br>
                <small>${type === 'teacher' ? 'Teacher Location' : 'Centre Location'}</small><br>
                <small>Lat: ${lat.toFixed(6)}, Lng: ${lng.toFixed(6)}</small>
            </div>
        `;

        state.infoWindow.setContent(content);
        state.infoWindow.open(state.map, marker);

        // Trigger resize to fix gray tiles
        google.maps.event.trigger(state.map, 'resize');
        state.map.setCenter(center);
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

})();