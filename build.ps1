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
    --console `
    --name CodeHub `
    --icon $Icon `
    --add-data "$LogoAssets;assets" `
    --hidden-import pygame `
    --hidden-import sounddevice `
    --hidden-import mss `
    --hidden-import cv2 `
    --hidden-import numpy `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageTk `
    --distpath $Dist `
    --workpath $Work `
    --specpath $BuildRoot `
    (Join-Path $Root "code_hub.py")

Write-Host "One-file build complete: $(Join-Path $Dist 'CodeHub.exe')"
