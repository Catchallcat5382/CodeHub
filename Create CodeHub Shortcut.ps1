$Desktop = [Environment]::GetFolderPath("Desktop")
$Target = Join-Path $PSScriptRoot "Launch CodeHub.bat"
$Shortcut = Join-Path $Desktop "CodeHub.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut($Shortcut)
$Link.TargetPath = $Target
$Link.WorkingDirectory = $PSScriptRoot
$Link.Save()
