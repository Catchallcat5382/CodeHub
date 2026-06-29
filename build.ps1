$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildRoot = Join-Path $Root "build_out"
$Dist = Join-Path $BuildRoot "dist"
$Work = Join-Path $BuildRoot "build"
$Icon = Join-Path $Root "assets\CodeHub Logo.ico"
$LogoAssets = Join-Path $Root "assets"

if (Test-Path $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name CodeHub `
    --icon $Icon `
    --add-data "$LogoAssets;assets" `
    --distpath $Dist `
    --workpath $Work `
    --specpath $BuildRoot `
    (Join-Path $Root "code_hub.py")

Write-Host "One-file build complete: $(Join-Path $Dist 'CodeHub.exe')"
