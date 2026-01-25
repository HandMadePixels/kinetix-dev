import os
import sys
import configparser
import keyring
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

    def get_token(self):
        """Retrieve the JWT token securely from Windows Credential Manager"""
        return keyring.get_password("KinetixAgent", "jwt_token")

    def set_token(self, token):
        """Store the JWT token securely in Windows Credential Manager"""
        keyring.set_password("KinetixAgent", "jwt_token", token)

    def clear_token(self):
        """Remove the JWT token from storage"""
        try:
            keyring.delete_password("KinetixAgent", "jwt_token")
        except keyring.errors.PasswordDeleteError:
            pass
