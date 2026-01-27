"""
Custom middleware for audit logging and rate limiting
"""

import logging
from django.utils import timezone
from django.core.cache import cache
from django.http import JsonResponse
from core.models import AuditLog


audit_logger = logging.getLogger('core.audit')
security_logger = logging.getLogger('django.security')


class AuditLoggingMiddleware:
    """
    Middleware to log all requests for audit purposes.
    Logs user actions, IP addresses, and request details.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        response = self.get_response(request)
        
        # Log after response (so we have status code)
        self.log_request(request, response)
        
        return response
    
    def scrub_sensitive_data(self, data):
        """Recursively redact sensitive keys from a dictionary or list"""
        if not isinstance(data, (dict, list)):
            return data
        
        sensitive_keys = {
            'token', 'refresh', 'password', 'key', 'secret', 
            'signature', 'auth_token', 'private_key', 'payload'
        }
        
        if isinstance(data, list):
            return [self.scrub_sensitive_data(item) for item in data]
        
        scrubbed = {}
        for k, v in data.items():
            # Check if key contains any sensitive substrings (case-insensitive)
            is_sensitive = any(sk in k.lower() for sk in sensitive_keys)
            
            if is_sensitive:
                scrubbed[k] = "********"
            elif isinstance(v, (dict, list)):
                scrubbed[k] = self.scrub_sensitive_data(v)
            else:
                scrubbed[k] = v
        return scrubbed

    def log_request(self, request, response):
        """Log request details to audit log"""
        
        # Skip static files and health checks
        if request.path.startswith('/static/') or request.path == '/health/':
            return
        
        # Get user info
        user_obj = None
        device_obj = None
        
        if request.user.is_authenticated:
            from core.models import Device
            if isinstance(request.user, Device):
                device_obj = request.user
            else:
                user_obj = request.user
                
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Determine action based on path and method
        action = self.determine_action(request)
        
        # Determine severity based on response status
        if response.status_code >= 500:
            severity = 'error'
        elif response.status_code >= 400:
            severity = 'warning'
        else:
            severity = 'info'
        
        # Log to file
        audit_logger.info(
            f"{ip_address} - {user_obj or device_obj or 'Anonymous'} - {request.method} {request.path} - {response.status_code}"
        )
        
        # Log to database (async to avoid performance impact)
        if action:
            # SECURITY FIX: Sanitize query parameters and metadata
            query_params = self.scrub_sensitive_data(dict(request.GET))
            metadata = {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'query_params': query_params,
            }

            try:
                AuditLog.objects.create(
                    user=user_obj,
                    device=device_obj,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    action=action,
                    severity=severity,
                    description=f"{request.method} {request.path}",
                    metadata=metadata
                )
            except Exception as e:
                security_logger.error(f"Failed to create audit log: {e}")
    
    def get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def determine_action(self, request):
        """Map request to audit action"""
        path = request.path
        method = request.method
        
        # API endpoints
        if '/api/v1/register' in path and method == 'POST':
            return 'device_register'
        elif '/api/v1/updates' in path and method == 'POST':
            return 'update_upload'
        elif '/api/v1/push-update' in path and method == 'POST':
            return 'update_push'
        elif '/api/v1/inventory' in path and method == 'POST':
            return 'inventory_submit'
        elif '/admin/login' in path:
            return 'login'
        elif '/admin/logout' in path:
            return 'logout'
        
        return None


class RateLimitMiddleware:
    """
    Custom rate limiting middleware.
    Complements DRF throttling for additional protection.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check rate limit
        if not self.check_rate_limit(request):
            security_logger.warning(
                f"Rate limit exceeded: {self.get_client_ip(request)} - {request.path}"
            )
            return JsonResponse(
                {'error': 'Rate limit exceeded. Please try again later.'},
                status=429
            )
        
        response = self.get_response(request)
        return response
    
    def check_rate_limit(self, request):
        """Check if request is within rate limits with per-device awareness"""
        
        ip_address = self.get_client_ip(request)
        
        # Skip rate limit for local requests during development/testing
        if ip_address in ['127.0.0.1', '::1', 'localhost']:
            return True
            
        # Skip for authenticated staff users
        if request.user.is_authenticated and getattr(request.user, 'is_staff', False):
            return True
        
        path = request.path
        
        # Determine the identity for the cache key
        identity = ip_address
        if request.user.is_authenticated:
            from core.models import Device
            if isinstance(request.user, Device):
                # SECURITY FIX: Use Device ID for granular limiting behind NAT
                identity = f"device:{request.user.id}"
            else:
                identity = f"user:{request.user.id}"

        # Different limits for different endpoints
        if '/api/v1/register' in path:
            limit = 20
            window = 3600  # 20 per hour
        elif '/api/v1/updates' in path and request.method == 'POST':
            limit = 10
            window = 3600  # 10 per hour
        elif '/api/v1/commands' in path or '/api/v1/heartbeat' in path:
            # SECURITY: Relaxed limit for control plane to allow "Immediate" reflection
            # 1000 per minute allows up to 16 requests per second per device.
            limit = 1000
            window = 60
        elif path.startswith('/api/'):
            limit = 300
            window = 60  # 300 per minute (5 per second avg)
        else:
            return True  # No limit for non-API endpoints
        
        # Check cache
        cache_key = f"ratelimit:{identity}:{path}"
        current_count = cache.get(cache_key)
        
        if current_count is None:
            cache.set(cache_key, 1, window)
            return True
        
        if current_count >= limit:
            return False
        
        # Increment counter without resetting window
        try:
            cache.incr(cache_key)
        except ValueError:
            # Handle race condition if key expired between get and incr
            cache.set(cache_key, 1, window)
            
        return True
    
    def get_client_ip(self, request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
