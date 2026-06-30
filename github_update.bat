@echo off
setlocal EnableExtensions
color 0A
title CodeHub GitHub Updater
cd /d "%~dp0"

echo ==========================================================
echo                 CODEHUB GITHUB UPDATER
echo ==========================================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Git is not installed or not on PATH.
    pause
    exit /b 1
)

if not exist ".git" (
    echo [FAIL] This folder is not a Git repository.
    pause
    exit /b 1
)

echo [GITIGNORE] Writing ignore rules...

(
echo # Python
echo __pycache__/
echo *.pyc
echo *.py[cod]
echo.
echo # Runtime data
echo data/
echo exports/
echo .codehub_runtime/
echo .codehub_tools/
echo _internal/
echo.
echo # Build folders
echo build/
echo build_out/
echo *.spec
echo CodeHubApp.spec
echo.
echo # Logs, temp files, secrets
echo publish_log.txt
echo *.log
echo .env
echo CodeHub_apply_update.cmd
echo CodeHub_local_update.cmd
echo.
echo # Personal-only scripts
echo Github.bat
echo GitHub Update.bat
echo GitHub Downgrade.bat
echo Publish to GitHub.bat
echo downgrade.bat
echo.
echo # Windows junk
echo Thumbs.db
echo Desktop.ini
echo *.lnk
) > ".gitignore"

echo [CLEAN] Removing local-only files...

for %%F in (
    "README.txt"
    "CodeHubApp.spec"
    "GitHub Update.bat"
    "GitHub Downgrade.bat"
    "Github.bat"
    "Publish to GitHub.bat"
    "publish_log.txt"
    "CodeHub_apply_update.cmd"
    "CodeHub_local_update.cmd"
) do (
    del /f /q "%%~F" >nul 2>&1
)

for %%D in (
    ".codehub_tools"
    ".codehub_runtime"
    "_internal"
    "build"
    "data"
    "exports"
    "__pycache__"
) do (
    rmdir /s /q "%%~D" >nul 2>&1
)

git rm -r --cached .codehub_tools .codehub_runtime _internal build data exports __pycache__ README.txt CodeHubApp.spec "GitHub Update.bat" "GitHub Downgrade.bat" Github.bat "Publish to GitHub.bat" publish_log.txt CodeHub_apply_update.cmd CodeHub_local_update.cmd >nul 2>&1

if not exist "code_hub.py" (
    echo [FAIL] code_hub.py was not copied into repo.
    echo Check that your real file is named code_hub.py inside:
    echo F:\Auto Hotkey\Python\CodeHub
    pause
    exit /b 1
)

echo [VERSION] Updating build number...

for /f %%C in ('git rev-list --count HEAD 2^>nul') do set "COMMIT_COUNT=%%C"
if "%COMMIT_COUNT%"=="" set "COMMIT_COUNT=0"
set /a NEXT_BUILD=COMMIT_COUNT+1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p='code_hub.py';" ^
  "$t=Get-Content $p -Raw;" ^
  "if ($t -match 'BUILD_NUMBER\s*=\s*\d+') {" ^
  "  $t=$t -replace 'BUILD_NUMBER\s*=\s*\d+', 'BUILD_NUMBER = %NEXT_BUILD%';" ^
  "} else {" ^
  "  $t='BUILD_NUMBER = %NEXT_BUILD%' + [Environment]::NewLine + $t;" ^
  "}" ^
  "Set-Content $p $t -Encoding UTF8;"

echo [VERSION] Build number: %NEXT_BUILD%

echo [GIT] Staging files...
git add -A

echo.
echo [GIT] Pending changes:
git status --short
echo.

git diff --cached --quiet
if not errorlevel 1 (
    echo [DONE] Nothing to commit.
    pause
    exit /b 0
)

set /p MSG=Commit message: 
if "%MSG%"=="" set "MSG=CodeHub update"

echo [GIT] Committing...
git commit -m "%MSG%"
if errorlevel 1 (
    echo [FAIL] Commit failed.
    pause
    exit /b 1
)

echo [GIT] Pushing to origin main...
git push origin main
if errorlevel 1 (
    echo [FAIL] Push failed.
    pause
    exit /b 1
)

echo.
echo [DONE] GitHub updated successfully.
pause
exit /b 0