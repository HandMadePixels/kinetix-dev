"""
Cryptographic utilities for RSA signing and verification
"""

import hashlib
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend


def generate_rsa_keypair(key_size=4096):
    """
    Generate RSA keypair for signing updates.
    
    Args:
        key_size: Key size in bits (default 4096 for high security)
    
    Returns:
        tuple: (private_key_pem, public_key_pem) as strings
    """
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Serialize private key to PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize public key to PEM format
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return private_pem, public_pem


def sign_data(data, private_key_pem):
    """
    Sign data using RSA private key.
    
    Args:
        data: bytes or str to sign
        private_key_pem: Private key in PEM format (str)
    
    Returns:
        str: Base64-encoded signature
    """
    import base64
    
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    # Load private key
    key_data = private_key_pem.strip().encode('utf-8')
    private_key = serialization.load_pem_private_key(
        key_data,
        password=None,
        backend=default_backend()
    )
    
    # Sign data
    signature = private_key.sign(
        data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Return base64-encoded signature
    return base64.b64encode(signature).decode('utf-8')


def verify_signature(data, signature_b64, public_key_pem):
    """
    Verify RSA signature.
    
    Args:
        data: bytes or str that was signed
        signature_b64: Base64-encoded signature (str)
        public_key_pem: Public key in PEM format (str)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    import base64
    
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Decode signature
        signature = base64.b64decode(signature_b64)
        
        # Load public key
        key_data = public_key_pem.strip().encode('utf-8')
        public_key = serialization.load_pem_public_key(
            key_data,
            backend=default_backend()
        )
        
        # Verify signature
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        return True
    
    except Exception:
        return False


def compute_file_hash(file_path, algorithm='sha256'):
    """
    Compute hash of a file.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, sha512)
    
    Returns:
        str: Hexadecimal hash digest
    """
    # SECURITY FIX: Restrict to secure algorithms
    allowed_algorithms = {'sha256', 'sha512'}
    if algorithm.lower() not in allowed_algorithms:
        raise ValueError(f"Insecure or unsupported hash algorithm: {algorithm}. Use sha256 or sha512.")

    hash_func = getattr(hashlib, algorithm.lower())()
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for hashing: {file_path}")

    with open(file_path, 'rb') as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(65536), b''): # Larger chunks for performance
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def compute_data_hash(data, algorithm='sha256'):
    """
    Compute hash of data.
    
    Args:
        data: bytes or str to hash
        algorithm: Hash algorithm (sha256, sha512)
    
    Returns:
        str: Hexadecimal hash digest
    """
    # SECURITY FIX: Restrict to secure algorithms
    allowed_algorithms = {'sha256', 'sha512'}
    if algorithm.lower() not in allowed_algorithms:
        raise ValueError(f"Insecure or unsupported hash algorithm: {algorithm}. Use sha256 or sha512.")

    if isinstance(data, str):
        data = data.encode('utf-8')
    
    hash_func = getattr(hashlib, algorithm.lower())()
    hash_func.update(data)
    
    return hash_func.hexdigest()


def sign_file(file_path, private_key_pem):
    """
    Sign a file using RSA private key.
    
    Args:
        file_path: Path to file to sign
        private_key_pem: Private key in PEM format (str)
    
    Returns:
        tuple: (sha256_hash, signature_b64)
    """
    # Compute file hash
    file_hash = compute_file_hash(file_path, 'sha256')
    
    # Sign the hash
    signature = sign_data(file_hash, private_key_pem)
    
    return file_hash, signature


from cryptography.fernet import Fernet

def encrypt_with_public_key(data, public_key_pem):
    """
    Encrypt data using a hybrid RSA + Fernet approach.
    1. Generate a random symmetric key (Fernet).
    2. Encrypt the data with Fernet.
    3. Encrypt the Fernet key with the RSA public key.
    4. Return (Encrypted Key |:| Encrypted Data) as Base64.
    """
    import base64
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # 1. Symmetric Encryption (Fast, no size limit)
        sym_key = Fernet.generate_key()
        f = Fernet(sym_key)
        ciphertext_data = f.encrypt(data)
        
        # 2. Asymmetric Encryption of the Key
        key_data = public_key_pem.strip().encode('utf-8')
        public_key = serialization.load_pem_public_key(
            key_data,
            backend=default_backend()
        )
        
        encrypted_key = public_key.encrypt(
            sym_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # 3. Combine both (Base64 encoded)
        combined = base64.b64encode(encrypted_key).decode('utf-8') + ":" + base64.b64encode(ciphertext_data).decode('utf-8')
        return combined
        
    except Exception as e:
        raise Exception(f"RSA Hybrid Encryption failed: {str(e)}")


def decrypt_with_private_key(combined_ciphertext, private_key_pem):
    """
    Decrypt data using the hybrid RSA + Fernet approach.
    """
    import base64
    try:
        if ":" not in combined_ciphertext:
            raise ValueError("Invalid combined ciphertext format")
            
        enc_key_b64, enc_data_b64 = combined_ciphertext.split(":", 1)
        encrypted_key = base64.b64decode(enc_key_b64)
        ciphertext_data = base64.b64decode(enc_data_b64)
        
        # 1. Decrypt the Symmetric Key
        key_data = private_key_pem.strip().encode('utf-8')
        private_key = serialization.load_pem_private_key(
            key_data,
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
        
        # 2. Decrypt the Data
        f = Fernet(sym_key)
        plaintext = f.decrypt(ciphertext_data)
        return plaintext.decode('utf-8')
        
    except Exception as e:
        raise Exception(f"RSA Hybrid Decryption failed: {str(e)}")


def verify_file_signature(file_path, expected_hash, signature_b64, public_key_pem):
    """
    Verify file signature.
    
    Args:
        file_path: Path to file
        expected_hash: Expected SHA256 hash
        signature_b64: Base64-encoded signature
        public_key_pem: Public key in PEM format
    
    Returns:
        tuple: (hash_valid, signature_valid)
    """
    # Compute actual hash
    actual_hash = compute_file_hash(file_path, 'sha256')
    
    # Check hash matches
    hash_valid = actual_hash == expected_hash
    
    # Verify signature
    signature_valid = verify_signature(expected_hash, signature_b64, public_key_pem)
    
    return hash_valid, signature_valid
