@echo off
setlocal
color 0A
title CodeHub Updater
cd /d "%~dp0"

echo [CodeHub] checking source tree...
echo [CodeHub] building single-file executable...

powershell.exe -ExecutionPolicy Bypass -File "%~dp0build.ps1"
if errorlevel 1 (
    echo [CodeHub] build failed.
    pause
    exit /b 1
)

echo [CodeHub] updating local copy...
copy /y "%~dp0build_out\dist\CodeHub.exe" "%~dp0CodeHub.exe" >nul
if errorlevel 1 (
    echo [CodeHub] failed to update local copy.
    pause
    exit /b 1
)

if exist "F:\Auto Hotkey\Python\Apps" (
    echo [CodeHub] updating Apps copy...
    copy /y "%~dp0build_out\dist\CodeHub.exe" "F:\Auto Hotkey\Python\Apps\CodeHub.exe" >nul
)

echo [CodeHub] starting updated app...
start "" "%~dp0CodeHub.exe"

echo [CodeHub] updated and closing...
timeout /t 1 /nobreak >nul
exit /b 0