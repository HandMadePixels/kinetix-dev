import os
import sys
import configparser
import keyring
import base64
from pathlib import Path

class AgentConfig:
    """Manages Agent configuration and secure token storage"""
    
    DEFAULT_CONFIG = {
        'Server': {
            'URL': 'http://127.0.0.1:8000',
            'PollInterval': '300',  # 5 minutes
            'Timeout': '30',
        },
        'Security': {
            'PublicKeyFile': 'public_key.pem',
            'VerifySSL': 'True',
        },
        'Agent': {
            'ID': '',
            'Version': '1.0.0',
            'MaxLogSize': '5242880',  # 5MB
            'MaxLogBackups': '3',
        }
    }

    def __init__(self, config_path=None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # Determine base directory
            if getattr(sys, 'frozen', False):
                # If frozen, look in the same directory as the executable
                base_dir = os.path.dirname(sys.executable)
            else:
                # Default to same directory as the script
                base_dir = os.path.abspath(os.path.dirname(__file__))
            
            self.config_path = Path(base_dir) / "agent.ini"
        
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        """Load configuration from INI file"""
        if not self.config_path.exists():
            self.config.read_dict(self.DEFAULT_CONFIG)
            self.save()
        else:
            self.config.read(str(self.config_path))

    def save(self):
        """Save current configuration to INI file"""
        with open(self.config_path, 'w') as configfile:
            self.config.write(configfile)

    @property
    def server_url(self):
        return self.config.get('Server', 'URL').rstrip('/')

    @server_url.setter
    def server_url(self, value):
        self.config.set('Server', 'URL', value)
        self.save()

    @property
    def poll_interval(self):
        return self.config.getint('Server', 'PollInterval')

    @poll_interval.setter
    def poll_interval(self, value):
        self.config.set('Server', 'PollInterval', str(value))
        self.save()

    @property
    def agent_id(self):
        return self.config.get('Agent', 'ID')

    @agent_id.setter
    def agent_id(self, value):
        self.config.set('Agent', 'ID', value)
        self.save()

    @property
    def max_log_size(self):
        return self.config.getint('Agent', 'MaxLogSize', fallback=5*1024*1024)

    @property
    def max_log_backups(self):
        return self.config.getint('Agent', 'MaxLogBackups', fallback=3)

    def get_token(self):
        """Retrieve the JWT token securely from Windows Credential Manager"""
        return keyring.get_password("KinetixAgent", "jwt_token")

    def set_token(self, token):
        """Store the JWT token securely in Windows Credential Manager"""
        keyring.set_password("KinetixAgent", "jwt_token", token)

    def get_refresh_token(self):
        """Retrieve the Refresh token securely from Windows Credential Manager"""
        return keyring.get_password("KinetixAgent", "refresh_token")

    def set_refresh_token(self, token):
        """Store the Refresh token securely in Windows Credential Manager"""
        keyring.set_password("KinetixAgent", "refresh_token", token)

    def clear_tokens(self):
        """Remove both JWT and Refresh tokens from storage"""
        try:
            keyring.delete_password("KinetixAgent", "jwt_token")
        except keyring.errors.PasswordDeleteError:
            pass
        
        try:
            keyring.delete_password("KinetixAgent", "refresh_token")
        except keyring.errors.PasswordDeleteError:
            pass

    def get_device_private_key(self):
        """Retrieve device private key from an encrypted local file"""
        # Determine base directory
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            
        key_path = Path(base_dir) / ".device_key"
        if not key_path.exists():
            return None
            
        try:
            from cryptography.fernet import Fernet
            import hashlib
            import uuid
            
            # Generate a consistent machine-specific key
            machine_id = str(uuid.getnode()).encode()
            enc_key = base64.urlsafe_b64encode(hashlib.sha256(machine_id).digest())
            fernet = Fernet(enc_key)
            
            with open(key_path, 'rb') as f:
                encrypted_data = f.read()
                return fernet.decrypt(encrypted_data).decode('utf-8')
        except Exception:
            return None

    def set_device_private_key(self, key_pem):
        """Store device private key in an encrypted local file"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            
        key_path = Path(base_dir) / ".device_key"
        
        from cryptography.fernet import Fernet
        import hashlib
        import uuid
        
        # Generate a consistent machine-specific key
        machine_id = str(uuid.getnode()).encode()
        enc_key = base64.urlsafe_b64encode(hashlib.sha256(machine_id).digest())
        fernet = Fernet(enc_key)
        
        encrypted_data = fernet.encrypt(key_pem.encode('utf-8'))
        with open(key_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Set file to hidden on Windows
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(key_path), 0x02) # 0x02 is hidden
        except:
            pass

    def get_device_public_key(self):
        """Retrieve device public key from config"""
        return self.config.get('Agent', 'PublicKey', fallback=None)

    def set_device_public_key(self, key_pem):
        """Store device public key in config"""
        self.config.set('Agent', 'PublicKey', key_pem)
        self.save()
