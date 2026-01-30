import requests
import json
import time
import os
import sys
from agent_logger import agent_log
from agent_config import AgentConfig

class AgentClient:
    """Handles communication with the Kinetix API"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.verify = True # Enforce SSL verification

    def _ensure_device_keypair(self):
        """Ensure device has its own RSA keypair for secure token exchange"""
        if not self.config.get_device_private_key():
            agent_log.info("Generating new device keypair for secure handshake...")
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend

            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048, # Reduced from 4096 for better performance and to prevent service hang
                backend=default_backend()
            )
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            self.config.set_device_private_key(private_pem)
            self.config.set_device_public_key(public_pem)
            return private_pem, public_pem
        
        return self.config.get_device_private_key(), self.config.get_device_public_key()

    def _decrypt_token(self, combined_ciphertext):
        """Decrypt token using hybrid RSA + Fernet approach"""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        from cryptography.fernet import Fernet
        import base64

        if ":" not in combined_ciphertext:
            raise ValueError("Invalid secure token format")

        enc_key_b64, enc_data_b64 = combined_ciphertext.split(":", 1)
        encrypted_key = base64.b64decode(enc_key_b64)
        ciphertext_data = base64.b64decode(enc_data_b64)

        private_key_pem = self.config.get_device_private_key()
        if not private_key_pem:
            raise ValueError("No device private key available for decryption")

        # 1. Decrypt the Fernet Key using RSA
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        sym_key = private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # 2. Decrypt the actual data using Fernet
        f = Fernet(sym_key)
        plaintext = f.decrypt(ciphertext_data)
        return plaintext.decode('utf-8')

    def _get_headers(self, authenticated=True):
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'KinetixAgent/{self.config.version} (Windows)'
        }
        if authenticated:
            token = self.config.get_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'
        return headers

    def _refresh_auth(self):
        """Attempt to refresh the access token using the refresh token"""
        refresh_token = self.config.get_refresh_token()
        if not refresh_token:
            agent_log.warning("No refresh token available.")
            return False
        
        url = f"{self.config.server_url}/api/v1/token/refresh/"
        try:
            response = self.session.post(url, json={'refresh': refresh_token}, timeout=15)
            if response.status_code == 200:
                data = response.json()
                self.config.set_token(data['access'])
                # If rotation is enabled, we might get a new refresh token
                if 'refresh' in data:
                    self.config.set_refresh_token(data['refresh'])
                agent_log.info("Access token refreshed successfully.")
                return True
            else:
                agent_log.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            agent_log.error(f"Error during token refresh: {e}")
            return False

    def _make_request(self, method, endpoint, **kwargs):
        """
        Wrapper for requests to handle token refreshing on 401.
        endpoint: relative path (e.g. 'commands/') or full URL
        """
        # Construct URL if needed
        if not endpoint.startswith('http'):
            url = f"{self.config.server_url}/api/v1/{endpoint}"
        else:
            url = endpoint

        # Prepare headers
        authenticated = kwargs.pop('authenticated', True)
        headers = kwargs.pop('headers', {})
        
        # Merge default headers if not provided
        default_headers = self._get_headers(authenticated=authenticated)
        for k, v in default_headers.items():
            if k not in headers:
                headers[k] = v
        
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            
            # If unauthorized, try to refresh and retry ONCE
            if response.status_code == 401 and authenticated:
                agent_log.info("Token expired (401). Attempting refresh...")
                if self._refresh_auth():
                    # Update headers with new token
                    headers.update(self._get_headers(authenticated=True))
                    # Retry the request
                    response = self.session.request(method, url, headers=headers, **kwargs)
                else:
                    agent_log.warning("Token refresh failed. Re-authentication/Re-registration may be required.")
            
            return response
        except Exception as e:
            # Re-raise to let caller handle logging specific to their context if they want,
            # but usually we log here and return None? 
            # The existing code structure catches exceptions in the caller methods.
            raise e

    def register(self, hostname, ip_address, os_version):
        """Register agent with the Kinetix"""
        url = f"register/"
        
        # Ensure device has its own keypair first
        private_key_pem, public_key_pem = self._ensure_device_keypair()

        payload = {
            "hostname": hostname,
            "ip_address": ip_address,
            "os_version": os_version,
            "agent_version": self.config.version,
            "device_id": self.config.agent_id or None,
            "device_public_key": public_key_pem or "",
            "registration_signature": ""
        }
        
        # SECURITY FIX: Re-Registration Challenge
        # If we already have a device_id, we must sign the registration request
        # to prove we own the private key for the previously registered public key.
        if self.config.agent_id:
            try:
                from cryptography.hazmat.primitives import hashes, serialization
                from cryptography.hazmat.primitives.asymmetric import padding
                from cryptography.hazmat.backends import default_backend
                import base64

                # We sign the "hostname:device_id" string
                sign_payload = f"{hostname}:{self.config.agent_id}".encode('utf-8')
                
                private_key = serialization.load_pem_private_key(
                    private_key_pem.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
                
                signature = private_key.sign(
                    sign_payload,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.DIGEST_LENGTH
                    ),
                    hashes.SHA256()
                )
                
                payload["registration_signature"] = base64.b64encode(signature).decode('utf-8')
                agent_log.info("Identity signature included for re-registration.")
            except Exception as e:
                agent_log.error(f"Failed to sign registration payload: {e}")

        try:
            # authenticated=False for registration
            response = self._make_request('POST', url, json=payload, authenticated=False, timeout=30)
            
            if response is not None and response.status_code in [200, 201]:
                data = response.json()
                self.config.agent_id = data.get('device_id')
                self.config.set_token(data.get('token'))
                
                # SECURITY FIX: Retrieve and handle nonce for token exchange
                nonce_raw = data.get('nonce')
                is_encrypted = data.get('is_encrypted', False)
                
                if nonce_raw:
                    if is_encrypted:
                        try:
                            nonce = self._decrypt_token(nonce_raw)
                            agent_log.info("Successfully decrypted secure registration nonce.")
                        except Exception as e:
                            agent_log.error(f"Failed to decrypt nonce: {e}")
                            nonce = nonce_raw
                    else:
                        nonce = nonce_raw
                    
                    # Exchange nonce for refresh token
                    exchange_url = "token-exchange/"
                    exchange_payload = {
                        "device_id": self.config.agent_id,
                        "nonce": nonce
                    }
                    
                    agent_log.info("Exchanging nonce for initial refresh token...")
                    exchange_res = self._make_request('POST', exchange_url, json=exchange_payload, authenticated=False, timeout=15)
                    if exchange_res is not None and exchange_res.status_code == 200:
                        refresh_token = exchange_res.json().get('refresh')
                        self.config.set_refresh_token(refresh_token)
                        agent_log.info("Successfully retrieved refresh token via secure handshake.")
                    else:
                        code = exchange_res.status_code if exchange_res else "No Response"
                        agent_log.error(f"Token exchange failed: {code}")
                
                # Save public key if provided (server's public key for update verification)
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
                status = response.status_code if response is not None else "No Response"
                text = response.text if response is not None else ""
                agent_log.error(f"Registration failed: {status} - {text}")
                return False
        except Exception as e:
            agent_log.error(f"Network error during registration: {e}")
            return False

    def get_commands(self):
        """Poll for new commands"""
        params = {"hostname": self.config.agent_id}
        
        try:
            response = self._make_request('GET', 'commands/', params=params, timeout=30)
            
            if response is not None and response.status_code == 200:
                return response.json()
            elif response is not None and response.status_code == 401:
                agent_log.warning("Authentication failed after refresh attempt, re-registering...")
                return {"error": "unauthorized"}
            else:
                status = response.status_code if response is not None else "Unknown"
                agent_log.error(f"Failed to fetch commands: {status}")
                return None
        except Exception as e:
            agent_log.error(f"Network error during polling: {e}")
            return None

    def get_latest_agent_info(self):
        """Check server for the latest agent version info"""
        try:
            response = self._make_request('GET', 'agent-update/check/', timeout=15)
            if response is not None and response.status_code == 200:
                return response.json()
            elif response is not None and response.status_code == 401:
                return {"error": "unauthorized"}
            return None
        except Exception as e:
            agent_log.error(f"Error checking for agent update: {e}")
            return None

    def send_inventory(self, inventory_data):
        """Send collected system inventory to server"""
        
        # Debug: Print keys being sent
        # print(f"Sending inventory keys: {list(inventory_data.keys())}")
        
        try:
            response = self._make_request('POST', 'inventory/', json=inventory_data, timeout=60)
            
            if response is not None and response.status_code in [200, 201]:
                agent_log.info("Inventory successfully submitted")
                return True
            elif response is not None and response.status_code == 401:
                return {"error": "unauthorized"}
            else:
                status = response.status_code if response is not None else "Unknown"
                agent_log.error(f"Failed to send inventory: {status}")
                return False
        except Exception as e:
            agent_log.error(f"Network error during inventory submission: {e}")
            return False

    def send_update_status(self, push_id, status, error_message=None):
        """Submit update installation status to server"""
        payload = {
            "push_id": push_id,
            "status": status,
            "error_message": error_message or ""
        }
        
        # Exponential backoff for retries
        max_retries = 3
        for i in range(max_retries):
            try:
                response = self._make_request('POST', 'update-status/', json=payload, timeout=30)
                
                if response is not None and response.status_code in [200, 201]:
                    agent_log.info(f"Update status ({status}) successfully submitted for {push_id}")
                    return True
                else:
                    code = response.status_code if response is not None else "Unknown"
                    agent_log.error(f"Status submission failed ({code}). Retry {i+1}")
                    time.sleep(2 ** i)
            except Exception as e:
                agent_log.error(f"Network error sending update status: {e}. Retry {i+1}")
                time.sleep(2 ** i)
        
        return False

    def send_command_status(self, command_id, status, message=None):
        """Submit generic command status to server"""
        payload = {
            "command_id": command_id,
            "status": status,
            "message": message or ""
        }
        try:
            response = self._make_request('POST', 'command-status/', json=payload, timeout=30)
            return response is not None and response.status_code in [200, 201]
        except Exception as e:
            agent_log.error(f"Error sending command status: {e}")
            return False