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

REM 0. Version Management
set VERSION_FILE=%~dp0..\agent\VERSION
if not exist "!VERSION_FILE!" echo 1.0.0.0 > "!VERSION_FILE!"
set /p CURRENT_VERSION=<"!VERSION_FILE!"

REM Ensure version has 4 parts for reliable incrementing
echo !CURRENT_VERSION! | findstr /r "^[0-9]*\.[0-9]*\.[0-9]*$" >nul
if !errorlevel! equ 0 set CURRENT_VERSION=!CURRENT_VERSION!.0

REM Split version into components
for /f "tokens=1-4 delims=." %%a in ("!CURRENT_VERSION!") do (
    set VERSION_MAJOR=%%a
    set VERSION_MINOR=%%b
    set VERSION_PATCH=%%c
    set VERSION_BUILD=%%d
)

if "!VERSION_BUILD!" == "" set VERSION_BUILD=0

REM Increment build number
set /a VERSION_BUILD+=1
set NEW_VERSION=!VERSION_MAJOR!.!VERSION_MINOR!.!VERSION_PATCH!.!VERSION_BUILD!

echo Current Version: !CURRENT_VERSION!
echo New Version:     !NEW_VERSION!

REM Update VERSION file
echo !NEW_VERSION! > "!VERSION_FILE!"

REM Update agent.ini
powershell -Command "(Get-Content '%~dp0..\agent\agent\agent.ini') -replace 'Version = .*', 'Version = !NEW_VERSION!' | Set-Content '%~dp0..\agent\agent\agent.ini'"

REM Update product.wxs
powershell -Command "(Get-Content '%~dp0..\agent\agent\installer\product.wxs') -replace 'Version=\"\d+\.\d+\.\d+\.\d+\"', 'Version=\"!NEW_VERSION!\"' | Set-Content '%~dp0..\agent\agent\installer\product.wxs'"

REM Update agent_config.py (Hardcoded version in binary)
powershell -Command "(Get-Content '%~dp0..\agent\agent\agent_config.py') -replace 'VERSION = \".*\"', 'VERSION = \"!NEW_VERSION!\"' | Set-Content '%~dp0..\agent\agent\agent_config.py'"

REM 1. Move to agent directory
cd /d "%~dp0..\agent\agent"

REM NEW: Ensure agent is not running so it doesn't lock the EXE
echo [0/3] Stopping existing agent processes...
taskkill /F /IM kinetix_agent.exe /T >nul 2>&1
net stop KinetixAgent >nul 2>&1

REM NEW: Recovery check for previous failed builds
if exist "..\dist\kinetix_agent_main.exe" (
    echo [FIX] Recovering binary from previous failed build...
    if not exist "..\dist\kinetix_agent" mkdir "..\dist\kinetix_agent"
    move /y "..\dist\kinetix_agent_main.exe" "..\dist\kinetix_agent\kinetix_agent.exe" >nul
)

REM 2. Build the Executable (cc_agent.exe)
echo [1/3] Building Agent Executable...
call ..\..\server-manager\agent_build.bat
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

echo Running Heat to harvest dependencies...
REM Copy the main EXE out temporarily so Heat doesn't harvest it (we handle it manually in product.wxs for the Service)
copy /y "..\dist\kinetix_agent\kinetix_agent.exe" "..\dist\kinetix_agent_main.exe" >nul

REM NEW: Try to remove it from the harvest folder (this is where it often locks)
del /f /q "..\dist\kinetix_agent\kinetix_agent.exe" >nul

"!WIX_PATH!heat.exe" dir "..\dist\kinetix_agent" -cg AgentFiles -dr INSTALLFOLDER -srd -sreg -sfrag -ke -ag -out generated_files.wxs

REM Give Windows/Antivirus a longer moment to release handles
timeout /t 5 /nobreak >nul

echo Restoring main executable...
REM Copy it back so product.wxs can find it at the expected path
copy /y "..\dist\kinetix_agent_main.exe" "..\dist\kinetix_agent\kinetix_agent.exe" >nul

REM Clean up the temp copy
if exist "..\dist\kinetix_agent\kinetix_agent.exe" del /f /q "..\dist\kinetix_agent_main.exe" >nul

echo Running Candle...
"!WIX_PATH!candle.exe" -ext WixUtilExtension product.wxs generated_files.wxs
if %errorlevel% neq 0 (
    echo [ERROR] WiX Compilation Candle failed.
    pause
    exit /b 1
)

echo Running Light...
REM Use -b to tell Light where to find the harvested files
"!WIX_PATH!light.exe" -ext WixUtilExtension -b "..\dist\kinetix_agent" product.wixobj generated_files.wixobj -o kinetix_agent.msi
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
echo %~dp0..\media\agent_drops\kinetix_agent_!NEW_VERSION!.msi
echo.
echo ============================================================================
echo.

move /y "kinetix_agent.msi" "..\..\..\media\agent_drops\kinetix_agent_!NEW_VERSION!.msi" >nul
echo A copy has been placed in the media\agent_drops folder for server auto-update: kinetix_agent_!NEW_VERSION!.msi
echo.

pause
