@echo off
cd /d "%~dp0.."
if not exist "venv\Scripts\activate.bat" (
    echo [WARNING] Virtual environment not found. Launching manager with system Python...
    python server-manager\manager_gui.py
    exit /b %errorlevel%
)
call venv\Scripts\activate.bat
python server-manager\manager_gui.py
