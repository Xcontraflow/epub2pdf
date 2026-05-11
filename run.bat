@echo off
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Startup failed. Please run install.bat first.
    pause
)
