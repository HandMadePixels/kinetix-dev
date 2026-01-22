import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import RSAKeyPair
from core.crypto import generate_rsa_keypair

class Command(BaseCommand):
    help = 'Generates RSA keypair for signing and verification'

    def handle(self, *args, **options):
        self.stdout.write("Checking for existing RSA keys...")
        
        # Check if keypair already exists in DB
        key_obj = RSAKeyPair.objects.first()
        
        if key_obj:
            self.stdout.write(self.style.SUCCESS("RSA keypair already exists in database."))
            private_pem = key_obj.private_key
            public_pem = key_obj.public_key
        else:
            self.stdout.write("Generating new 4096-bit RSA keypair...")
            private_pem, public_pem = generate_rsa_keypair(key_size=4096)
            
            RSAKeyPair.objects.create(
                private_key=private_pem,
                public_key=public_pem
            )
            self.stdout.write(self.style.SUCCESS("New RSA keypair generated and saved to database."))

        # Ensure keys directory exists
        keys_dir = os.path.join(settings.BASE_DIR, 'keys')
        os.makedirs(keys_dir, exist_ok=True)

        # Save public key to file system (needed by Agent build process)
        public_path = os.path.join(keys_dir, 'public_key.pem')
        with open(public_path, 'w') as f:
            f.write(public_pem)
        
        self.stdout.write(f"Public key exported to: {public_path}")

        # Opt-out: Don't save private key to disk unless requested, for security.
        # But for this dev project, let's save it to help the user.
        private_path = os.path.join(keys_dir, 'private_key.pem')
        with open(private_path, 'w') as f:
            f.write(private_pem)
            
        self.stdout.write(f"Private key exported to: {private_path}")
        self.stdout.write(self.style.SUCCESS("Keys are ready!"))
