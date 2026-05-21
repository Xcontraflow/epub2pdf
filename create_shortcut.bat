@echo off
set "EXE_PATH=%~dp0dist\EPUB2PDF\EPUB2PDF.exe"
set "WORK_DIR=%~dp0dist\EPUB2PDF"

if not exist "%EXE_PATH%" (
    echo [ERROR] EXE not found: %EXE_PATH%
    echo Run build_exe.bat first.
    pause & exit /b 1
)

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\EPUB2PDF.lnk'); $sc.TargetPath = $env:EXE_PATH; $sc.WorkingDirectory = $env:WORK_DIR; $sc.Description = 'EPUB to PDF Converter'; $sc.Save(); Write-Host 'Desktop shortcut created.'"
