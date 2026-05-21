@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   EPUB2PDF - Setup
echo ================================================
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+ first.
    pause & exit /b 1
)

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install Pillow --quiet
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause & exit /b 1
)

echo [2/3] Generating icon...
python make_icon.py
if %errorlevel% neq 0 (
    echo [ERROR] Icon generation failed.
    pause & exit /b 1
)

echo [3/3] Creating desktop shortcut...

rem Find pythonw.exe path (sibling of python.exe)
for /f "delims=" %%P in ('python -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))"') do set "PYTHONW=%%P"

if not exist "%PYTHONW%" (
    echo [ERROR] pythonw.exe not found at: %PYTHONW%
    pause & exit /b 1
)

set "PROJ_DIR=%~dp0"
set "ICON_PATH=%~dp0icon.ico"
set "MAIN_PY=%~dp0main.py"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\EPUB2PDF.lnk'); $sc.TargetPath = $env:PYTHONW; $sc.Arguments = '\"' + $env:MAIN_PY + '\"'; $sc.WorkingDirectory = $env:PROJ_DIR.TrimEnd('\\'); $sc.IconLocation = $env:ICON_PATH; $sc.Description = 'EPUB to PDF Converter'; $sc.WindowStyle = 1; $sc.Save(); Write-Host 'Shortcut created on Desktop.'"

if %errorlevel% neq 0 (
    echo [ERROR] Shortcut creation failed.
    pause & exit /b 1
)

echo.
echo ================================================
echo   Done!
echo   Desktop shortcut: EPUB2PDF
echo   Click it to launch (no console, no rebuild ever).
echo ================================================
echo.
pause
