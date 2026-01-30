@echo off
REM ============================================================================
REM Kinetix - Development Server Launcher
REM ============================================================================
REM This script starts all required services for development
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo.
echo ============================================================================
echo   Kinetix - Starting Development Environment
echo ============================================================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run quickstart.bat first to set up the project.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if Redis is running
echo Checking Redis connection...
python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('[OK] Redis is running')" 2>nul
if errorlevel 1 (
    echo.
    echo [INFO] Redis is not running. Attempting to start Redis server...
    
    REM Try to start redis-server in a new window
    where redis-server >nul 2>&1
    if %errorlevel% equ 0 (
        start "Kinetix - Redis Server" cmd /k "redis-server"
        echo Waiting for Redis to initialize...
        timeout /t 3 /nobreak >nul
        
        REM Re-check connection
        python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('[OK] Redis started successfully')" 2>nul
        if errorlevel 1 (
            echo [WARNING] Failed to connect to Redis after starting.
            echo Celery tasks may not work.
            set SKIP_CELERY=1
        ) else (
            echo [OK] Redis is now running
            set SKIP_CELERY=0
        )
    ) else (
        echo [WARNING] redis-server.exe not found in PATH.
        echo Please ensure Redis is installed and running.
        echo Celery tasks require Redis to be running.
        echo Press any key to continue without Celery, or Ctrl+C to exit...
        pause >nul
        set SKIP_CELERY=1
    )
) else (
    echo [OK] Redis is running
    set SKIP_CELERY=0
)
echo.

REM Check if database exists
if not exist "db.sqlite3" (
    echo [WARNING] Database not found. Running migrations...
    python manage.py migrate
    echo.
)

echo ============================================================================
echo   Starting Services
echo ============================================================================
echo.
echo This will open 3 terminal windows:
echo   1. Django Development Server (port 8000)
echo   2. Celery Worker (background tasks)
echo   3. Celery Beat (scheduled tasks)
echo.
echo Press any key to continue...
pause >nul
echo.

REM Get the current directory
set CURRENT_DIR=%CD%

REM Start Django development server in new window
echo Starting Django server...
start "Kinetix - Django Server" cmd /k "cd /d %CURRENT_DIR% && venv\Scripts\activate && python manage.py runserver > logs\server_out.log 2> logs\server_err.log"

REM Wait a moment for Django to start
timeout /t 2 /nobreak >nul

if "%SKIP_CELERY%"=="0" (
    REM Start Celery worker in new window
    echo Starting Celery worker...
    start "Kinetix - Celery Worker" cmd /k "cd /d %CURRENT_DIR% && venv\Scripts\activate && celery -A command_center worker -l info --pool=solo --logfile=logs\worker.log"
    
    REM Wait a moment
    timeout /t 2 /nobreak >nul
    
    REM Start Celery beat in new window
    echo Starting Celery beat...
    start "Kinetix - Celery Beat" cmd /k "cd /d %CURRENT_DIR% && venv\Scripts\activate && celery -A command_center beat -l info --logfile=logs\beat.log"
) else (
    echo [SKIPPED] Celery services (Redis not available)
)

echo.
echo ============================================================================
echo   Services Started!
echo ============================================================================
echo.
echo Django Server:  http://localhost:8000
echo Admin Panel:    http://localhost:8000/admin
echo API Endpoint:   http://localhost:8000/api/v1/
echo.
if "%SKIP_CELERY%"=="0" (
    echo Celery Worker: Running (background tasks enabled)
    echo Celery Beat:   Running (scheduled tasks enabled)
) else (
    echo Celery:        Not running (start Redis first)
)
echo.
echo ============================================================================
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul

REM Open browser
start http://localhost:8000

echo.
echo Browser opened. You can now use Kinetix!
echo.
echo To stop all services:
echo   1. Close all terminal windows
echo   2. Or press Ctrl+C in each window
echo.
echo ============================================================================
echo.
echo This window can be closed. Services are running in separate windows.
echo.
pause
