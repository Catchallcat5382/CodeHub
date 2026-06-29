$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildRoot = Join-Path $Root "build_out"
$Dist = Join-Path $BuildRoot "dist"
$Work = Join-Path $BuildRoot "build"
$Icon = Join-Path $Root "assets\CodeHub Logo.ico"

python -m PyInstaller --noconfirm --clean --windowed --name CodeHubApp --icon $Icon --distpath $Dist --workpath $Work --specpath $BuildRoot (Join-Path $Root "code_hub.py")
python -m PyInstaller --noconfirm --clean --console --name CodeHub --icon $Icon --distpath $Dist --workpath $Work --specpath $BuildRoot (Join-Path $Root "codehub_launcher.py")

Write-Host "Build complete: $Dist"
