import requests
import hashlib
import os
import sys
import subprocess
import base64
import time
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from agent_logger import agent_log

class AgentUpdater:
    """Handles secure download, verification, and installation of updates"""
    
    def __init__(self, public_key_path):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
        
        self.base_dir = base_dir

        # Resolve public key path
        if not os.path.isabs(public_key_path):
            self.public_key_path = os.path.join(base_dir, public_key_path)
        else:
            self.public_key_path = public_key_path
            
        self.temp_dir = os.path.join(base_dir, "temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def download_file(self, url, dest_path):
        """Download file with progress tracking and resume support"""
        try:
            # Ensure a clean start for every download to avoid corruption
            if os.path.exists(dest_path):
                os.remove(dest_path)
            
            mode = 'wb'
            response = requests.get(url, stream=True, timeout=60, verify=True)
            
            if response.status_code in [200, 206]:
                with open(dest_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
            else:
                agent_log.error(f"Download failed with status code: {response.status_code}")
                return False
        except Exception as e:
            agent_log.error(f"Download error: {e}")
            return False

    def verify_hash(self, file_path, expected_hash):
        """Verify SHA256 hash of the downloaded file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        actual_hash = sha256_hash.hexdigest()
        if actual_hash.lower() == expected_hash.lower():
            return True
        else:
            agent_log.security(f"Hash mismatch! Expected: {expected_hash}, Actual: {actual_hash}")
            return False

    def verify_signature(self, file_path, signature_b64, expected_hash):
        """Verify RSA signature using the embedded public key"""
        try:
            if not os.path.exists(self.public_key_path):
                agent_log.error("Public key not found for signature verification")
                return False

            with open(self.public_key_path, "rb") as key_file:
                key_data = key_file.read().strip()
                public_key = serialization.load_pem_public_key(key_data)

            # Decode signature from Base64
            signature = base64.b64decode(signature_b64)
            
            # The server signs the hexadecimal hash string, not the binary data
            data_to_verify = expected_hash.lower().encode('utf-8')
            
            public_key.verify(
                signature,
                data_to_verify,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            agent_log.security(f"Signature verification failed: {type(e).__name__} - {e}")
            return False

    def install_update(self, file_path, args=None):
        """Execute update installer silently"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.msi':
                # Create a log file path for msiexec in the agent logs directory
                log_dir = os.path.join(self.base_dir, 'logs')
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                log_file = os.path.join(log_dir, f"install_{int(time.time())}.log")

                # ALLUSERS=1 forces per-machine installation (crucial for SYSTEM services)
                # REINSTALLMODE=amus ensures we overwrite/upgrade correctly
                cmd = [
                    'msiexec', '/i', file_path, 
                    '/quiet', '/norestart', 
                    'ALLUSERS=1', 'REINSTALLMODE=amus',
                    f'/L*V', log_file
                ]
                if args:
                    cmd.extend(args.split())
            elif ext == '.exe':
                cmd = [file_path, '/S', '/v', '/qn'] # Standard silent flags
                if args:
                    cmd.extend(args.split())
            else:
                agent_log.error(f"Unsupported file extension: {ext}")
                return False

            agent_log.info(f"Executing install: {' '.join(cmd)}")
            result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
            
            if result.returncode == 0:
                agent_log.info("Installation successful")
                return True
            else:
                agent_log.error(f"Installation failed with return code {result.returncode}: {result.stderr}")
                return False
        except Exception as e:
            agent_log.error(f"Installation error: {e}")
            return False
        finally:
            # Cleanup temp file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except: pass
