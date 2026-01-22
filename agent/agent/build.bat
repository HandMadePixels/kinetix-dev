@echo off
REM ============================================================================
REM Kinetix Agent - Build Script
REM ============================================================================

echo.
echo ============================================================================
echo   Kinetix Agent - Building Executable
echo ============================================================================
echo.

REM 1. Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM 2. Copy Public Key from Server
echo Copying public key for update verification...
if exist "..\..\keys\public_key.pem" (
    copy /y "..\..\keys\public_key.pem" "public_key.pem" >nul
) else (
    echo [WARNING] public_key.pem not found in ..\..\keys\
    echo Verification will fail unless you provide a key manually.
)

REM 3. Run PyInstaller
echo Freezing application with PyInstaller...
pyinstaller --clean agent.spec

if %errorlevel% equ 0 (
    echo [OK] Agent executable built successfully.
) else (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b %errorlevel%
)
