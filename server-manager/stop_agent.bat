@echo off
cd /d "%~dp0.."
:: Check for administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrator privileges confirmed.
) else (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%0' -Verb RunAs"
    exit /b
)

echo Stopping Kinetix Agent service (KinetixAgent)...
net stop KinetixAgent
if %errorLevel% == 0 (
    echo Agent stopped successfully.
) else (
    echo Failed to stop agent or agent was not running.
)
pause
