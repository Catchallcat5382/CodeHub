$Out = Join-Path $PSScriptRoot "release"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item "$PSScriptRoot\CodeHub.exe" "$Out\CodeHub.exe" -Force
Copy-Item "$PSScriptRoot\assets" "$Out\assets" -Recurse -Force
