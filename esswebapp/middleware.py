"""
Domain-based URL Access Control Middleware

Restricts access to URL patterns based on the request domain:
- Webapp domain: Cannot access /api/ URLs
- API domain: Cannot access non-/api/ URLs (webapp URLs)
- Localhost/127.0.0.1: Can access everything (development)
"""

import logging
from django.http import HttpResponseForbidden, JsonResponse
from django.conf import settings
from EkSeSreshtha.env_details import ATTENDANCE_ALLOWED_IPS

logger = logging.getLogger(__name__)


class DomainURIRestrictionMiddleware:
    """
    Middleware to restrict URL access based on domain.
    
    Configuration via settings:
    DOMAIN_URI_RESTRICTIONS = {
        'webapp_domains': ['webapp.example.com', 'app.example.com'],
        'api_domains': ['api.example.com', 'api-v2.example.com'],
        'local_hosts': ['localhost', '127.0.0.1', '[::1]', 'testserver'],
    }
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Get configuration from settings with defaults
        restrictions = getattr(settings, 'DOMAIN_URI_RESTRICTIONS', {})
        
        self.webapp_domains = set(restrictions.get('webapp_domains', []))
        self.api_domains = set(restrictions.get('api_domains', []))
        self.local_hosts = set(restrictions.get('local_hosts', [
            'localhost', '127.0.0.1', '[::1]', 'testserver'
        ]))
        
        # Normalize domains (remove port if present)
        self.webapp_domains = {self._normalize_host(d) for d in self.webapp_domains}
        self.api_domains = {self._normalize_host(d) for d in self.api_domains}
        self.local_hosts = {self._normalize_host(d) for d in self.local_hosts}
        
        logger.info(
            f"DomainURIRestrictionMiddleware initialized: "
            f"webapp_domains={self.webapp_domains}, "
            f"api_domains={self.api_domains}, "
            f"local_hosts={self.local_hosts}"
        )
    
    def _normalize_host(self, host):
        """Remove port from host header."""
        if ':' in host:
            host = host.split(':')[0]
        return host.lower()
    
    def _get_client_host(self, request):
        """Get normalized host from request."""
        host = request.get_host()
        return self._normalize_host(host)
    
    def _is_local(self, host):
        """Check if host is a local development host."""
        return host in self.local_hosts
    
    def _is_webapp_domain(self, host):
        """Check if host is a webapp domain."""
        return host in self.webapp_domains
    
    def _is_api_domain(self, host):
        """Check if host is an API domain."""
        return host in self.api_domains
    
    def _is_api_path(self, path):
        """Check if path is an API path."""
        return path.startswith('/api/')
    
    def _is_admin_path(self, path):
        """Check if path is admin path (always allow)."""
        return path.startswith('/admin/')
    
    def _is_static_media_path(self, path):
        """Check if path is static/media (always allow)."""
        return path.startswith('/static/') or path.startswith('/media/')
    
    def __call__(self, request):
        host = self._get_client_host(request)
        path = request.path
        
        # Always allow local hosts, admin, static, media
        if (self._is_local(host) or 
            self._is_admin_path(path) or 
            self._is_static_media_path(path)):
            return self.get_response(request)
        
        # Check domain-path combinations
        is_api_path = self._is_api_path(path)
        is_webapp_domain = self._is_webapp_domain(host)
        is_api_domain = self._is_api_domain(host)
        
        # Webapp domain trying to access API URLs
        if is_webapp_domain and is_api_path:
            logger.warning(
                f"DomainURIBlock: webapp domain '{host}' blocked from API path '{path}'"
            )
            return HttpResponseForbidden(
                "Access denied: Webapp domain cannot access API endpoints."
            )
        
        # API domain trying to access webapp URLs
        if is_api_domain and not is_api_path:
            logger.warning(
                f"DomainURIBlock: API domain '{host}' blocked from webapp path '{path}'"
            )
            return HttpResponseForbidden(
                "Access denied: API domain cannot access webapp endpoints."
            )
        
        # Unknown domain - allow but log (or could block)
        if not is_webapp_domain and not is_api_domain:
            logger.info(f"DomainURIAllow: Unknown domain '{host}' accessing '{path}'")
        
        return self.get_response(request)


class AttendanceIPRestrictionMiddleware:
    """
    Restricts the Center Attendance endpoints to a single trusted client IP.

    Applies ONLY to:
      - POST /api/generate-center-attendance-token/
      - POST /api/center-attendance/

    Requests from any other source receive 403 with a JSON body.
    The allowed IP is configured via settings.ATTENDANCE_IP_RESTRICTIONS.
    Local/dev hosts are bypassed so development and tests keep working.
    """

    # URL paths protected by this middleware (no trailing slash)
    PROTECTED_PATHS = frozenset({
        '/api/generate-center-attendance-token',
        '/api/center-attendance',
    })

    def __init__(self, get_response):
        self.get_response = get_response

        # Local/dev hosts that bypass the IP check (development + test client).
        # Built-in list - deliberately not configurable via settings.
        self.local_hosts = {
            self._normalize_ip(h)
            for h in ['localhost', '127.0.0.1', '[::1]', 'testserver']
        }
        # Allowed IPs: raw comma-separated value from .env, exposed via
        # EkSeSreshtha/env_details.py (ATTENDANCE_ALLOWED_IPS).
        # Split/parsed here: entries stripped, empties dropped.
        raw_ips = ATTENDANCE_ALLOWED_IPS or ''
        self.allowed_ips = {
            self._normalize_ip(ip.strip())
            for ip in raw_ips.split(',')
            if ip.strip()
        }

        logger.info(
            f"AttendanceIPRestrictionMiddleware initialized: "
            f"allowed_ips={self.allowed_ips}, local_hosts={self.local_hosts}"
        )

    def _normalize_ip(self, value):
        """Lowercase and strip port (e.g. '3.6.172.231:80' -> '3.6.172.231')."""
        if not value:
            return ''
        value = str(value).strip().lower()
        # IPv6 with brackets, e.g. '[::1]:8000'
        if value.startswith('['):
            return value.split(']')[0][1:] if ']' in value else value
        # Strip :port for IPv4/host names
        if ':' in value and value.count(':') == 1:
            value = value.split(':')[0]
        return value

    def _client_ip(self, request):
        """
        Best-effort client IP: REMOTE_ADDR, falling back to the Host header
        comparison used by the existing domain middleware.
        """
        remote = request.META.get('REMOTE_ADDR', '')
        return self._normalize_ip(remote)

    def _is_protected(self, request):
        # Normalize: strip trailing slash so both '/api/center-attendance'
        # and '/api/center-attendance/' match.
        path = request.path.rstrip('/')
        if path not in self.PROTECTED_PATHS:
            return False
        # The two views only accept POST
        return request.method == 'POST'

    def __call__(self, request):
        if self._is_protected(request):
            # Decision is based on the CLIENT IP only (REMOTE_ADDR).
            # The Host header is deliberately NOT trusted here - an attacker
            # could send 'Host: localhost' to abuse the local bypass.
            client = self._client_ip(request)

            allowed = (
                client in self.allowed_ips
                or client in self.local_hosts
            )

            if not allowed:
                logger.warning(
                    f"AttendanceIPBlock: '{client}' blocked from '{request.path}'"
                )
                return JsonResponse(
                    {'message': 'Access denied: unauthorized source.'},
                    status=403,
                )

            logger.info(
                f"AttendanceIPAllow: '{client}' allowed on '{request.path}'"
            )

        return self.get_response(request)