"""
Domain-based URL Access Control Middleware

Restricts access to URL patterns based on the request domain:
- Webapp domain: Cannot access /api/ URLs
- API domain: Cannot access non-/api/ URLs (webapp URLs)
- Localhost/127.0.0.1: Can access everything (development)
"""

import logging
from django.http import HttpResponseForbidden
from django.conf import settings

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