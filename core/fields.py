"""
Custom encrypted database fields using Fernet symmetric encryption
"""

from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import base64


class EncryptedFieldMixin:
    """Mixin to provide HKDF key derivation logic to fields"""
    
    def get_derived_fernet(self, model_name, field_name):
        """Derive a field-specific key using HKDF"""
        master_key = settings.ENCRYPTION_KEY
        if isinstance(master_key, str):
            master_key = master_key.encode()
            
        # Context info ensures the derived key is unique to this specific column
        info = f"{model_name}:{field_name}".encode()
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=info
        )
        
        derived_key = base64.urlsafe_b64encode(hkdf.derive(master_key))
        return Fernet(derived_key)

    def get_master_fernet(self):
        """Get Fernet instance using the raw master key (for legacy decryption)"""
        key = settings.ENCRYPTION_KEY
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)


class EncryptedTextField(models.TextField, EncryptedFieldMixin):
    """
    Encrypted text field using HKDF-derived Fernet keys.
    """
    
    description = "Encrypted text field (HKDF)"
    
    def get_prep_value(self, value):
        """Encrypt value using derived key before saving"""
        if value is None or value == '':
            return value
        
        if isinstance(value, str):
            value = value.encode()
        
        # Derive key based on model/field context
        fernet = self.get_derived_fernet(self.model._meta.model_name, self.name)
        encrypted = fernet.encrypt(value)
        return encrypted.decode()
    
    def from_db_value(self, value, expression, connection):
        """Decrypt value with legacy fallback"""
        if value is None or value == '':
            return value
        
        try:
            if isinstance(value, str):
                value = value.encode()
            
            # 1. Try derived key (New Standard)
            try:
                fernet = self.get_derived_fernet(self.model._meta.model_name, self.name)
                return fernet.decrypt(value).decode()
            except Exception:
                # 2. Fallback to master key (Legacy Data)
                master_fernet = self.get_master_fernet()
                return master_fernet.decrypt(value).decode()
                
        except Exception as e:
            import logging
            logger = logging.getLogger('django.security')
            logger.error(f"Decryption failed for {self.model._meta.model_name}.{self.name}")
            return None
    
    def to_python(self, value):
        if isinstance(value, str) or value is None:
            return value
        return str(value)


class EncryptedCharField(models.CharField, EncryptedFieldMixin):
    """
    Encrypted char field using HKDF-derived Fernet keys.
    """
    
    description = "Encrypted char field (HKDF)"
    
    def __init__(self, *args, **kwargs):
        if 'max_length' in kwargs:
            kwargs['max_length'] = int(kwargs['max_length'] * 2)
        super().__init__(*args, **kwargs)
    
    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        
        if isinstance(value, str):
            value = value.encode()
        
        fernet = self.get_derived_fernet(self.model._meta.model_name, self.name)
        encrypted = fernet.encrypt(value)
        return encrypted.decode()
    
    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        
        try:
            if isinstance(value, str):
                value = value.encode()
            
            try:
                fernet = self.get_derived_fernet(self.model._meta.model_name, self.name)
                return fernet.decrypt(value).decode()
            except Exception:
                master_fernet = self.get_master_fernet()
                return master_fernet.decrypt(value).decode()
        except Exception:
            return None
    
    def to_python(self, value):
        if isinstance(value, str) or value is None:
            return value
        return str(value)
