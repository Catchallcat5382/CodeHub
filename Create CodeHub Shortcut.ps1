$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ShortcutPath = Join-Path $Root "CodeHub.lnk"
$ExePath = Join-Path $Root "CodeHub.exe"
$IconPath = Join-Path $Root "assets\CodeHub Logo.ico"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Launch CodeHub"
$Shortcut.Save()
Write-Host "Created $ShortcutPath"
