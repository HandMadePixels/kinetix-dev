@echo off
REM ============================================================================
REM Kinetix - Quick Start Setup Script
REM ============================================================================
REM This script automates the initial setup of the Kinetix application
REM Run this script to set up the development environment in minutes
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo.
echo ============================================================================
echo   Kinetix - Quick Start Setup
echo ============================================================================
echo.

REM Check if Python is installed
echo [1/10] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)

python --version
echo [OK] Python found
echo.

REM Check if virtual environment exists
echo [2/10] Checking virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo [OK] Virtual environment already exists
) else (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)
echo.

REM Activate virtual environment
echo [3/10] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM Install dependencies
echo [4/10] Installing dependencies...
echo This may take a few minutes...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Create and verify .env file
echo [5/10] Setting up environment configuration...
python server-manager\ensure_keys.py
if errorlevel 1 (
    echo [ERROR] Failed to set up environment keys
    pause
    exit /b 1
)
echo [OK] Environment configuration verified

echo.

REM Create necessary directories
echo [6/10] Creating directories...
if not exist "logs" mkdir logs
if not exist "media" mkdir media
if not exist "media\updates" mkdir media\updates
if not exist "staticfiles" mkdir staticfiles
if not exist "keys" mkdir keys
if not exist "backups" mkdir backups
echo [OK] Directories created
echo.

REM Check if Redis is running
echo [7/11] Checking Redis connection...
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('[OK] Redis is running')" 2>nul
if errorlevel 1 (
    echo [INFO] Redis is not running. Attempting to start Redis server...
    where redis-server >nul 2>&1
    if %errorlevel% equ 0 (
        start "Kinetix - Redis Server" cmd /k "redis-server"
        echo [OK] Started Redis server in a new window
    ) else (
        echo [WARNING] redis-server.exe not found in PATH.
        echo Please ensure Redis is installed for background tasks to work.
    )
) else (
    echo [OK] Redis is running
)
echo.

REM Run database migrations
echo [8/11] Running database migrations...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Database migration failed
    pause
    exit /b 1
)
echo [OK] Database migrations completed
echo.

REM Generate RSA keypair
echo [9/11] Generating RSA keypair for update signing...
python manage.py generate_keypair
if errorlevel 1 (
    echo [WARNING] Could not generate keypair automatically
) else (
    echo [OK] RSA keys generated and exported to keys/ folder
)
echo.

REM Collect static files
echo [10/11] Collecting static files...
python manage.py collectstatic --noinput >nul 2>&1
echo [OK] Static files collected
echo.

REM Create superuser prompt
echo [11/11] Creating superuser account...
echo.
echo You need to create an admin account to access the system.
echo.
set /p CREATE_USER="Create superuser now? (y/n): "
if /i "%CREATE_USER%"=="y" (
    python manage.py createsuperuser
    if errorlevel 1 (
        echo [WARNING] Superuser creation skipped or failed
        echo You can create it later with: python manage.py createsuperuser
    ) else (
        echo [OK] Superuser created
    )
) else (
    echo [SKIPPED] You can create a superuser later with: python manage.py createsuperuser
)
echo.

REM Setup complete
echo ============================================================================
echo   Setup Complete!
echo ============================================================================
echo.
echo Your Kinetix is ready to run!
echo.
echo NEXT STEPS:
echo.
echo 1. Start Services:
echo    server-manager\run_dev.bat
echo.
echo 2. Access the application:
echo    Web Interface: http://localhost:8000
echo    Admin Panel:   http://localhost:8000/admin
echo.
echo ============================================================================
echo.
echo TIP: Run 'server-manager\run_dev.bat' to start all services (including Redis) automatically
echo.
echo For more information, see QUICKSTART.md
echo ============================================================================
echo.

pause
