@echo off
echo ================================================
echo   EPUB2PDF - Build EXE
echo ================================================
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+ first.
    pause & exit /b 1
)

echo [1/4] Installing dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause & exit /b 1
)

echo [2/4] Cleaning old build...
if exist "dist\EPUB2PDF" rmdir /s /q "dist\EPUB2PDF"
if exist "build"         rmdir /s /q "build"
if exist "EPUB2PDF.spec" del /q "EPUB2PDF.spec"

echo [3/4] Building EXE (first time takes 1-3 min)...
pyinstaller --onedir --windowed --name "EPUB2PDF" --icon "icon.ico" --collect-data customtkinter --collect-all playwright --hidden-import ebooklib --hidden-import bs4 --hidden-import pypdf --hidden-import lxml --hidden-import PIL --noupx main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. See errors above.
    pause & exit /b 1
)

echo [4/4] Creating desktop shortcut...
set "EXE_PATH=%~dp0dist\EPUB2PDF\EPUB2PDF.exe"
set "WORK_DIR=%~dp0dist\EPUB2PDF"
set "ICON_PATH=%~dp0icon.ico"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\EPUB2PDF.lnk'); $sc.TargetPath = $env:EXE_PATH; $sc.WorkingDirectory = $env:WORK_DIR; $sc.IconLocation = $env:ICON_PATH; $sc.Description = 'EPUB to PDF Converter'; $sc.Save(); Write-Host 'Shortcut created.'"

echo.
echo ================================================
echo   Done!
echo   EXE:      dist\EPUB2PDF\EPUB2PDF.exe
echo   Shortcut: Desktop\EPUB2PDF.lnk
echo ================================================
echo.
pause
