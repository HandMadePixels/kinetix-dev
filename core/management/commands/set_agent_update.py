import os
import hashlib
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from core.models import SystemConfig

class Command(BaseCommand):
    help = 'Sets the latest agent version and installer file'

    def add_arguments(self, parser):
        parser.add_argument('version', type=str, help='The version string (e.g. 1.0.1.0)')
        parser.add_argument('msi_path', type=str, help='Path to the agent MSI file')

    def handle(self, *args, **options):
        version = options['version']
        msi_path = options['msi_path']

        if not os.path.exists(msi_path):
            raise CommandError(f"MSI file not found at: {msi_path}")

        self.stdout.write(f"Setting agent update to version {version}...")

        config = SystemConfig.get_config()
        config.latest_agent_version = version
        
        with open(msi_path, 'rb') as f:
            config.agent_msi_file.save(os.path.basename(msi_path), File(f), save=False)
            
            # Re-compute hash just to be sure (model save handles it but we can log it here)
            f.seek(0)
            hasher = hashlib.sha256()
            while chunk := f.read(8192):
                hasher.update(chunk)
            config.agent_msi_sha256 = hasher.hexdigest()

        config.save()

        self.stdout.write(self.style.SUCCESS(f"Successfully updated agent to version {version}"))
        self.stdout.write(f"MSI Path: {config.agent_msi_file.name}")
        self.stdout.write(f"SHA256: {config.agent_msi_sha256}")
