import requests
import json
import time
import os
import sys
from logger import agent_log
from config import AgentConfig

class AgentClient:
    """Handles communication with the Kinetix API"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.verify = True # Enforce SSL verification

    def _get_headers(self, authenticated=True):
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'KinetixAgent/1.0.0 (Windows)'
        }
        if authenticated:
            token = self.config.get_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'
        return headers

    def register(self, hostname, ip_address, os_version):
        """Register agent with the Kinetix"""
        url = f"{self.config.server_url}/api/v1/register/"
        payload = {
            "hostname": hostname,
            "ip_address": ip_address,
            "os_version": os_version,
            "agent_version": "1.0.0",
            "device_id": self.config.agent_id or None
        }
        
        try:
            response = self.session.post(
                url, 
                json=payload, 
                headers=self._get_headers(authenticated=False),
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.config.agent_id = data.get('device_id')
                self.config.set_token(data.get('token'))
                
                # Save public key if provided
                public_key = data.get('public_key')
                if public_key:
                    try:
                        key_filename = self.config.config.get('Security', 'PublicKeyFile', fallback='public_key.pem')
                        
                        # Correctly resolve path for both script and EXE
                        if getattr(sys, 'frozen', False):
                            base_dir = os.path.dirname(sys.executable)
                        else:
                            base_dir = os.path.dirname(os.path.abspath(__file__))
                            
                        key_path = os.path.join(base_dir, key_filename)
                        
                        with open(key_path, 'wb') as f:
                            f.write(public_key.strip().encode('utf-8'))
                        agent_log.info(f"Updated public key: {key_path}")
                    except Exception as e:
                        agent_log.error(f"Failed to save public key: {e}")

                agent_log.info(f"Successfully registered. Device ID: {self.config.agent_id}")
                return True
            else:
                agent_log.error(f"Registration failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            agent_log.error(f"Network error during registration: {e}")
            return False

    def get_commands(self):
        """Poll for new commands"""
        url = f"{self.config.server_url}/api/v1/commands/"
        params = {"hostname": self.config.agent_id}
        
        try:
            response = self.session.get(
                url, 
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                agent_log.warning("Authentication failed, re-registering...")
                # Token might be expired, reset and trigger logic in main loop
                return {"error": "unauthorized"}
            else:
                agent_log.error(f"Failed to fetch commands: {response.status_code}")
                return None
        except Exception as e:
            agent_log.error(f"Network error during polling: {e}")
            return None

    def send_inventory(self, inventory_data):
        """Send collected system inventory to server"""
        url = f"{self.config.server_url}/api/v1/inventory/"
        
        # Debug: Print keys being sent
        print(f"Sending inventory keys: {list(inventory_data.keys())}")
        print(f"Number of services: {len(inventory_data.get('services', []))}")
        print(f"Number of apps: {len(inventory_data.get('installed_apps', []))}")
        
        try:
            response = self.session.post(
                url, 
                json=inventory_data, 
                headers=self._get_headers(),
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                agent_log.info("Inventory successfully submitted")
                return True
            else:
                agent_log.error(f"Failed to send inventory: {response.status_code}")
                return False
        except Exception as e:
            agent_log.error(f"Network error during inventory submission: {e}")
            return False

    def send_update_status(self, push_id, status, error_message=None):
        """Submit update installation status to server"""
        url = f"{self.config.server_url}/api/v1/update-status/"
        payload = {
            "push_id": push_id,
            "status": status,
            "error_message": error_message or ""
        }
        
        # Exponential backoff for retries
        max_retries = 3
        for i in range(max_retries):
            try:
                response = self.session.post(
                    url, 
                    json=payload, 
                    headers=self._get_headers(),
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    agent_log.info(f"Update status ({status}) successfully submitted for {push_id}")
                    return True
                else:
                    agent_log.error(f"Status submission failed ({response.status_code}). Retry {i+1}")
                    time.sleep(2 ** i)
            except Exception as e:
                agent_log.error(f"Network error sending update status: {e}. Retry {i+1}")
                time.sleep(2 ** i)
        
        return False
