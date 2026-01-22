@echo off
REM ============================================================================
REM Kinetix - Stop Development Services
REM ============================================================================
REM This script stops all running Kinetix services
REM ============================================================================

echo.
echo ============================================================================
echo   Kinetix - Stopping Services
echo ============================================================================
echo.

echo Stopping Web Servers (Dev/Prod)...
taskkill /FI "WINDOWTITLE eq Kinetix - Django Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Kinetix - Production Web Server*" /T /F >nul 2>&1
taskkill /IM waitress-serve.exe /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] Web servers not running
) else (
    echo [OK] Web servers stopped
)

echo Stopping Celery worker...
taskkill /FI "WINDOWTITLE eq Kinetix - Celery Worker*" /T /F >nul 2>&1
taskkill /IM celery.exe /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] Celery worker not running
) else (
    echo [OK] Celery worker stopped
)

echo Stopping Celery beat...
taskkill /FI "WINDOWTITLE eq Kinetix - Celery Beat*" /T /F >nul 2>&1
if errorlevel 1 (
    echo [INFO] Celery beat not running
) else (
    echo [OK] Celery beat stopped
)

echo.
echo ============================================================================
echo   All Services Stopped
echo ============================================================================
echo.
echo Note: Redis server is not stopped by this script.
echo If you want to stop Redis, run: redis-cli shutdown
echo.
pause
