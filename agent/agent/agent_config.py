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
        # Persistent storage directory (survives MSI uninstalls/upgrades)
        self.persist_dir = Path(os.environ.get('ProgramData', 'C:\\ProgramData')) / "KinetixAgent"
        if not self.persist_dir.exists():
            try:
                os.makedirs(self.persist_dir, exist_ok=True)
            except:
                pass

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

    def _get_persist_file(self, filename):
        """Helper to get path to a file in the persistent directory"""
        return self.persist_dir / filename

    def _read_persist(self, filename):
        """Read a string from a persistent file"""
        p_file = self._get_persist_file(filename)
        if p_file.exists():
            try:
                return p_file.read_text().strip()
            except:
                return None
        return None

    def _write_persist(self, filename, content):
        """Write a string to a persistent file"""
        p_file = self._get_persist_file(filename)
        try:
            p_file.write_text(content)
            # Hide the file
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(p_file), 0x02)
        except:
            pass

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
        val = self.config.get('Server', 'URL').rstrip('/')
        if val == 'http://127.0.0.1:8000':
            # Check for backup in persist or keyring
            backup = self._read_persist("server_url") or keyring.get_password("KinetixAgent", "server_url")
            if backup:
                self.config.set('Server', 'URL', backup)
                self.save()
                return backup.rstrip('/')
        return val

    @server_url.setter
    def server_url(self, value):
        self.config.set('Server', 'URL', value)
        self.save()
        if value:
            self._write_persist("server_url", value)
            try: keyring.set_password("KinetixAgent", "server_url", value)
            except: pass

    @property
    def poll_interval(self):
        val = self.config.getint('Server', 'PollInterval')
        if val == 300:
            backup = self._read_persist("poll_interval") or keyring.get_password("KinetixAgent", "poll_interval")
            if backup:
                self.config.set('Server', 'PollInterval', str(backup))
                self.save()
                return int(backup)
        return val

    @poll_interval.setter
    def poll_interval(self, value):
        self.config.set('Server', 'PollInterval', str(value))
        self.save()
        if value:
            self._write_persist("poll_interval", str(value))
            try: keyring.set_password("KinetixAgent", "poll_interval", str(value))
            except: pass

    @property
    def update_check_interval(self):
        return self.config.getint('Agent', 'UpdateCheckInterval', fallback=3600)

    @update_check_interval.setter
    def update_check_interval(self, value):
        self.config.set('Agent', 'UpdateCheckInterval', str(value))
        self.save()

    @property
    def agent_id(self):
        # Primary: INI file
        val = self.config.get('Agent', 'ID', fallback='')
        if not val:
            # Backup: Persist or Keyring (survives MSI upgrades)
            val = self._read_persist("agent_id") or keyring.get_password("KinetixAgent", "agent_id") or ""
            if val:
                # Sync back to config if found
                self.config.set('Agent', 'ID', val)
                self.save()
        return val

    @agent_id.setter
    def agent_id(self, value):
        self.config.set('Agent', 'ID', value)
        self.save()
        if value:
            self._write_persist("agent_id", value)
            try: keyring.set_password("KinetixAgent", "agent_id", value)
            except: pass

    @property
    def max_log_size(self):
        return self.config.getint('Agent', 'MaxLogSize', fallback=5*1024*1024)

    @property
    def max_log_backups(self):
        return self.config.getint('Agent', 'MaxLogBackups', fallback=3)

    # The hardcoded version of the agent code. 
    # This should be incremented for every release.
    VERSION = "1.0.0.52"

    @property
    def version(self):
        return self.VERSION

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
        """Retrieve device private key from persistent storage"""
        # Primary: C:\ProgramData (most reliable for large blobs)
        val = self._read_persist("device_private_key")
        if val:
            return val

        # Secondary: Keyring (if small enough)
        try:
            val = keyring.get_password("KinetixAgent", "device_private_key")
            if val:
                return val
        except:
            pass

        # Legacy: Local hidden file in install dir
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
            
            machine_id = str(uuid.getnode()).encode()
            enc_key = base64.urlsafe_b64encode(hashlib.sha256(machine_id).digest())
            fernet = Fernet(enc_key)
            
            with open(key_path, 'rb') as f:
                encrypted_data = f.read()
                decrypted = fernet.decrypt(encrypted_data).decode('utf-8')
                if decrypted:
                    # Upgrade to persistent storage
                    self._write_persist("device_private_key", decrypted)
                return decrypted
        except Exception:
            return None

    def set_device_private_key(self, key_pem):
        """Store device private key in persistent storage"""
        # 1. Store in C:\ProgramData (Safe for any size)
        self._write_persist("device_private_key", key_pem)

        # 2. Try storing in Keyring (Optional backup, may fail due to size)
        try:
            keyring.set_password("KinetixAgent", "device_private_key", key_pem)
        except:
            # Expected if key is too large for keyring
            pass

        # 3. Store in local file (Compatibility)
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            
        key_path = Path(base_dir) / ".device_key"
        
        from cryptography.fernet import Fernet
        import hashlib
        import uuid
        
        machine_id = str(uuid.getnode()).encode()
        enc_key = base64.urlsafe_b64encode(hashlib.sha256(machine_id).digest())
        fernet = Fernet(enc_key)
        
        encrypted_data = fernet.encrypt(key_pem.encode('utf-8'))
        with open(key_path, 'wb') as f:
            f.write(encrypted_data)
        
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(key_path), 0x02) # hidden
        except:
            pass

    def get_device_public_key(self):
        """Retrieve device public key from config or persistent backup"""
        val = self.config.get('Agent', 'PublicKey', fallback='')
        if not val:
            val = self._read_persist("device_public_key") or ""
            if not val:
                try: val = keyring.get_password("KinetixAgent", "device_public_key") or ""
                except: pass
            
            if val:
                self.config.set('Agent', 'PublicKey', val)
                self.save()
        return val

    def set_device_public_key(self, key_pem):
        """Store device public key in config, persist, and keyring"""
        self.config.set('Agent', 'PublicKey', key_pem)
        self.save()
        self._write_persist("device_public_key", key_pem)
        try: keyring.set_password("KinetixAgent", "device_public_key", key_pem)
        except: pass
