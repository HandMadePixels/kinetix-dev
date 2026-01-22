from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
from django.core.exceptions import ValidationError
from core.models import Device

class DeviceJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that supports Device objects as users.
    Useful for agent API communication.
    """
    
    def get_user(self, validated_token):
        user_id = validated_token.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('Token contains no user identifier', code='token_not_valid')

        # Try finding in Device model first (since agents use this most)
        try:
            device = Device.objects.get(id=user_id)
            # Standard DRF expects an object with is_authenticated property
            # Device model has this added as a property
            return device
        except (Device.DoesNotExist, ValidationError):
            # Fallback to standard User model
            return super().get_user(validated_token)
