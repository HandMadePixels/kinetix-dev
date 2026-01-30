@echo off
REM ============================================================================
REM Kinetix - Production-Grade Server Launcher
REM ============================================================================
REM This script starts the application using Waitress (WSGI) and Celery
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0.."

REM Ensure production settings are used
set DEBUG=False
set ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.7

echo.
echo ============================================================================
echo   Kinetix - Starting Production-Grade Environment
echo ============================================================================
echo.

REM 1. Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found! Run quickstart.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

REM New: Kill any process already on port 8000
echo Clearing port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
timeout /t 1 /nobreak >nul

REM 2. Check/Start Redis
echo [1/5] Checking Redis connection...
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('[OK] Redis is running')" 2>nul
if errorlevel 1 (
    echo [INFO] Redis is not running. Attempting to start Redis server...
    where redis-server >nul 2>&1
    if %errorlevel% equ 0 (
        start "Kinetix - Redis Server" cmd /k "redis-server"
        echo Waiting for Redis to initialize...
        timeout /t 5 /nobreak >nul
    ) else (
        echo [ERROR] redis-server.exe not found in PATH! 
        echo Please install Redis and ensure it is in your PATH.
        pause
        exit /b 1
    )
) else (
    echo [OK] Redis is already running.
)

REM 3. Run migrations and collectstatic
echo [2/5] Preparing database and static files...
python manage.py makemigrations --noinput
python manage.py migrate --noinput
if not exist "staticfiles" mkdir staticfiles
REM Removed --clear because it causes PermissionErrors on Windows when files are locked
python manage.py collectstatic --noinput
echo [OK] Preparation complete.

REM 4. Verify Security Settings
echo [3/5] Verifying environment configuration...
python -c "from decouple import config; debug = config('DEBUG', default=False, cast=bool); print('[WARNING] DEBUG is set to TRUE! This is NOT recommended for production.' if debug else '[OK] Running in production mode (DEBUG=False)')"

REM 5. Start Services
echo [4/5] Starting application services...
set CURRENT_DIR=%CD%

REM Start Waitress (WSGI Server)
echo Starting Waitress server on http://0.0.0.0:8000 ...
start "Kinetix - Production Web Server" cmd /k "cd /d %CURRENT_DIR% && echo Server is starting... && venv\Scripts\python.exe -m waitress --listen=0.0.0.0:8000 command_center.wsgi:application > logs\server_out.log 2> logs\server_err.log"

REM Start Celery Worker
echo Starting Celery worker...
start "Kinetix - Celery Worker" cmd /k "cd /d %CURRENT_DIR% && venv\Scripts\activate && celery -A command_center worker -l info --pool=solo --logfile=logs\worker.log"

REM Start Celery Beat
echo Starting Celery beat...
start "Kinetix - Celery Beat" cmd /k "cd /d %CURRENT_DIR% && venv\Scripts\activate && celery -A command_center beat -l info --logfile=logs\beat.log"

echo [5/5] Finalizing services...
timeout /t 5 /nobreak >nul

echo.
echo ============================================================================
echo   Production-Grade Services Started!
echo ============================================================================
echo.
echo Web Interface: http://192.168.1.7:8000
echo.
echo PRO TIP: If you see "This site can't be reached":
echo 1. Check if the "Production Web Server" window shows any errors.
echo 2. Try using Incognito/Private mode in your browser.
echo 3. Ensure no other application (like a dev server) is using port 8000.
echo.
echo To stop everything, run: stop_dev.bat
echo ============================================================================
echo.

start http://192.168.1.7:8000
pause
