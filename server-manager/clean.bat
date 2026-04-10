@echo off
REM ============================================================================
REM Kinetix - System Cleanup & Reset Tool
REM ============================================================================
REM Tiered cleanup for development and maintenance.
REM Safe Clean: Removes temp/cache files only.
REM Reset: Wipes database and media for a fresh start.
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0.."

echo.
echo ============================================================================
echo   Kinetix - System Maintenance
echo ============================================================================
echo.

REM 1. Create emergency backup of configuration
echo [1/7] Creating configuration backup...
if not exist "backups" mkdir backups
set TIMESTAMP=%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BCK_DIR=backups\pre_clean_%TIMESTAMP%
mkdir "%BCK_DIR%"

if exist ".env" copy ".env" "%BCK_DIR%\" >nul
if exist "keys" xcopy /E /I /H /Y "keys" "%BCK_DIR%\keys" >nul
if exist "db.sqlite3" copy "db.sqlite3" "%BCK_DIR%\" >nul

echo [OK] Configuration backed up to: %BCK_DIR%
echo.

REM 2. Select Clean Tier
echo Choose Cleanup Level:
echo  [1] Safe Clean (Default) - Removes cache, logs, temp files and venv.
echo  [2] Full Data Reset - EVERYTHING in level 1 + Wipes Database and Media.
echo  [3] Cancel
echo.

set /p TIER="Select option [1-3]: "

if "%TIER%"=="3" (
    echo [INFO] Cleanup cancelled.
    pause
    exit /b 0
)

if "%TIER%"=="2" (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo WARNING: You have selected FULL DATA RESET.
    echo This will delete all registered devices, app inventory, and update files.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    set /p CONFIRM="Type 'RESET' to confirm deep wipe: "
    if /i "!CONFIRM!" neq "RESET" (
        echo [INFO] Reset cancelled. Reverting to Safe Clean.
        set TIER=1
    )
) else (
    set TIER=1
)

echo.
echo [2/7] Stopping services...
REM Only kill windows starting with 'Kinetix - ' (services), avoiding the Manager or IDEs
taskkill /FI "WINDOWTITLE eq Kinetix - *" /T /F >nul 2>&1
taskkill /IM celery.exe /F >nul 2>&1
taskkill /IM waitress-serve.exe /F >nul 2>&1
echo [OK] Services stopped.

echo.
echo [3/7] Cleaning Virtual Environments...
if exist "venv" (
    echo Removing root venv...
    rd /s /q "venv" >nul 2>&1
)
if exist "agent\agent\venv" (
    echo Removing agent venv...
    rd /s /q "agent\agent\venv" >nul 2>&1
)
echo [OK] Virtual environments removed.

echo.
echo [4/7] Cleaning Python artifacts...
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    rd /s /q "%%d" >nul 2>&1
)
del /s /q *.pyc *.pyo >nul 2>&1
for /d /r . %%d in (.pytest_cache) do @if exist "%%d" (
    rd /s /q "%%d" >nul 2>&1
)
for /d /r . %%d in (.coverage) do @if exist "%%d" (
    del /q "%%d" >nul 2>&1
)
echo [OK] Python cache cleaned.

echo.
echo [5/7] Cleaning Build Artifacts & Logs...
if exist "staticfiles" rd /s /q "staticfiles" >nul 2>&1
if exist "build" rd /s /q "build" >nul 2>&1
if exist "dist" rd /s /q "dist" >nul 2>&1
if exist "agent\agent\build" rd /s /q "agent\agent\build" >nul 2>&1
if exist "agent\agent\dist" rd /s /q "agent\agent\dist" >nul 2>&1
if exist "logs" (
    del /q "logs\*.log" >nul 2>&1
)
del /q *.log >nul 2>&1
echo [OK] Artifacts and logs cleaned.

echo.
echo [6/7] Data Reset (if selected)...
if "%TIER%"=="2" (
    echo Wiping database...
    if exist "db.sqlite3" del /f /q "db.sqlite3"
    
    echo Wiping media updates...
    if exist "media\updates" (
        del /s /q "media\updates\*.*" >nul 2>&1
    )
    
    echo Wiping security keys...
    if exist "keys" rd /s /q "keys"
    if exist "cert.crt" del /f /q "cert.crt"
    if exist "cert.key" del /f /q "cert.key"
    
    echo Scrubbing sensitive keys from .env...
    if exist ".env" (
        powershell -Command "(Get-Content .env) -replace '^SECRET_KEY=.*', 'SECRET_KEY=' -replace '^ENCRYPTION_KEY=.*', 'ENCRYPTION_KEY=' | Set-Content .env"
    )

    echo Cleaning agent build artifacts and MSI files...
    if exist "agent\agent\build" rd /s /q "agent\agent\build"
    if exist "agent\agent\dist" rd /s /q "agent\agent\dist"
    if exist "agent\agent\venv" rd /s /q "agent\agent\venv"
    del /s /q *.msi >nul 2>&1
    
    echo Resetting agent version...
    if exist "agent\VERSION" echo 1.0.0.0 > "agent\VERSION"

    echo [OK] Database, keys, certificates, and sensitive configs wiped.
) else (
    echo [SKIP] Safe Clean: Database and Media preserved.
)

echo.
echo [7/7] Recreating Directory Structure...
if not exist "logs" mkdir logs
if not exist "keys" mkdir keys
if not exist "media\updates" mkdir media\updates
if not exist "backups" mkdir backups
echo [OK] Structure verified.

echo.
echo ============================================================================
echo   Cleanup Complete!
echo ============================================================================
echo.
echo Status Summary:
echo  - Configuration (.env, keys)  : PRESERVED (and backed up)
if "%TIER%"=="2" (
echo  - Application Data (DB, Media): WIPED
) else (
echo  - Application Data (DB, Media): PRESERVED
)
echo.
echo To restore your project environment:
echo   1. Run 'quickstart.bat'
echo.
echo ============================================================================

pause