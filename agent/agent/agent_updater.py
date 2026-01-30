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
    
    # SECURITY FIX: Explicitly allow only secure hash algorithms
    ALLOWED_HASH_ALGORITHMS = {'sha256', 'sha512'}

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

    def compute_file_hash(self, file_path, algorithm='sha256'):
        """Helper to compute hash of a file safely"""
        if algorithm.lower() not in self.ALLOWED_HASH_ALGORITHMS:
            raise ValueError(f"Insecure or unsupported hash algorithm: {algorithm}")
            
        hash_func = getattr(hashlib, algorithm.lower())()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                hash_func.update(byte_block)
        return hash_func.hexdigest()

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
        try:
            actual_hash = self.compute_file_hash(file_path, 'sha256')
            if actual_hash.lower() == expected_hash.lower():
                return True
            else:
                agent_log.security(f"Hash mismatch! Expected: {expected_hash}, Actual: {actual_hash}")
                return False
        except Exception as e:
            agent_log.error(f"Hash calculation error: {e}")
            return False

    def verify_mime(self, file_path):
        """Verify the content type of the file using magic bytes"""
        try:
            import magic
            # Use specific path if needed, but magic.from_file is usually fine on Windows with -bin
            mime_type = magic.from_file(file_path, mime=True)
            
            allowed_mimes = [
                'application/x-msi', 
                'application/x-dosexec', 
                'application/x-ms-dos-executable',
                'application/vnd.microsoft.portable-executable',
                'application/zip',
                'application/x-zip-compressed'
            ]
            
            if mime_type in allowed_mimes:
                return True
            
            agent_log.security(f"MIME verification failed: Content type {mime_type} is not allowed.")
            return False
        except ImportError:
            agent_log.warning("MIME verification skipped: 'magic' module not found in bundle.")
            return True
        except Exception as e:
            agent_log.warning(f"MIME verification failed: {e}")
            return True

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
        import shutil
        import tempfile
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.msi':
                # SECURITY/STABILITY: Copy MSI to system temp folder. 
                # If we run it from the installation dir, it might get deleted/locked during the upgrade.
                sys_temp = tempfile.gettempdir()
                target_msi = os.path.join(sys_temp, os.path.basename(file_path))
                shutil.copy2(file_path, target_msi)
                
                # Create a log file path for msiexec
                log_file = os.path.join(sys_temp, f"kinetix_install_{int(time.time())}.log")

                # /i : install
                # /quiet : no UI
                # /norestart : don't reboot the machine
                # ALLUSERS=1 : per-machine install
                # ALLUSERS=1 : per-machine install
                cmd = [
                    'msiexec', '/i', f'"{target_msi}"', 
                    '/quiet', '/norestart', 
                    'ALLUSERS=1',
                    f'/L*V', f'"{log_file}"'
                ]
                if args:
                    cmd.extend(args.split())
                
                agent_log.info(f"Launching MSI installer: {' '.join(cmd)}")
                
                # Use DETACHED_PROCESS and CREATE_NEW_PROCESS_GROUP to ensure the installer
                # stays alive after the agent service process exits.
                # Only on Windows.
                creation_flags = 0
                if os.name == 'nt':
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008 # DETACHED_PROCESS
                
                subprocess.Popen(' '.join(cmd), shell=True, close_fds=True, creationflags=creation_flags)
                return True

            elif ext == '.exe':
                cmd = [file_path, '/S', '/v', '/qn'] # Standard silent flags
                if args:
                    cmd.extend(args.split())
                agent_log.info(f"Executing EXE install: {' '.join(cmd)}")
                result = subprocess.run(cmd, shell=False, capture_output=True, text=True)
                return result.returncode == 0
            else:
                agent_log.error(f"Unsupported file extension: {ext}")
                return False

        except Exception as e:
            agent_log.error(f"Installation error: {e}")
            return False
        finally:
            # We don't cleanup MSI here anymore because Popen is async
            if ext != '.msi':
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except: pass
