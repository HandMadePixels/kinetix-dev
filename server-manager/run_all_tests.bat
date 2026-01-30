@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
 echo   Kinetix Automated Test Suite (v1.5.0 Hardened)
 echo ============================================================
 echo.

REM 1. Command Center API Tests
 echo [1/3] Running Command Center API tests...
venv\Scripts\python.exe manage.py test tests.test_kinetix_requirements
if %errorlevel% neq 0 (
    echo [ERROR] Command Center API tests failed!
    pause
    exit /b %errorlevel%
)
 echo [SUCCESS] Command Center API tests passed.
 echo.

REM 2. Agent Security Suite
 echo [2/3] Running Agent Security logic tests...
venv\Scripts\python.exe tests\agent_security_suite.py
if %errorlevel% neq 0 (
    echo [ERROR] Agent Security tests failed!
    pause
    exit /b %errorlevel%
)
 echo [SUCCESS] Agent Security tests passed.
 echo.

REM 3. Agent Collector Tests
 echo [3/4] Running Agent Collector tests...
venv\Scripts\python.exe tests\test_agent_collector.py
if %errorlevel% neq 0 (
    echo [ERROR] Agent Collector tests failed!
    pause
    exit /b %errorlevel%
)
 echo [SUCCESS] Agent Collector tests passed.
 echo.

REM 4. Agent Updater Logic Tests
 echo [4/4] Running Agent Updater logic tests...
venv\Scripts\python.exe tests\test_agent_updater_logic.py
if %errorlevel% neq 0 (
    echo [ERROR] Agent Updater tests failed!
    pause
    exit /b %errorlevel%
)
 echo [SUCCESS] Agent Updater tests passed.
 echo.

 echo ============================================================
 echo   ALL TESTS PASSED SUCCESSFULLY! 🚀
 echo ============================================================
pause
