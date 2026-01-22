"""
Custom encrypted database fields using Fernet symmetric encryption
"""

from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet


class EncryptedTextField(models.TextField):
    """
    Encrypted text field using Fernet encryption.
    Data is encrypted before saving and decrypted when retrieved.
    """
    
    description = "Encrypted text field"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet = None
    
    @property
    def fernet(self):
        """Lazy initialization of Fernet cipher"""
        if self._fernet is None:
            key = settings.ENCRYPTION_KEY
            if isinstance(key, str):
                key = key.encode()
            self._fernet = Fernet(key)
        return self._fernet
    
    def get_prep_value(self, value):
        """Encrypt value before saving to database"""
        if value is None or value == '':
            return value
        
        if isinstance(value, str):
            value = value.encode()
        
        encrypted = self.fernet.encrypt(value)
        return encrypted.decode()
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value when retrieving from database"""
        if value is None or value == '':
            return value
        
        try:
            if isinstance(value, str):
                value = value.encode()
            
            decrypted = self.fernet.decrypt(value)
            return decrypted.decode()
        except Exception as e:
            # Log decryption error but don't expose details
            import logging
            logger = logging.getLogger('django.security')
            logger.error(f"Decryption failed: {type(e).__name__}")
            return None
    
    def to_python(self, value):
        """Convert to Python type"""
        if isinstance(value, str) or value is None:
            return value
        return str(value)


class EncryptedCharField(models.CharField):
    """
    Encrypted char field using Fernet encryption.
    Similar to EncryptedTextField but with max_length constraint.
    """
    
    description = "Encrypted char field"
    
    def __init__(self, *args, **kwargs):
        # Encrypted data will be longer, so adjust max_length
        if 'max_length' in kwargs:
            # Fernet adds ~50% overhead + base64 encoding
            kwargs['max_length'] = int(kwargs['max_length'] * 2)
        super().__init__(*args, **kwargs)
        self._fernet = None
    
    @property
    def fernet(self):
        """Lazy initialization of Fernet cipher"""
        if self._fernet is None:
            key = settings.ENCRYPTION_KEY
            if isinstance(key, str):
                key = key.encode()
            self._fernet = Fernet(key)
        return self._fernet
    
    def get_prep_value(self, value):
        """Encrypt value before saving to database"""
        if value is None or value == '':
            return value
        
        if isinstance(value, str):
            value = value.encode()
        
        encrypted = self.fernet.encrypt(value)
        return encrypted.decode()
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value when retrieving from database"""
        if value is None or value == '':
            return value
        
        try:
            if isinstance(value, str):
                value = value.encode()
            
            decrypted = self.fernet.decrypt(value)
            return decrypted.decode()
        except Exception as e:
            import logging
            logger = logging.getLogger('django.security')
            logger.error(f"Decryption failed: {type(e).__name__}")
            return None
    
    def to_python(self, value):
        """Convert to Python type"""
        if isinstance(value, str) or value is None:
            return value
        return str(value)
