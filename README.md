# Endpoint Management Kinetix

## Overview
Enterprise-grade Django-based endpoint management system for secure Windows update delivery and device inventory management. Packaged as a standalone Windows MSI installer.

## Features
- **Device Registration**: Automatic device registration with JWT authentication
- **Update Management**: Upload, verify, and push updates with digital signatures
- **Inventory Management**: Track services and installed applications per device
- **Real-time Dashboard**: Monitor device status, pending updates, and inventory
- **Audit Logging**: Complete audit trail for all operations
- **Security**: OWASP-compliant with encryption, rate limiting, and malware scanning

## Architecture
- **Backend**: Django 5.x + Django REST Framework
- **Database**: SQLite (embedded) with PostgreSQL migration path
- **Task Queue**: Celery + Redis for async operations
- **Frontend**: Django Templates + HTMX + Bootstrap 5
- **Security**: JWT auth, RSA signatures, Fernet encryption

## Installation

### Quick Start (Windows) ⚡
**Fastest way to get started - automated setup!**

```cmd
# 1. Run one-time setup (installs everything)
quickstart.bat

# 2. Start Redis in a separate terminal
redis-server

# 3. Start all services (Django + Celery)
run_dev.bat
```

That's it! The application will open in your browser at http://localhost:8000

See [BATCH_SCRIPTS.md](BATCH_SCRIPTS.md) for detailed information about all available scripts.

### MSI Installer (Recommended for Production)
1. Download `Kinetix-Setup.msi`
2. Run installer with admin privileges
3. Access at `https://localhost:8000`
4. Default credentials: admin/admin (change immediately)

### Manual Installation
```bash
# Clone repository
git clone <repo-url>
cd EndpointSoln

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# Generate RSA keypair
python manage.py generate_keypair

# Run development server
python manage.py runserver
```

## Project Structure
```
EndpointSoln/
├── command_center/          # Django project settings
├── core/                    # Core app (auth, models, utils)
├── api/                     # REST API endpoints
├── inventory/               # Device inventory management
├── updates/                 # Update management
├── dashboard/               # Admin dashboard
├── static/                  # Static files (CSS, JS)
├── templates/               # HTML templates
├── media/                   # Uploaded files
├── installer/               # MSI packaging scripts
├── requirements.txt
└── manage.py
```

## API Documentation

### Authentication
All API endpoints require JWT authentication (except registration).

**Header**: `Authorization: Bearer <token>`

### Endpoints

#### Device Registration
```http
POST /api/v1/register
Content-Type: application/json

{
  "hostname": "DEVICE-001",
  "ip_address": "192.168.1.100",
  "os_version": "Windows 11 Pro"
}

Response:
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "device_id": "uuid",
  "public_key": "-----BEGIN PUBLIC KEY-----..."
}
```

#### Upload Update
```http
POST /api/v1/updates
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <binary>
version: "1.0.0"
description: "Security patch"

Response:
{
  "update_id": "uuid",
  "sha256": "abc123...",
  "signature": "def456...",
  "scan_status": "clean"
}
```

#### Push Update
```http
POST /api/v1/push-update
Authorization: Bearer <token>
Content-Type: application/json

{
  "update_id": "uuid",
  "target_hostnames": ["DEVICE-001", "DEVICE-002"],
  "schedule": "2026-01-20T10:00:00Z"
}

Response:
{
  "task_id": "celery-task-uuid",
  "status": "queued"
}
```

#### Submit Inventory
```http
POST /api/v1/inventory
Authorization: Bearer <token>
Content-Type: application/json

{
  "hostname": "DEVICE-001",
  "services": [
    {
      "name": "wuauserv",
      "display_name": "Windows Update",
      "status": "running"
    }
  ],
  "installed_apps": [
    {
      "display_name": "Microsoft Office",
      "version": "16.0.0",
      "publisher": "Microsoft Corporation"
    }
  ]
}

Response:
{
  "status": "success",
  "inventory_id": "uuid"
}
```

#### Get Device Commands
```http
GET /api/v1/commands?hostname=DEVICE-001
Authorization: Bearer <token>

Response:
{
  "commands": [
    {
      "command": "update",
      "update_url": "https://server/media/updates/file.msi",
      "sha256": "abc123...",
      "signature": "def456..."
    }
  ]
}
```

## Security Features

### Encryption
- **Database**: Fernet encryption for sensitive fields (tokens, keys)
- **Transport**: HTTPS with TLS 1.2+
- **Files**: Encrypted storage for update files

### Authentication
- **JWT**: Short-lived tokens (15 min) with refresh (7 days)
- **RBAC**: Admin, Operator, Read-only roles
- **MFA**: Optional TOTP support

### Validation
- **Input**: Django forms + DRF serializers
- **File Upload**: Size limits, type validation, malware scanning
- **API**: Rate limiting (10 req/min per IP)

### Auditing
- All actions logged with user, timestamp, IP
- Failed authentication attempts tracked
- Suspicious activity alerts

## Configuration

### Environment Variables
Create `.env` file:
```env
SECRET_KEY=<django-secret-key>
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
VIRUSTOTAL_API_KEY=<your-key>
```

### Admin Settings
Access at `/admin/core/systemconfig/`:
- Server URL
- API keys (VirusTotal)
- Update retention policy
- Rate limiting thresholds

## Building MSI Installer

### Prerequisites
- Python 3.11+
- WiX Toolset 3.11+
- PyInstaller

### Build Steps
```bash
# 1. Freeze application
cd installer
python build_freeze.py

# 2. Create MSI
python build_msi.py

# Output: dist/Kinetix-Setup.msi
```

See `installer/BUILD.md` for detailed instructions.

## Development

### Running Tests
```bash
python manage.py test
```

### Code Quality
```bash
# Linting
flake8 .

# Security scan
bandit -r .

# Type checking
mypy .
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Deployment

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use strong `SECRET_KEY`
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Set up backup strategy
- [ ] Enable audit logging
- [ ] Configure email alerts
- [ ] Review security headers
- [ ] Test disaster recovery

## Troubleshooting

### Common Issues

**Q: Can't access server after installation**
A: Check Windows Firewall, ensure port 8000 is open

**Q: Update upload fails**
A: Check file size limits in settings, verify disk space

**Q: Device registration fails**
A: Verify network connectivity, check JWT token expiry

## Support
- Documentation: `/docs/`
- Issue Tracker: GitHub Issues
- Email: support@example.com

## License
Proprietary - All Rights Reserved

## Version
1.0.0 (2026-01-18)
