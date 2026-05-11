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

echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause & exit /b 1
)

echo [2/3] Cleaning old build...
if exist "dist\EPUB2PDF" rmdir /s /q "dist\EPUB2PDF"
if exist "build"         rmdir /s /q "build"
if exist "EPUB2PDF.spec" del /q "EPUB2PDF.spec"

echo [3/3] Building EXE (first time takes 1-3 min)...
pyinstaller --onedir --windowed --name "EPUB2PDF" --collect-data customtkinter --collect-all playwright --hidden-import ebooklib --hidden-import bs4 --hidden-import pypdf --hidden-import lxml --hidden-import PIL --noupx main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. See errors above.
    pause & exit /b 1
)

echo.
echo ================================================
echo   Done!
echo   EXE: dist\EPUB2PDF\EPUB2PDF.exe
echo   Copy the entire dist\EPUB2PDF\ folder anywhere.
echo   Requires Edge or Chrome installed on the system.
echo ================================================
echo.
pause
