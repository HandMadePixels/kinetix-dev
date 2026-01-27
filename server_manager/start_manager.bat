@echo off
cd /d "%~dp0.."
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run quickstart.bat first.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
python server_manager\manager_gui.py
