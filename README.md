# CodeHub

CodeHub is a desktop macro and script workspace for recording input, exporting automation scripts, editing generated code, and building small utility UIs.

It is designed around a simple workflow: record actions, save them as reusable scripts, review or edit the output, and keep everything organized in one app.

## Features

- Record keyboard and mouse input with `F1` to start and `F2` to stop.
- Export recordings as AutoHotkey v2 or Python scripts.
- Exit CodeHub with `F9`.
- Exit generated scripts with `Numpad 5`.
- Save settings, recordings, assistant data, and workspace state with JSON.
- Browse, edit, rename, delete, and run scripts from the workspace.
- Use a visual Code Builder to generate starter AutoHotkey v2 or Python Tkinter UI code.
- Convert simple Python macro snippets to AutoHotkey v2 and AutoHotkey v2 snippets to Python.
- Preview assistant-generated edits as a diff before staging them.
- Undo assistant, converter, builder, or editor changes before saving.
- Review recordings with event stats, input timelines, optional screenshot frames, optional replay video, and optional audio WAV capture.
- Configure replay screenshot FPS up to 240, with 60 as the default.
- Use optional UI click/tab sounds and a loading sound from the `assets` folder.
- Hide or show local data paths from Settings.
- Check GitHub for updates from inside the app.
- Enable optional auto-update on startup.

## Generated Scripts

Generated scripts include:

- Clear comments explaining what the script does.
- `F1` start and `F2` stop behavior where applicable.
- `Numpad 5` exit behavior.
- A small transparent top-right watermark that says `Made by Cat`.
- Comments showing where to remove the watermark code if desired.

## Updates

CodeHub can check the public GitHub repository for a newer build. Manual update checks are available in Settings, and automatic update checks can be enabled there too.

The distributed executable is a single-file build. Because it contains an embedded Python runtime and required packages, first startup can take longer than a normal native app while the runtime is prepared.

Script edits are staged in the Workspace editor. Press Save to write them to disk, or choose Delete/Cancel when prompted if you try to leave with unsaved changes.

## Source Use

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run from source:

```powershell
python code_hub.py
```

Build a single-file executable:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\build.ps1
```

## Notes

CodeHub uses normal screen, keyboard, and mouse automation APIs. It does not read private game memory. Use automation only where it is allowed by the software or game you are using.
