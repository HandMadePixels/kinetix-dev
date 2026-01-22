from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging

logger = logging.getLogger('django.security')

def custom_exception_handler(exc, context):
    """Custom DRF exception handler"""
    response = exception_handler(exc, context)
    
    if response is not None:
        # Log error
        logger.error(f"API Error: {exc.__class__.__name__} - {str(exc)}")
        
        # Customize error response
        response.data = {
            'error': response.data,
            'status_code': response.status_code
        }
    
    return response
