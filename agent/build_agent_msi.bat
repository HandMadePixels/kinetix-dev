@echo off
REM ============================================================================
REM Kinetix Agent - One-Click MSI Builder
REM ============================================================================
REM This script automates both the PyInstaller freeze and the WiX MSI creation.
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo   Kinetix Agent - Building MSI Installer
echo ============================================================================
echo.

REM 1. Move to agent directory
cd /d "%~dp0agent"

REM 2. Build the Executable (cc_agent.exe)
echo [1/3] Building Agent Executable...
call build.bat
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

REM 3. Locating WiX Toolset
echo [2/3] Locating WiX Toolset...
set "WIX_PATH=NOTFOUND"

REM Check if in PATH
where candle.exe >nul 2>&1
if %errorlevel% equ 0 (
    set WIX_PATH=
) else (
    REM Check common install locations for v3.x
    for /d %%d in ("C:\Program Files (x86)\WiX Toolset v3*") do (
        if exist "%%d\bin\candle.exe" set "WIX_PATH=%%d\bin\"
    )
    if "!WIX_PATH!" == "NOTFOUND" (
        for /d %%d in ("C:\Program Files\WiX Toolset v3*") do (
            if exist "%%d\bin\candle.exe" set "WIX_PATH=%%d\bin\"
        )
    )
)

if "!WIX_PATH!" == "NOTFOUND" (
    echo [ERROR] WiX Toolset v3.x not found!
    echo Please install it from https://wixtoolset.org/releases/v3.14/
    echo or ensure 'candle.exe' is in your system PATH.
    pause
    exit /b 1
)

REM 4. Building the MSI
echo [3/3] Compiling MSI with WiX...
cd installer

echo Running Candle...
"!WIX_PATH!candle.exe" product.wxs -o product.wixobj
if %errorlevel% neq 0 (
    echo [ERROR] WiX Compilation Candle failed.
    pause
    exit /b 1
)

echo Running Light...
"!WIX_PATH!light.exe" product.wixobj -o kinetix_agent.msi
if %errorlevel% neq 0 (
    echo [ERROR] WiX Linking Light failed.
    pause
    exit /b 1
)

REM 5. Cleanup and Finish
echo.
echo ============================================================================
echo   MSI Build Successful! 🚀
echo ============================================================================
echo.
echo Your installer is ready:
echo F:\EndpointSoln\agent\installer\kinetix_agent.msi
echo.
echo ============================================================================
echo.

move /y "kinetix_agent.msi" "..\kinetix_agent.msi" >nul
echo A copy has been placed in the agent/ root folder for convenience.
echo.

pause
