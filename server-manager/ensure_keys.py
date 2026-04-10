import os
import sys
import secrets
from pathlib import Path

def ensure_keys():
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / '.env'
    env_example = project_root / '.env.example'

    if not env_file.exists():
        # Check for both .env.example and .env.sample
        templates = [project_root / '.env.example', project_root / '.env.sample']
        template_used = None
        
        for template in templates:
            if template.exists():
                template_used = template
                break
        
        if template_used:
            print(f"Creating .env from {template_used.name}...")
            with open(template_used, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
        else:
            print("No environment template found. Creating skeletal .env...")
            with open(env_file, 'w') as f:
                f.write("# Generated .env\nDEBUG=False\nALLOWED_HOSTS=localhost,127.0.0.1\n")

    with open(env_file, 'r') as f:
        lines = f.readlines()

    updated_lines = []
    keys_found = {'SECRET_KEY': False, 'ENCRYPTION_KEY': False}
    
    # Generate keys
    try:
        from django.core.management.utils import get_random_secret_key
        new_secret = get_random_secret_key()
    except ImportError:
        new_secret = secrets.token_urlsafe(50)
        
    try:
        from cryptography.fernet import Fernet
        new_encryption = Fernet.generate_key().decode()
    except ImportError:
        new_encryption = secrets.token_urlsafe(32) # Fallback if cryptography not installed yet

    modified = False
    
    for line in lines:
        original_line = line
        line_strip = line.strip()
        
        if line_strip.startswith('SECRET_KEY='):
            keys_found['SECRET_KEY'] = True
            val = line_strip.split('=', 1)[1].strip()
            if not val:
                line = f"SECRET_KEY={new_secret}\n"
                modified = True
                print("Generated new SECRET_KEY")
        
        elif line_strip.startswith('ENCRYPTION_KEY='):
            keys_found['ENCRYPTION_KEY'] = True
            val = line_strip.split('=', 1)[1].strip()
            if not val:
                line = f"ENCRYPTION_KEY={new_encryption}\n"
                modified = True
                print("Generated new ENCRYPTION_KEY")
        
        updated_lines.append(line)

    # Append if missing
    if not keys_found['SECRET_KEY']:
        updated_lines.append(f"SECRET_KEY={new_secret}\n")
        modified = True
        print("Added missing SECRET_KEY")
    
    if not keys_found['ENCRYPTION_KEY']:
        updated_lines.append(f"ENCRYPTION_KEY={new_encryption}\n")
        modified = True
        print("Added missing ENCRYPTION_KEY")

    if modified:
        with open(env_file, 'w') as f:
            f.writelines(updated_lines)
        print("Successfully updated .env with security keys.")
    else:
        print("All security keys are present.")

if __name__ == "__main__":
    ensure_keys()
