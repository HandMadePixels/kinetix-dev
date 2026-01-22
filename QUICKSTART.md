# Quick Start Guide

## Development Setup (5 minutes)

### 1. Prerequisites
- Python 3.11+ installed
- Redis installed (download from https://github.com/microsoftarchive/redis/releases)

### 2. Clone and Setup
```powershell
# Navigate to project
cd F:\EndpointSoln

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment
```powershell
# Copy environment template
copy .env.example .env

# Edit .env and set:
# - SECRET_KEY (generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
# - Other settings as needed
```

### 4. Initialize Database
```powershell
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Generate RSA keypair
python manage.py generate_keypair

# Collect static files
python manage.py collectstatic
```

### 5. Start Services

**Terminal 1 - Django Server:**
```powershell
python manage.py runserver
```

**Terminal 2 - Celery Worker:**
```powershell
celery -A command_center worker -l info --pool=solo
```

**Terminal 3 - Celery Beat (optional):**
```powershell
celery -A command_center beat -l info
```

### 6. Access Application
- Web Interface: http://localhost:8000
- Admin Panel: http://localhost:8000/admin
- API Docs: http://localhost:8000/api/v1/

## Testing the System

### Register a Test Device
```powershell
curl -X POST http://localhost:8000/api/v1/register/ `
  -H "Content-Type: application/json" `
  -d '{\"hostname\":\"TEST-PC-001\",\"ip_address\":\"192.168.1.100\",\"os_version\":\"Windows 11 Pro\"}'
```

Response will include JWT token - save it for next requests.

### Upload an Update
```powershell
# Create test file
echo "test update" > test_update.msi

# Upload (replace TOKEN with actual token)
curl -X POST http://localhost:8000/api/v1/updates/ `
  -H "Authorization: Bearer TOKEN" `
  -F "file=@test_update.msi" `
  -F "version=1.0.0" `
  -F "description=Test update"
```

### Submit Inventory
```powershell
curl -X POST http://localhost:8000/api/v1/inventory/ `
  -H "Authorization: Bearer TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    \"hostname\":\"TEST-PC-001\",
    \"services\":[
      {\"name\":\"wuauserv\",\"display_name\":\"Windows Update\",\"status\":\"running\"}
    ],
    \"installed_apps\":[
      {\"display_name\":\"Test App\",\"version\":\"1.0\",\"publisher\":\"Test Publisher\"}
    ]
  }'
```

## Building MSI Installer

### Prerequisites
- WiX Toolset 3.11+ (https://wixtoolset.org/)
- All development dependencies installed

### Build Process
```powershell
# Run build script
python installer\build_msi.py
```

Output: `dist\Kinetix-Setup.msi`

### Test Installation
```powershell
# Install
msiexec /i dist\Kinetix-Setup.msi /l*v install.log

# Check service
sc query Kinetix

# Access
# Open browser to https://localhost:8000
```

## Common Commands

### Django Management
```powershell
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Shell
python manage.py shell

# Database shell
python manage.py dbshell
```

### Celery
```powershell
# Worker
celery -A command_center worker -l info

# Beat scheduler
celery -A command_center beat -l info

# Flower (monitoring)
celery -A command_center flower
```

### Testing
```powershell
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test core

# Coverage
pytest --cov=. --cov-report=html
```

### Security
```powershell
# Check for vulnerabilities
pip-audit

# Security scan
bandit -r .

# Check dependencies
safety check
```

## Troubleshooting

### Redis Connection Error
```
Error: Redis connection refused
```
**Solution**: Start Redis server
```powershell
redis-server
```

### Database Locked
```
Error: database is locked
```
**Solution**: Close other connections to SQLite database

### Import Errors
```
Error: No module named 'xxx'
```
**Solution**: Ensure virtual environment is activated and dependencies installed
```powershell
venv\Scripts\activate
pip install -r requirements.txt
```

### Static Files Not Found
```
Error: 404 on /static/...
```
**Solution**: Collect static files
```powershell
python manage.py collectstatic
```

## Next Steps

1. **Configure VirusTotal API** - Get API key from https://www.virustotal.com/
2. **Set up HTTPS** - Generate SSL certificate or use Let's Encrypt
3. **Configure Email** - For alerts and notifications
4. **Review Security** - Follow SECURITY_AUDIT.md checklist
5. **Deploy to Production** - Follow deployment guide

## Resources

- Django Documentation: https://docs.djangoproject.com/
- DRF Documentation: https://www.django-rest-framework.org/
- Celery Documentation: https://docs.celeryproject.org/
- Security Guide: SECURITY_AUDIT.md
- Build Guide: installer/BUILD.md

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review documentation
3. Search GitHub issues
4. Contact support team
