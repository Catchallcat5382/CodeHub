$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ((Split-Path -Leaf $Root) -eq ".codehub_tools") {
    $Root = Split-Path -Parent $Root
}
$OutDir = Join-Path $Root "release"
$Stage = Join-Path $OutDir "CodeHub"
$Zip = Join-Path $OutDir "CodeHub-release.zip"
Remove-Item -Path $Stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Copy-Item -Path (Join-Path $Root "CodeHub.exe") -Destination $Stage -Force
Copy-Item -Path (Join-Path $Root "requirements.txt") -Destination $Stage -Force
Copy-Item -Path (Join-Path $Root "README.txt") -Destination $Stage -Force
Copy-Item -Path (Join-Path $Root "_internal") -Destination (Join-Path $Stage "_internal") -Recurse -Force
Copy-Item -Path (Join-Path $Root ".codehub_runtime") -Destination (Join-Path $Stage ".codehub_runtime") -Recurse -Force
Copy-Item -Path (Join-Path $Root "assets") -Destination (Join-Path $Stage "assets") -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "exports") | Out-Null

Remove-Item -Path $Zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $Stage -DestinationPath $Zip -Force
Write-Host "Created $Zip"
