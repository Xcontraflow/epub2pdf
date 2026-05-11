@echo off
echo ============================================
echo   EPUB to PDF Converter - Install
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

echo [1/2] Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo.
echo [2/2] Checking for browser...
echo   The program uses Microsoft Edge or Google Chrome (already on Windows 10/11).
echo   If neither is installed, run this to download Chromium (~400MB):
echo     playwright install chromium
echo.

if %errorlevel% neq 0 (
    echo [ERROR] Installation failed. Try: pip install -r requirements.txt
) else (
    echo [OK] Done! Run run.bat to start.
)
echo.
pause
