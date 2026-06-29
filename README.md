CodeHub
=======

Location requested:
F:\Auto Hotkey\Python\CodeHub

Run:
Best app launch:
1. Open "F:\Auto Hotkey\Python\CodeHub"
2. Run CodeHub.exe
3. Right-click CodeHub on the taskbar and pin it.

CodeHub.exe is the bootstrap app:
- It opens the command prompt style startup screen.
- It checks requirements.txt.
- On first launch, or when requirements.txt changes, it installs/updates packages.
- Then it launches the real GUI from the hidden .codehub_runtime folder.

Shortcut launch:
- Open CodeHub.lnk. It points to CodeHub.exe and uses the CodeHub icon.

Script/dev launch:
1. Open PowerShell.
2. cd "F:\Auto Hotkey\Python\CodeHub"
3. py -m pip install -r requirements.txt
4. py code_hub.py

Hacker console launch:
- Open "Launch CodeHub.bat".
- This keeps the command prompt bootstrap effect.

If py does not work, use python instead.

Main hotkeys:
- F1 starts recording in CodeHub and starts generated scripts.
- F2 stops recording in CodeHub and stops generated scripts.
- Numpad 5 exits generated scripts.
- Normal and advanced recordings preserve key press/release timing, so held keys replay as held keys.

What is included:
- code_hub.py: the app.
- requirements.txt: Python packages.
- assets\CodeHub Logo.png: custom app logo.
- assets\CodeHub Logo transparent.png: transparent app/taskbar icon version.
- data/settings.json: persistent settings.
- data/recordings.json: cached macro recordings.
- data/knowledge.json: editable helper knowledge.
- exports/: generated scripts appear here by default.

Recording flow:
1. Pick recording mode and default export type before recording.
2. Press F1 to start.
3. Press F2 to stop.
4. A save popup asks for the macro name and whether to export as Default, AutoHotkey v2, or Python.
5. CodeHub saves the recording to JSON and exports the script.

Workspace:
The Workspace tab lets you open, edit, save, save as, rename, and delete generated scripts.
Deleting files requires enabling delete permission in Tools > Permissions.

Tools:
The Tools tab has separate workspaces for assistant notes, Python/AHK conversion notes, OCR capture around your mouse, and permissions.

Watermark:
CodeHub itself does not show a watermark.
Every generated script uses a tiny, very transparent top-right watermark saying "Made by Cat".
Every exported script includes comments showing what to delete if you want the watermark removed.

Window behavior:
CodeHub uses a normal Windows app window, so it can be resized, minimized, restored from the taskbar, and shown with the app logo.

Auto refresh:
The app rescans exported scripts and JSON recordings in the background. If you delete a script outside CodeHub, the workspace list refreshes automatically.

Review:
The Review tab can load a saved macro, replay the event timeline visually, show pressed keys, speed, click/key counts, and saved review screenshots. It is not a full video recorder yet, but it captures lightweight screenshots during recording when enabled in Settings.

Settings:
Permissions moved to Settings and are saved in data\settings.json. You can also change UI font size, compact/comfortable density, export folder, and review screenshot capture.

GitHub/release packaging:
- Use .codehub_tools\Create Release Package.ps1 to create release\CodeHub-release.zip.
- The release package ships the executable/runtime, not the editable source script.
- This prevents casual source browsing, but no distributed desktop app can fully prevent reverse engineering.

OCR:
Python can read text it sees on screen through screenshots plus OCR. This is not the same as reading hidden game memory.
For OCR, install the requirements and install the Windows Tesseract OCR program. If Tesseract is not on PATH, pytesseract cannot read text.
Use OCR and automation only where the app/game rules allow it.
