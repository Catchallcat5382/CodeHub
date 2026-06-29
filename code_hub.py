import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import difflib
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, HORIZONTAL, LEFT, RIGHT, X, BooleanVar, DoubleVar, PhotoImage, StringVar, Tk, Toplevel
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk

from pynput import keyboard, mouse
from pynput.keyboard import Key

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


APP_NAME = "CodeHub"
MAKER_NAME = "Macro Maker"
if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
    if APP_ROOT.name == ".codehub_runtime":
        APP_ROOT = APP_ROOT.parent
else:
    APP_ROOT = Path(__file__).resolve().parent
ASSET_DIR = APP_ROOT / "assets"
DATA_DIR = APP_ROOT / "data"
EXPORT_DIR = APP_ROOT / "exports"
SETTINGS_PATH = DATA_DIR / "settings.json"
RECORDINGS_PATH = DATA_DIR / "recordings.json"
KNOWLEDGE_PATH = DATA_DIR / "knowledge.json"


DEFAULT_SETTINGS = {
    "export_dir": str(EXPORT_DIR),
    "default_script_name": "MyMacro",
    "watermark_corner": "top_right",
    "watermark_opacity": 0.46,
    "ocr_region": {"x": 0, "y": 0, "width": 420, "height": 160},
    "ai_can_edit": False,
    "ai_can_delete": False,
    "ai_can_run": False,
    "ui_font_size": 9,
    "ui_density": "compact",
    "record_screenshots": True,
    "review_capture_interval_ms": 2000,
}


DEFAULT_KNOWLEDGE = {
    "python": [
        "Python can control keyboard and mouse through pynput.",
        "Python can read visible screen text through screenshots plus OCR.",
        "Python OCR reads pixels on screen; it does not read private game memory.",
        "Use JSON files for settings, saved recordings, script metadata, and reusable presets.",
    ],
    "autohotkey": [
        "AutoHotkey v2 scripts should start with #Requires AutoHotkey v2.0.",
        "Use F1 to start, F2 to stop, and Numpad5::ExitApp to quit generated scripts.",
        "A transparent watermark can be made with Gui('+AlwaysOnTop -Caption +ToolWindow +E0x20').",
        "Use a running flag so F2 can stop long loops safely.",
    ],
    "ocr": [
        "OCR works best on a small cropped region with high contrast text.",
        "If a game blocks screenshots, OCR may return blank or wrong text.",
        "Check the rules of any app or game before using automation.",
    ],
}


def ensure_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        write_json(SETTINGS_PATH, DEFAULT_SETTINGS)
    if not RECORDINGS_PATH.exists():
        write_json(RECORDINGS_PATH, {"recordings": []})
    if not KNOWLEDGE_PATH.exists():
        write_json(KNOWLEDGE_PATH, DEFAULT_KNOWLEDGE)


def set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cat.CodeHub.MacroMaker")
    except Exception:
        pass


def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fallback


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


def safe_name(text):
    text = (text or "macro").strip()
    return re.sub(r'[\\/:*?"<>|]+', "_", text) or "macro"


def resolve_app_path(value):
    path = Path(value)
    if not path.is_absolute():
        path = APP_ROOT / path
    return path


def format_size(num_bytes):
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024


def python_command():
    for command in (["py", "-3"], ["py"], ["python"], ["python3"]):
        try:
            result = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return command
        except Exception:
            continue
    return [sys.executable]


def pythonw_command():
    candidates = []
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        candidates.append([str(executable.with_name("pythonw.exe"))])
    for name in ("pythonw", "pythonw.exe"):
        found = shutil.which(name)
        if found:
            candidates.append([found])
    for command in candidates:
        try:
            result = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=5, creationflags=hidden_process_flags())
            if result.returncode == 0:
                return command
        except Exception:
            continue
    return python_command()


def hidden_process_flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def find_ahk_exe():
    candidates = []
    for name in ("AutoHotkey64.exe", "AutoHotkey.exe", "AutoHotkeyU64.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend([
        Path("C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"),
        Path("C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"),
        Path("C:/Program Files/AutoHotkey/AutoHotkey.exe"),
        Path("C:/Program Files/AutoHotkey/AutoHotkey64.exe"),
        Path("C:/Program Files (x86)/AutoHotkey/AutoHotkey.exe"),
    ])
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def ahk_text(text):
    return str(text).replace("`", "``").replace('"', '`"')


def to_ahk_key(key_text):
    mapping = {
        "Key.space": "Space",
        "Key.enter": "Enter",
        "Key.tab": "Tab",
        "Key.backspace": "Backspace",
        "Key.delete": "Delete",
        "Key.esc": "Escape",
        "Key.escape": "Escape",
        "Key.up": "Up",
        "Key.down": "Down",
        "Key.left": "Left",
        "Key.right": "Right",
        "Key.home": "Home",
        "Key.end": "End",
        "Key.page_up": "PgUp",
        "Key.page_down": "PgDn",
        "Key.shift": "Shift",
        "Key.shift_l": "LShift",
        "Key.shift_r": "RShift",
        "Key.ctrl": "Ctrl",
        "Key.ctrl_l": "LCtrl",
        "Key.ctrl_r": "RCtrl",
        "Key.alt": "Alt",
        "Key.alt_l": "LAlt",
        "Key.alt_r": "RAlt",
        "Key.cmd": "LWin",
        "Key.cmd_l": "LWin",
        "Key.cmd_r": "RWin",
        "Key.caps_lock": "CapsLock",
        "Key.num_lock": "NumLock",
        "Key.insert": "Insert",
        "Key.print_screen": "PrintScreen",
        "Key.f1": "F1",
        "Key.f2": "F2",
        "Key.f3": "F3",
        "Key.f4": "F4",
        "Key.f5": "F5",
        "Key.f6": "F6",
        "Key.f7": "F7",
        "Key.f8": "F8",
        "Key.f9": "F9",
        "Key.f10": "F10",
        "Key.f11": "F11",
        "Key.f12": "F12",
    }
    if key_text.startswith("'") and key_text.endswith("'") and len(key_text) >= 3:
        return key_text[1:-1]
    return mapping.get(key_text, "")


def generate_ahk(events, mode, script_name):
    name = safe_name(script_name)
    load_ms = max(450, min(2400, 420 + len(events) * 7))
    lines = [
        "#Requires AutoHotkey v2.0",
        "#SingleInstance Force",
        "; Generated by CodeHub / Macro Maker.",
        f"; Script: {name}",
        f"; Mode: {mode}",
        f"; Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "; Hotkeys: F1 starts playback, F2 stops playback, Numpad 5 exits.",
        "; Loader: delete ShowCodeHubLoader() calls plus the ShowCodeHubLoader function if you do not want the loading popup.",
        "; Watermark: delete CreateWatermark() and the CreateWatermark function if you do not want it.",
        "; Timing: playback uses absolute recorded timestamps to avoid drift in rhythm/game macros.",
        "; Editing notes: change WaitUntil(startTick + N) timings and Click/MouseMove coordinates.",
        "",
        "global running := false",
        f'global macroName := "{ahk_text(name)}"',
        "SetKeyDelay(-1, -1)",
        "SetMouseDelay(-1)",
        "SetWinDelay(-1)",
        "SetControlDelay(-1)",
        "CreateWatermark()",
        f"ShowCodeHubLoader({load_ms}, 'Loading ' macroName)",
        "",
        "F1::",
        "{",
        "    global running",
        "    running := true",
        '    ToolTip("Started " macroName, 16, 16)',
        "    SetTimer(() => ToolTip(), -900)",
        f"    ShowCodeHubLoader({load_ms}, 'Preparing playback')",
        "    PlayMacro()",
        "}",
        "",
        "F2::",
        "{",
        "    global running",
        "    running := false",
        '    ToolTip("Stopped " macroName, 16, 16)',
        "    SetTimer(() => ToolTip(), -900)",
        "}",
        "",
        "Numpad5::ExitApp",
        "",
        "PlayMacro()",
        "{",
        "    global running",
        "    startTick := A_TickCount",
    ]
    for event in events:
        event_time = float(event.get("time", 0))
        target_ms = int(max(0, event_time) * 1000)
        lines.extend(["    if !running", "        return"])
        if target_ms > 0:
            lines.append(f"    WaitUntil(startTick + {target_ms})")
        kind = event.get("type")
        if kind == "mouse_move" and mode == "advanced":
            lines.append(f"    MouseMove({int(event.get('x', 0))}, {int(event.get('y', 0))}, 0)")
        elif kind == "mouse_click":
            x = int(event.get("x", 0))
            y = int(event.get("y", 0))
            button = event.get("button", "left")
            pressed = event.get("pressed", True)
            prefix = {"left": "", "right": "Right ", "middle": "Middle "}.get(button, "")
            if mode == "minimal":
                if pressed:
                    lines.append(f"    Click({x}, {y})" if not prefix else f'    Click("{prefix}{x}, {y}")')
            else:
                action = "Down" if pressed else "Up"
                lines.append(f'    Click("{prefix}{action}", {x}, {y})')
        elif kind == "mouse_scroll" and mode != "minimal":
            wheel = "WheelUp" if int(event.get("dy", 0)) > 0 else "WheelDown"
            lines.append(f'    Send("{{{wheel}}}")')
        elif kind == "key_char" and mode == "minimal":
            char = str(event.get("char", "")).replace("{", "{{}").replace("}", "{}}").replace('"', '\\"')
            lines.append(f'    Send("{char}")')
        elif kind in ("key_press", "key_release"):
            key = to_ahk_key(str(event.get("key", "")))
            if key and not (mode == "minimal" and kind == "key_release"):
                direction = " down" if kind == "key_press" else " up"
                lines.append(f'    Send("{{{key}{direction}}}")')
    lines.extend([
        "    running := false",
        "}",
        "",
        "WaitUntil(targetTick)",
        "{",
        "    global running",
        "    while running && A_TickCount < targetTick",
        "    {",
        "        remaining := targetTick - A_TickCount",
        "        Sleep(remaining > 3 ? 1 : 0)",
        "    }",
        "}",
        "",
        "ShowCodeHubLoader(durationMs := 900, title := 'Loading macro')",
        "{",
        "    ; This is the removable CodeHub loading popup. Delete this function and its calls to remove it.",
        "    loader := Gui('+AlwaysOnTop -Caption +ToolWindow')",
        "    loader.BackColor := '081019'",
        "    loader.MarginX := 18",
        "    loader.MarginY := 14",
        "    loader.SetFont('s10 cEAF6FF', 'Segoe UI')",
        "    loader.AddText('w300 Center', title)",
        "    loader.SetFont('s8 c8FD9FF', 'Segoe UI')",
        "    status := loader.AddText('w300 Center y+6', 'CodeHub macro loader')",
        "    barBg := loader.AddProgress('w300 h10 y+10 Background182434 c176BFF Range0-100', 0)",
        "    x := (A_ScreenWidth - 336) // 2",
        "    y := (A_ScreenHeight - 118) // 2",
        "    loader.Show('NoActivate x' x ' y' y ' w336 h118')",
        "    steps := 28",
        "    delay := Max(8, Floor(durationMs / steps))",
        "    Loop steps",
        "    {",
        "        barBg.Value := Floor((A_Index / steps) * 100)",
        "        status.Text := 'Indexing input timing... ' barBg.Value '%'",
        "        Sleep(delay)",
        "    }",
        "    status.Text := 'Loaded, closing in 1 second'",
        "    barBg.Value := 100",
        "    Sleep(1000)",
        "    loader.Destroy()",
        "}",
        "",
        "CreateWatermark()",
        "{",
        "    ; Top-right is the default because it usually avoids taskbars and common left-side menus.",
        "    ; Remove this whole function plus the CreateWatermark() call above to delete the watermark.",
        "    wm := Gui('+AlwaysOnTop -Caption +ToolWindow +E0x20')",
        "    wm.BackColor := '101820'",
        "    wm.MarginX := 8",
        "    wm.MarginY := 4",
        "    wm.SetFont('s8 cD6DEE8', 'Segoe UI')",
        '    wm.AddText("w150 Center", "Made by Cat")',
        "    WinSetTransparent(62, wm.Hwnd)",
        "    x := A_ScreenWidth - 174",
        "    y := 4",
        "    wm.Show('NoActivate x' x ' y' y ' w168 h26')",
        "}",
        "",
    ])
    return "\n".join(lines)


def generate_python(events, mode, script_name):
    name = safe_name(script_name)
    payload = json.dumps(events, indent=2)
    return f'''"""
Generated by CodeHub / Macro Maker.
Script: {name}
Hotkeys: F1 starts playback, F2 stops playback, Numpad 5 exits.
Watermark: remove the Watermark class and the Watermark().show() line if you do not want it.
Editing notes: change event "time" values for timing and x/y values for click positions.
"""
import json
import os
import threading
import time
import tkinter as tk
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Button, Controller as MouseController

SCRIPT_NAME = {name!r}
MODE = {mode!r}
EVENTS = json.loads({payload!r})
running = False
mouse = MouseController()
keys = KeyboardController()


def hide_console_if_present():
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


class Watermark:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.46)
        label = tk.Label(
            self.root,
            text="Made by Cat",
            bg="#101820",
            fg="#d6dee8",
            font=("Segoe UI", 7),
            padx=6,
            pady=2,
        )
        label.pack()
        self.root.update_idletasks()
        self.root.attributes("-alpha", 0.24)
        x = self.root.winfo_screenwidth() - self.root.winfo_width() - 6
        self.root.geometry(f"+{{x}}+4")

    def show(self):
        threading.Thread(target=self.root.mainloop, daemon=True).start()


def key_from_text(text):
    table = {{
        "Key.space": Key.space, "Key.enter": Key.enter, "Key.tab": Key.tab,
        "Key.backspace": Key.backspace, "Key.delete": Key.delete, "Key.esc": Key.esc,
        "Key.escape": Key.esc, "Key.up": Key.up, "Key.down": Key.down,
        "Key.left": Key.left, "Key.right": Key.right,
    }}
    if text in table:
        return table[text]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    return None


def play_macro():
    global running
    start = time.perf_counter()
    print(f"[Macro Maker] Playing {{SCRIPT_NAME}}. F2 stops; Numpad 5 exits.")
    for event in EVENTS:
        if not running:
            print("[Macro Maker] Stopped.")
            return
        event_time = float(event.get("time", 0))
        while running:
            remaining = (start + event_time) - time.perf_counter()
            if remaining <= 0:
                break
            time.sleep(0.001 if remaining > 0.003 else 0)
        kind = event.get("type")
        if kind == "mouse_move" and MODE == "advanced":
            mouse.position = (event.get("x", 0), event.get("y", 0))
        elif kind == "mouse_click":
            button = getattr(Button, event.get("button", "left"), Button.left)
            mouse.position = (event.get("x", 0), event.get("y", 0))
            if event.get("pressed", True):
                mouse.press(button)
            else:
                mouse.release(button)
        elif kind == "mouse_scroll":
            mouse.scroll(event.get("dx", 0), event.get("dy", 0))
        elif kind == "key_char" and MODE == "minimal":
            keys.type(event.get("char", ""))
        elif kind in ("key_press", "key_release"):
            key = key_from_text(str(event.get("key", "")))
            if key:
                if kind == "key_press":
                    keys.press(key)
                else:
                    keys.release(key)
    running = False
    print("[Macro Maker] Finished.")


def start_playback():
    global running
    if running:
        return
    running = True
    threading.Thread(target=play_macro, daemon=True).start()


def stop_playback():
    global running
    running = False


def on_press(key):
    if key == Key.f1:
        start_playback()
    elif key == Key.f2:
        stop_playback()
    elif getattr(key, "vk", None) == 101:
        print("[Macro Maker] Numpad 5 exit.")
        stop_playback()
        return False


if __name__ == "__main__":
    hide_console_if_present()
    print("F1 start | F2 stop | Numpad 5 exit")
    Watermark().show()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
'''


def event_line(event):
    t = float(event.get("time", 0))
    kind = event.get("type", "")
    if kind == "mouse_click":
        state = "down" if event.get("pressed") else "up"
        return f"[{t:06.2f}] click {state} {event.get('button')} @ {event.get('x')},{event.get('y')}"
    if kind == "mouse_move":
        return f"[{t:06.2f}] move @ {event.get('x')},{event.get('y')}"
    if kind == "mouse_scroll":
        return f"[{t:06.2f}] scroll dx={event.get('dx')} dy={event.get('dy')}"
    if kind == "key_char":
        return f"[{t:06.2f}] type {event.get('char')!r}"
    return f"[{t:06.2f}] {kind} {event.get('key', '')}"


class Recorder:
    def __init__(self, add_event):
        self.add_event = add_event
        self.events = []
        self.mode = "normal"
        self.recording = False
        self.start_time = 0.0
        self.lock = threading.Lock()
        self.mouse_listener = None
        self.keyboard_listener = None

    def now(self):
        return time.perf_counter() - self.start_time

    def start(self, mode):
        self.mode = mode
        self.events = []
        self.recording = True
        self.start_time = time.perf_counter()
        self.mouse_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self):
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        with self.lock:
            return list(self.events)

    def save(self, event):
        with self.lock:
            self.events.append(event)
        self.add_event(event)

    def on_move(self, x, y):
        if self.recording and self.mode == "advanced":
            self.save({"type": "mouse_move", "x": x, "y": y, "time": self.now()})

    def on_click(self, x, y, button, pressed):
        if self.recording:
            self.save({
                "type": "mouse_click",
                "x": x,
                "y": y,
                "button": str(button).replace("Button.", "").lower(),
                "pressed": pressed,
                "time": self.now(),
            })

    def on_scroll(self, x, y, dx, dy):
        if self.recording:
            self.save({"type": "mouse_scroll", "x": x, "y": y, "dx": dx, "dy": dy, "time": self.now()})

    def on_press(self, key):
        if not self.recording or key in (Key.f1, Key.f2):
            return
        if self.mode == "minimal" and hasattr(key, "char") and key.char:
            self.save({"type": "key_char", "char": key.char, "key": str(key), "time": self.now()})
        else:
            self.save({"type": "key_press", "key": str(key), "time": self.now()})

    def on_release(self, key):
        if self.recording and key not in (Key.f1, Key.f2):
            self.save({"type": "key_release", "key": str(key), "time": self.now()})


class SaveRecordingDialog:
    def __init__(self, parent, default_name, default_export):
        self.result = None
        self.window = Toplevel(parent)
        self.window.title("Save Recording")
        self.window.configure(bg="#0b1118")
        self.window.transient(parent)
        self.window.grab_set()
        self.window.resizable(False, False)
        self.name_var = StringVar(value=default_name)
        self.export_var = StringVar(value="Default")

        panel = ttk.Frame(self.window, padding=20, style="Panel.TFrame")
        panel.pack(fill=BOTH, expand=True)
        ttk.Label(panel, text="Save this macro", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(panel, text=f"Default export is currently {default_export}.", style="Muted.TLabel").pack(anchor="w", pady=(2, 14))
        ttk.Label(panel, text="Macro name").pack(anchor="w")
        name_entry = ttk.Entry(panel, textvariable=self.name_var, width=42)
        name_entry.pack(fill=X, pady=(4, 12))
        ttk.Label(panel, text="Create script as").pack(anchor="w")
        export_box = ttk.Combobox(panel, textvariable=self.export_var, values=["Default", "AutoHotkey v2", "Python"], state="readonly")
        export_box.pack(fill=X, pady=(4, 18))
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill=X)
        ttk.Button(row, text="Cancel", command=self.cancel).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(row, text="SAVE MACRO", command=self.accept).pack(side=RIGHT)
        self.window.bind("<Return>", lambda _event: self.accept())
        self.window.bind("<Escape>", lambda _event: self.cancel())
        name_entry.focus_set()
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 240
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 145
        self.window.geometry(f"480x290+{max(0, x)}+{max(0, y)}")
        self.window.wait_window()

    def accept(self):
        name = safe_name(self.name_var.get())
        if not name:
            messagebox.showerror(APP_NAME, "Give the macro a name.")
            return
        self.result = {"name": name, "export_kind": self.export_var.get()}
        self.window.destroy()

    def cancel(self):
        self.window.destroy()


class CodeHubApp:
    def __init__(self):
        ensure_files()
        self.settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        self.recordings = read_json(RECORDINGS_PATH, {"recordings": []})
        self.knowledge = read_json(KNOWLEDGE_PATH, DEFAULT_KNOWLEDGE)
        set_windows_app_id()
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1040x680")
        self.root.minsize(820, 520)
        self.root.resizable(True, True)
        self.root.configure(bg="#0b1118")
        self.logo_path = ASSET_DIR / "CodeHub Logo transparent.png"
        self.icon_path = ASSET_DIR / "CodeHub Logo.ico"
        if not self.logo_path.exists():
            self.logo_path = ASSET_DIR / "CodeHub Logo.png"
        self.logo_image = None
        self.logo_small = None
        if self.logo_path.exists():
            try:
                self.logo_image = PhotoImage(file=str(self.logo_path))
                self.logo_small = self.logo_image.subsample(26, 26)
                self.root.iconphoto(True, self.logo_image)
                if self.icon_path.exists():
                    self.root.iconbitmap(str(self.icon_path))
            except Exception:
                self.logo_image = None
                self.logo_small = None
        self.is_recording = False
        self.current_editor_file = None
        self.recorder = Recorder(self.on_event)
        self.fullscreen = BooleanVar(value=False)
        self.mode = StringVar(value="normal")
        self.default_export_kind = StringVar(value=self.settings.get("default_export_kind", "AutoHotkey v2"))
        self.export_dir_var = StringVar(value=self.settings.get("export_dir", str(EXPORT_DIR)))
        self.status = StringVar(value="Idle")
        self.ai_can_edit = BooleanVar(value=bool(self.settings.get("ai_can_edit", False)))
        self.ai_can_delete = BooleanVar(value=bool(self.settings.get("ai_can_delete", False)))
        self.ai_can_run = BooleanVar(value=bool(self.settings.get("ai_can_run", False)))
        self.ui_font_size = StringVar(value=str(self.settings.get("ui_font_size", 9)))
        self.ui_density = StringVar(value=self.settings.get("ui_density", "compact"))
        self.record_screenshots = BooleanVar(value=bool(self.settings.get("record_screenshots", True)))
        self._last_file_snapshot = set()
        self._last_recordings_signature = ""
        self._last_recordings_mtime = None
        self.macro_locked = False
        self.macro_process = None
        self.macro_lock_kind = "process"
        self.external_macro_pids = set()
        self.external_macro_paths = set()
        self._last_process_scan = 0.0
        self._process_scan_running = False
        self.lock_window = None
        self.lock_overlay = None
        self.position_logging = False
        self.position_log_events = []
        self.position_listener = None
        self.review_shot_paths = []
        self.review_shot_index = 0
        self.review_photo = None
        self.review_playing = False
        self.review_paused = False
        self.review_play_index = 0
        self.review_speed = DoubleVar(value=1.0)
        self.ai_pending_path = None
        self.ai_pending_text = ""
        self.ai_undo_stack = []
        self.configure_style()
        self.build()
        self.start_hotkeys()
        self.start_auto_refresh()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        base_font_size = int(self.settings.get("ui_font_size", 9))
        button_pad = (8, 4) if self.settings.get("ui_density", "compact") == "compact" else (11, 7)
        tab_pad = (11, 5) if self.settings.get("ui_density", "compact") == "compact" else (15, 8)
        style.configure(".", background="#080d14", foreground="#edf6ff", fieldbackground="#101a27", font=("Segoe UI", base_font_size))
        style.configure("TFrame", background="#080d14")
        style.configure("Panel.TFrame", background="#101a27", relief="flat")
        style.configure("Lock.TFrame", background="#05070c", relief="flat")
        style.configure("LockPanel.TFrame", background="#101a27", relief="flat")
        style.configure("TLabel", background="#080d14", foreground="#edf6ff")
        style.configure("Panel.TLabel", background="#101a27", foreground="#edf6ff")
        style.configure("LockPanel.TLabel", background="#101a27", foreground="#edf6ff")
        style.configure("Muted.TLabel", background="#080d14", foreground="#8fa0b7")
        style.configure("PanelMuted.TLabel", background="#101a27", foreground="#8fa0b7")
        style.configure("LockMuted.TLabel", background="#101a27", foreground="#8fa0b7")
        style.configure("TButton", background="#176bff", foreground="#ffffff", borderwidth=0, padding=button_pad, font=("Segoe UI", base_font_size, "bold"))
        style.map("TButton", background=[("active", "#28a9ff"), ("disabled", "#253244")])
        style.configure("Ghost.TButton", background="#142033", foreground="#c6d8ed", padding=(8, 5))
        style.map("Ghost.TButton", background=[("active", "#1d2c44")])
        style.configure("TCombobox", foreground="#050a12", fieldbackground="#dceeff", background="#dceeff", arrowcolor="#050a12", padding=(6, 3))
        style.map("TCombobox", fieldbackground=[("readonly", "#dceeff")], foreground=[("readonly", "#050a12")], selectbackground=[("readonly", "#dceeff")], selectforeground=[("readonly", "#050a12")])
        style.configure("TNotebook", background="#080d14", borderwidth=0)
        style.configure("TNotebook.Tab", background="#101a27", foreground="#95a9c0", padding=tab_pad, font=("Segoe UI", base_font_size, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#13243a")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview", background="#081019", fieldbackground="#081019", foreground="#d9e7f5", rowheight=23, borderwidth=0)
        style.configure("Treeview.Heading", background="#101a27", foreground="#8fd9ff", borderwidth=0, font=("Segoe UI", 9, "bold"))

    def build(self):
        outer = ttk.Frame(self.root, padding=(10, 8, 10, 10))
        outer.pack(fill=BOTH, expand=True)
        self.main_container = outer
        header = ttk.Frame(outer, style="Panel.TFrame", padding=(10, 7))
        header.pack(fill=X, pady=(0, 8))
        if self.logo_small:
            ttk.Label(header, image=self.logo_small, style="Panel.TLabel").pack(side=LEFT, padx=(0, 8))
        title_box = ttk.Frame(header)
        title_box.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(title_box, text="CodeHub", font=("Segoe UI", 17, "bold"), style="Panel.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Recorder, scripts, tools, JSON saves.", style="PanelMuted.TLabel").pack(anchor="w")
        ttk.Label(header, textvariable=self.status, foreground="#8fd9ff", background="#101a27").pack(side=LEFT, padx=12)
        ttk.Button(header, text="Full Screen", style="Ghost.TButton", command=self.toggle_fullscreen).pack(side=RIGHT)

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill=BOTH, expand=True)
        self.tabs.add(self.recorder_tab(), text="Recorder")
        self.tabs.add(self.workspace_tab(), text="Workspace")
        self.tabs.add(self.tools_tab(), text="Tools")
        self.tabs.add(self.review_tab(), text="Review")
        self.tabs.add(self.settings_tab(), text="Settings")

    def minimize_window(self):
        self.root.iconify()

    def recorder_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        controls = ttk.Frame(tab)
        controls.pack(fill=X, pady=(0, 10))
        ttk.Label(controls, text="Recording mode").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.mode, values=["normal", "advanced", "minimal"], width=14, state="readonly").grid(row=0, column=1, padx=(0, 12), sticky="ew")
        ttk.Label(controls, text="Default export").grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.default_export_kind, values=["AutoHotkey v2", "Python"], width=16, state="readonly").grid(row=0, column=3, padx=(0, 12), sticky="ew")
        self.start_button = ttk.Button(controls, text="F1 Start Recording", command=self.start_recording)
        self.stop_button = ttk.Button(controls, text="F2 Stop and Save", command=self.stop_recording)
        self.stop_button.state(["disabled"])
        self.start_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0), padx=(0, 8))
        self.stop_button.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(10, 0), padx=(0, 8))
        ttk.Button(controls, text="Export Selected Again", command=self.export_selected).grid(row=1, column=4, sticky="ew", pady=(10, 0))
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        panes = ttk.PanedWindow(tab, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=3)
        panes.add(right, weight=2)
        ttk.Label(left, text="Live feed").pack(anchor="w")
        self.feed = ScrolledText(left, height=18, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="none")
        self.feed.pack(fill=BOTH, expand=True, pady=(6, 0))
        ttk.Label(right, text="Saved recordings").pack(anchor="w")
        rec_box = ttk.Frame(right)
        rec_box.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.recording_list = ttk.Treeview(rec_box, columns=("name", "export", "mode", "events", "file", "created"), show="headings", height=12)
        rec_scroll = ttk.Scrollbar(rec_box, orient="vertical", command=self.recording_list.yview)
        self.recording_list.configure(yscrollcommand=rec_scroll.set)
        for col, width in [("name", 130), ("export", 105), ("mode", 80), ("events", 70), ("file", 80), ("created", 170)]:
            self.recording_list.heading(col, text=col.title())
            self.recording_list.column(col, width=width, stretch=True)
        self.recording_list.pack(side=LEFT, fill=BOTH, expand=True)
        rec_scroll.pack(side=RIGHT, fill="y")
        action_row = ttk.Frame(right)
        action_row.pack(fill=X, pady=(8, 0))
        ttk.Button(action_row, text="Rename", command=self.rename_recording).pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        ttk.Button(action_row, text="Delete", command=self.delete_recording).pack(side=LEFT, fill=X, expand=True)
        self.refresh_recordings()
        return tab

    def workspace_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        panes = ttk.PanedWindow(tab, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)
        files = ttk.Frame(panes)
        edit = ttk.Frame(panes)
        panes.add(files, weight=1)
        panes.add(edit, weight=3)

        ttk.Label(files, text="Script files").pack(anchor="w")
        file_box = ttk.Frame(files)
        file_box.pack(fill=BOTH, expand=True, pady=(6, 8))
        self.file_tree = ttk.Treeview(file_box, columns=("path", "size"), show="headings", height=18)
        file_scroll = ttk.Scrollbar(file_box, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=file_scroll.set)
        self.file_tree.heading("path", text="Name")
        self.file_tree.heading("size", text="Size")
        self.file_tree.column("path", width=210, stretch=True)
        self.file_tree.column("size", width=70, stretch=False)
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        file_scroll.pack(side=RIGHT, fill="y")
        self.file_tree.bind("<Double-1>", lambda _event: self.open_selected_file())
        file_row = ttk.Frame(files)
        file_row.pack(fill=X)
        ttk.Button(file_row, text="Refresh", command=self.refresh_files).pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        ttk.Button(file_row, text="Open", command=self.open_selected_file).pack(side=LEFT, fill=X, expand=True)
        file_row2 = ttk.Frame(files)
        file_row2.pack(fill=X, pady=(6, 0))
        ttk.Button(file_row2, text="Rename", command=self.rename_selected_file).pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        ttk.Button(file_row2, text="Delete", command=self.delete_selected_file).pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        ttk.Button(file_row2, text="Run", command=self.run_selected_file).pack(side=LEFT, fill=X, expand=True)

        row = ttk.Frame(edit)
        row.pack(fill=X, pady=(0, 8))
        ttk.Button(row, text="Open Any Script", command=self.open_script).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Save", command=self.save_script).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Save As", command=self.save_script_as).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Insert Notes", command=self.insert_notes).pack(side=LEFT)
        ttk.Button(row, text="Run Open Script", command=self.run_open_script).pack(side=LEFT, padx=(8, 0))
        preset_row = ttk.Frame(edit)
        preset_row.pack(fill=X, pady=(0, 8))
        ttk.Button(preset_row, text="AHK Hotkeys", command=self.insert_ahk_hotkeys).pack(side=LEFT, padx=(0, 8))
        ttk.Button(preset_row, text="Python Macro Base", command=self.insert_python_macro_base).pack(side=LEFT, padx=(0, 8))
        ttk.Button(preset_row, text="JSON Helper", command=self.insert_json_helper).pack(side=LEFT)
        self.editor_path = StringVar(value="No file open")
        ttk.Label(edit, textvariable=self.editor_path, style="Muted.TLabel").pack(anchor="w")
        self.editor = ScrolledText(edit, bg="#081019", fg="#e7eef8", insertbackground="#ffffff", undo=True, wrap="none", font=("Consolas", 10))
        self.editor.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.editor.bind("<Tab>", self.editor_autocomplete)
        self.refresh_files()
        return tab

    def tools_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tool_tabs = ttk.Notebook(tab)
        self.tool_tabs.pack(fill=BOTH, expand=True)
        self.tool_tabs.add(self.assistant_tool(), text="Assistant")
        self.tool_tabs.add(self.converter_tool(), text="Converter")
        self.tool_tabs.add(self.position_logger_tool(), text="Position Logger")
        return tab

    def assistant_tool(self):
        helper = ttk.Frame(self.tool_tabs, padding=12)
        ttk.Label(helper, text="Local assistant", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(helper, text="Pick a script, ask for a change, review the diff, then apply or undo.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        target_row = ttk.Frame(helper)
        target_row.pack(fill=X, pady=(0, 8))
        ttk.Label(target_row, text="Target").pack(side=LEFT, padx=(0, 6))
        self.ai_target_var = StringVar(value="")
        self.ai_target_combo = ttk.Combobox(target_row, textvariable=self.ai_target_var, values=[], state="readonly")
        self.ai_target_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(target_row, text="Refresh", command=self.refresh_ai_targets).pack(side=LEFT)
        self.helper_question = ScrolledText(helper, height=6, bg="#081019", fg="#e7eef8", insertbackground="#ffffff", wrap="word")
        self.helper_question.pack(fill=BOTH, expand=True, pady=6)
        row = ttk.Frame(helper)
        row.pack(fill=X)
        ttk.Button(row, text="Ask Helper", command=self.ask_helper).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Generate Review", command=self.generate_ai_review).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Apply Reviewed Change", command=self.apply_ai_review).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Undo Last AI Change", command=self.undo_ai_change).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Apply Safe Header To Open Script", command=self.apply_ai_header).pack(side=LEFT)
        self.helper_answer = ScrolledText(helper, height=8, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="word")
        self.helper_answer.pack(fill=BOTH, expand=True, pady=(8, 0))
        ttk.Label(helper, text="Change review").pack(anchor="w", pady=(8, 0))
        self.ai_diff_view = ScrolledText(helper, height=10, bg="#050a12", fg="#8fd9ff", insertbackground="#ffffff", wrap="none")
        self.ai_diff_view.pack(fill=BOTH, expand=True, pady=(4, 0))
        self.root.after(100, self.refresh_ai_targets)
        return helper

    def converter_tool(self):
        converter = ttk.Frame(self.tool_tabs, padding=12)
        ttk.Label(converter, text="Python / AutoHotkey converter", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.converter_mode = StringVar(value="Python to AutoHotkey")
        ttk.Combobox(converter, textvariable=self.converter_mode, values=["Python to AutoHotkey", "AutoHotkey to Python"], state="readonly").pack(fill=X, pady=6)
        self.converter_input = ScrolledText(converter, height=9, bg="#081019", fg="#e7eef8", insertbackground="#ffffff", wrap="none")
        self.converter_input.pack(fill=BOTH, expand=True)
        row = ttk.Frame(converter)
        row.pack(fill=X, pady=8)
        ttk.Button(row, text="Convert", command=self.convert_code).pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        ttk.Button(row, text="Put Output In Editor", command=self.apply_converter_output_to_editor).pack(side=LEFT, fill=X, expand=True)
        self.converter_output = ScrolledText(converter, height=9, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="none")
        self.converter_output.pack(fill=BOTH, expand=True)
        return converter

    def position_logger_tool(self):
        tab = ttk.Frame(self.tool_tabs, padding=12)
        ttk.Label(tab, text="Left-click position logger", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(tab, text="Session-only logger. It records left clicks outside CodeHub while enabled, then clears when the app closes.", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        row = ttk.Frame(tab)
        row.pack(fill=X, pady=(0, 8))
        ttk.Button(row, text="Start Logging", command=self.start_position_logging).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Stop Logging", command=self.stop_position_logging).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Clear Log", command=self.clear_position_log).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Insert Clicks Into Editor", command=self.insert_position_log_into_editor).pack(side=LEFT)
        self.position_status = StringVar(value="Stopped | 0 clicks")
        ttk.Label(tab, textvariable=self.position_status, foreground="#8fd9ff", background="#080d14").pack(anchor="w", pady=(0, 8))
        self.position_output = ScrolledText(tab, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="none")
        self.position_output.pack(fill=BOTH, expand=True)
        return tab

    def permissions_tool(self):
        tab = ttk.Frame(self.tool_tabs, padding=12)
        ttk.Label(tab, text="Assistant permissions", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(tab, text="These are intentionally explicit. CodeHub will not edit, delete, or run things unless the matching box is enabled.", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Checkbutton(tab, text="Allow assistant to edit the open script", variable=self.ai_can_edit).pack(anchor="w", pady=4)
        ttk.Checkbutton(tab, text="Allow assistant to delete selected files", variable=self.ai_can_delete).pack(anchor="w", pady=4)
        ttk.Checkbutton(tab, text="Allow assistant to run script commands", variable=self.ai_can_run).pack(anchor="w", pady=4)
        note = ScrolledText(tab, height=8, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="word")
        note.pack(fill=BOTH, expand=True, pady=(12, 0))
        note.insert(END, "For this build, the assistant is local/rule-based. The toggles are wired for file actions in the UI, but it is not a real cloud coding agent yet. That is safer than pretending it can freely run your PC.")
        note.configure(state="disabled")
        return tab

    def review_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        top = ttk.Frame(tab)
        top.pack(fill=X, pady=(0, 8))
        ttk.Label(top, text="Recording").pack(side=LEFT, padx=(0, 6))
        self.review_recording_var = StringVar(value="")
        self.review_recording_combo = ttk.Combobox(top, textvariable=self.review_recording_var, values=[], state="readonly", width=34)
        self.review_recording_combo.pack(side=LEFT, padx=(0, 8))
        ttk.Button(top, text="Load", command=self.load_review_recording).pack(side=LEFT, padx=(0, 8))
        ttk.Button(top, text="Play", command=self.play_review).pack(side=LEFT, padx=(0, 6))
        ttk.Button(top, text="Pause", command=self.pause_review).pack(side=LEFT, padx=(0, 6))
        ttk.Button(top, text="Stop", command=self.stop_visual_replay).pack(side=LEFT, padx=(0, 6))
        ttk.Button(top, text="Rewind", command=self.rewind_review).pack(side=LEFT, padx=(0, 6))
        ttk.Label(top, text="Speed").pack(side=LEFT, padx=(8, 4))
        ttk.Combobox(top, textvariable=self.review_speed, values=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0], state="readonly", width=6).pack(side=LEFT)
        panes = ttk.PanedWindow(tab, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        ttk.Label(left, text="Replay / stats").pack(anchor="w")
        self.review_output = ScrolledText(left, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="word", height=12)
        self.review_output.pack(fill=BOTH, expand=True, pady=(6, 8))
        ttk.Label(left, text="Virtual keyboard / input monitor").pack(anchor="w")
        self.virtual_keys = ScrolledText(left, bg="#050a12", fg="#8fd9ff", insertbackground="#ffffff", wrap="word", height=10)
        self.virtual_keys.pack(fill=BOTH, expand=True, pady=(6, 0))
        ttk.Label(right, text="Screen snapshot replay").pack(anchor="w")
        self.review_image_label = ttk.Label(right, text="Load a recording to preview captured frames.", anchor="center")
        self.review_image_label.pack(fill=BOTH, expand=True, pady=(6, 8))
        ttk.Label(right, text="Macro event timeline").pack(anchor="w")
        self.review_timeline = ScrolledText(right, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="none", height=9)
        self.review_timeline.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.review_events = []
        self.review_replaying = False
        self.refresh_review_options()
        return tab

    def settings_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        ttk.Label(tab, text="Export folder").pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill=X, pady=6)
        ttk.Entry(row, textvariable=self.export_dir_var).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(row, text="Choose", command=self.choose_export_dir).pack(side=RIGHT)
        prefs = ttk.Frame(tab)
        prefs.pack(fill=X, pady=(8, 0))
        ttk.Label(prefs, text="UI font size").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(prefs, textvariable=self.ui_font_size, values=["8", "9", "10", "11", "12"], state="readonly", width=6).pack(side=LEFT, padx=(0, 12))
        ttk.Label(prefs, text="Density").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(prefs, textvariable=self.ui_density, values=["compact", "comfortable"], state="readonly", width=12).pack(side=LEFT, padx=(0, 12))
        ttk.Button(prefs, text="Save UI Settings", command=self.save_ui_settings).pack(side=LEFT)
        perms = ttk.Frame(tab)
        perms.pack(fill=X, pady=(12, 4))
        ttk.Label(perms, text="Permissions").pack(anchor="w")
        ttk.Checkbutton(perms, text="Allow assistant to edit the open script", variable=self.ai_can_edit, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(perms, text="Allow assistant to delete selected files", variable=self.ai_can_delete, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(perms, text="Allow assistant to run script commands", variable=self.ai_can_run, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(perms, text="Capture lightweight review screenshots while recording", variable=self.record_screenshots, command=self.save_permissions).pack(anchor="w", pady=2)
        info = ScrolledText(tab, height=10, bg="#081019", fg="#d9e7f5", insertbackground="#ffffff", wrap="word")
        info.pack(fill=BOTH, expand=True, pady=(10, 0))
        info.insert(END, f"Settings JSON: {SETTINGS_PATH}\n")
        info.insert(END, f"Recordings JSON: {RECORDINGS_PATH}\n")
        info.insert(END, f"Knowledge JSON: {KNOWLEDGE_PATH}\n")
        info.insert(END, "Generated scripts always include comments explaining hotkeys, editing, and watermark removal.\n")
        info.configure(state="disabled")
        return tab

    def start_hotkeys(self):
        def on_press(key):
            if self.macro_locked:
                return
            if key == Key.f1:
                self.root.after(0, self.start_recording)
            elif key == Key.f2:
                self.root.after(0, self.stop_recording)
        self.hotkey_listener = keyboard.Listener(on_press=on_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def start_recording(self):
        if self.macro_locked:
            return
        if self.is_recording:
            return
        self.is_recording = True
        self.review_shots = []
        self.feed.delete("1.0", END)
        self.settings["default_export_kind"] = self.default_export_kind.get()
        write_json(SETTINGS_PATH, self.settings)
        self.feed.insert(END, f"Recording started. Press F2 to stop. Default export: {self.default_export_kind.get()}.\n")
        self.status.set("Recording")
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        self.recorder.start(self.mode.get())
        self.capture_review_snapshot("start")
        self.root.after(1000, self.capture_review_tick)

    def stop_recording(self):
        if self.macro_locked:
            return
        if not self.is_recording:
            return
        self.is_recording = False
        self.capture_review_snapshot("stop")
        events = self.recorder.stop()
        default_name = self.settings.get("default_script_name", "MyMacro")
        dialog = SaveRecordingDialog(self.root, default_name, self.default_export_kind.get())
        self.start_button.state(["!disabled"])
        self.stop_button.state(["disabled"])
        if not dialog.result:
            self.status.set(f"Discarded {len(events)} events")
            self.feed.insert(END, "Recording stopped and discarded because save was cancelled.\n")
            return
        export_kind = dialog.result["export_kind"]
        if export_kind == "Default":
            export_kind = self.default_export_kind.get()
        record = {
            "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "name": dialog.result["name"],
            "mode": self.mode.get(),
            "export_kind": export_kind,
            "created": datetime.now().isoformat(timespec="seconds"),
            "events": events,
            "review_screenshots": getattr(self, "review_shots", []),
        }
        self.recordings.setdefault("recordings", []).append(record)
        write_json(RECORDINGS_PATH, self.recordings)
        self.settings["default_script_name"] = record["name"]
        self.settings["default_export_kind"] = self.default_export_kind.get()
        write_json(SETTINGS_PATH, self.settings)
        self.status.set(f"Saved {record['name']} | {len(events)} events")
        self.feed.insert(END, f"Saved {record['name']} to JSON and exporting as {export_kind}.\n")
        self.refresh_recordings()
        self.export_recording(record, export_kind)

    def on_event(self, event):
        self.root.after(0, lambda: self.feed.insert(END, event_line(event) + "\n"))

    def capture_review_snapshot(self, label):
        if not self.record_screenshots.get():
            return
        try:
            import mss
            from PIL import Image
            review_dir = DATA_DIR / "review_frames"
            review_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = review_dir / f"{stamp}_{label}.png"
            with mss.mss() as grabber:
                monitor = grabber.monitors[1]
                shot = grabber.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
                image.thumbnail((640, 360))
                image.save(path)
            self.review_shots.append(str(path))
        except Exception:
            pass

    def capture_review_tick(self):
        if not self.is_recording:
            return
        self.capture_review_snapshot("tick")
        interval = int(self.settings.get("review_capture_interval_ms", 2000))
        self.root.after(max(750, interval), self.capture_review_tick)

    def refresh_recordings(self):
        if not hasattr(self, "recording_list"):
            return
        old_focus = self.recording_list.focus()
        old_selection = self.recording_list.selection()
        self.recordings = read_json(RECORDINGS_PATH, {"recordings": []})
        self._last_recordings_signature = json.dumps(self.recordings, sort_keys=True)
        try:
            self._last_recordings_mtime = RECORDINGS_PATH.stat().st_mtime
        except OSError:
            self._last_recordings_mtime = None
        for row in self.recording_list.get_children():
            self.recording_list.delete(row)
        for index, rec in enumerate(self.recordings.get("recordings", [])):
            self.recording_list.insert("", END, iid=str(index), values=(
                rec.get("name"),
                rec.get("export_kind", "AutoHotkey v2"),
                rec.get("mode"),
                len(rec.get("events", [])),
                "Missing" if rec.get("export_missing") else "OK",
                rec.get("created"),
            ))
        if old_focus and self.recording_list.exists(old_focus):
            self.recording_list.focus(old_focus)
            self.recording_list.selection_set(old_selection or (old_focus,))
        self.refresh_review_options()

    def selected_recording(self):
        selected = self.recording_list.selection()
        item = selected[0] if selected else self.recording_list.focus()
        if not item:
            messagebox.showinfo(APP_NAME, "Select a recording first.")
            return None, None
        index = int(item)
        return index, self.recordings["recordings"][index]

    def selected_review_recording(self):
        value = self.review_recording_var.get() if hasattr(self, "review_recording_var") else ""
        if value:
            try:
                index = int(value.split(":", 1)[0])
                return index, self.recordings["recordings"][index]
            except Exception:
                pass
        return self.selected_recording()

    def refresh_review_options(self):
        if not hasattr(self, "review_recording_combo"):
            return
        values = [
            f"{index}: {rec.get('name', 'macro')} ({len(rec.get('events', []))} events)"
            for index, rec in enumerate(self.recordings.get("recordings", []))
        ]
        current = self.review_recording_var.get()
        self.review_recording_combo.configure(values=values)
        if current in values:
            self.review_recording_var.set(current)
        elif values:
            self.review_recording_var.set(values[-1])
        else:
            self.review_recording_var.set("")

    def export_selected(self):
        _, rec = self.selected_recording()
        if not rec:
            return
        self.export_recording(rec, rec.get("export_kind", self.default_export_kind.get()))

    def export_recording(self, rec, export_kind):
        export_dir = resolve_app_path(self.export_dir_var.get())
        export_dir.mkdir(parents=True, exist_ok=True)
        if export_kind == "AutoHotkey v2":
            code = generate_ahk(rec["events"], rec["mode"], rec["name"])
            path = export_dir / f"{safe_name(rec['name'])}.ahk"
        else:
            code = generate_python(rec["events"], rec["mode"], rec["name"])
            path = export_dir / f"{safe_name(rec['name'])}.py"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code)
        rec["export_path"] = str(path)
        rec["export_missing"] = False
        write_json(RECORDINGS_PATH, self.recordings)
        self.current_editor_file = path
        self.editor.delete("1.0", END)
        self.editor.insert(END, code)
        self.editor_path.set(str(path))
        self.tabs.select(1)
        self.refresh_files()
        messagebox.showinfo(APP_NAME, f"Exported:\n{path}")

    def delete_recording(self):
        index, rec = self.selected_recording()
        if rec is None:
            return
        if messagebox.askyesno(APP_NAME, f"Delete cached recording {rec.get('name')}?"):
            export_path = Path(rec.get("export_path", ""))
            if export_path.exists() and messagebox.askyesno(APP_NAME, "Also delete the exported script file?"):
                try:
                    export_path.unlink()
                except Exception as exc:
                    messagebox.showerror(APP_NAME, f"Could not delete exported script:\n{exc}")
            self.recordings["recordings"].pop(index)
            write_json(RECORDINGS_PATH, self.recordings)
            self.refresh_recordings()
            self.refresh_files()

    def rename_recording(self):
        index, rec = self.selected_recording()
        if rec is None:
            return
        dialog = SaveRecordingDialog(self.root, rec.get("name", "macro"), rec.get("export_kind", self.default_export_kind.get()))
        if not dialog.result:
            return
        export_kind = dialog.result["export_kind"]
        if export_kind == "Default":
            export_kind = self.default_export_kind.get()
        rec["name"] = dialog.result["name"]
        rec["export_kind"] = export_kind
        self.recordings["recordings"][index] = rec
        write_json(RECORDINGS_PATH, self.recordings)
        self.refresh_recordings()

    def refresh_files(self):
        if not hasattr(self, "file_tree"):
            return
        old_focus = self.file_tree.focus()
        old_selection = self.file_tree.selection()
        for row in self.file_tree.get_children():
            self.file_tree.delete(row)
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        files = sorted([path for path in export_dir.iterdir() if path.is_file() and path.suffix.lower() in {".py", ".ahk", ".txt"}])
        self._last_file_snapshot = {f"{path}|{path.stat().st_mtime}|{path.stat().st_size}" for path in files}
        for path in files:
            self.file_tree.insert("", END, iid=str(path), values=(path.name, format_size(path.stat().st_size)))
        if old_focus and self.file_tree.exists(old_focus):
            self.file_tree.focus(old_focus)
            self.file_tree.selection_set(old_selection or (old_focus,))
        if self.sync_recording_exports(files):
            self.refresh_recordings()
        self.refresh_ai_targets()

    def sync_recording_exports(self, files):
        records = self.recordings.get("recordings", [])
        changed = False
        stems = {path.stem.lower(): path for path in files}
        linked_paths = set()
        for rec in records:
            current = Path(rec.get("export_path", ""))
            if rec.get("export_path") and current.exists():
                linked_paths.add(str(current))
                if rec.get("name") != current.stem:
                    rec["name"] = current.stem
                    changed = True
                if rec.get("export_missing"):
                    rec["export_missing"] = False
                    changed = True
                continue
            expected = safe_name(rec.get("name", "")).lower()
            if expected in stems:
                linked_paths.add(str(stems[expected]))
                if rec.get("export_path") != str(stems[expected]):
                    rec["export_path"] = str(stems[expected])
                    changed = True
                if rec.get("export_missing"):
                    rec["export_missing"] = False
                    changed = True
            else:
                if not rec.get("export_missing"):
                    rec["export_missing"] = True
                    changed = True
        missing_records = [rec for rec in records if rec.get("export_missing")]
        unlinked_files = [path for path in files if str(path) not in linked_paths]
        if len(missing_records) == 1 and len(unlinked_files) == 1:
            rec = missing_records[0]
            path = unlinked_files[0]
            rec["name"] = path.stem
            rec["export_path"] = str(path)
            rec["export_missing"] = False
            changed = True
        if changed:
            write_json(RECORDINGS_PATH, self.recordings)
        return changed

    def start_auto_refresh(self):
        self.auto_refresh()

    def auto_refresh(self):
        try:
            if self.recordings_changed_on_disk():
                self.refresh_recordings()
            if self.files_changed_on_disk():
                self.refresh_files()
            self.watch_external_macros()
            if self.current_editor_file and not Path(self.current_editor_file).exists():
                self.current_editor_file = None
                self.editor_path.set("Open file was deleted outside CodeHub")
                self.status.set("Workspace refreshed")
        except Exception:
            pass
        self.root.after(1800, self.auto_refresh)

    def recordings_changed_on_disk(self):
        try:
            mtime = RECORDINGS_PATH.stat().st_mtime
        except OSError:
            mtime = None
        return mtime != self._last_recordings_mtime

    def files_changed_on_disk(self):
        if not hasattr(self, "file_tree"):
            return False
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            f"{path}|{path.stat().st_mtime}|{path.stat().st_size}"
            for path in export_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".py", ".ahk", ".txt"}
        }
        if snapshot != self._last_file_snapshot:
            self._last_file_snapshot = snapshot
            return True
        return False

    def load_review_recording(self):
        _, rec = self.selected_review_recording()
        if not rec:
            return
        self.review_events = rec.get("events", [])
        self.review_shot_paths = [p for p in rec.get("review_screenshots", []) if Path(p).exists()]
        self.review_shot_index = 0
        self.review_play_index = 0
        self.review_playing = False
        self.review_paused = False
        total_time = max([float(e.get("time", 0)) for e in self.review_events] or [0])
        presses = [e for e in self.review_events if e.get("type") in ("key_press", "key_char")]
        clicks = [e for e in self.review_events if e.get("type") == "mouse_click" and e.get("pressed")]
        self.review_output.delete("1.0", END)
        self.review_output.insert(END, f"Macro: {rec.get('name')}\n")
        self.review_output.insert(END, f"Mode: {rec.get('mode')} | Events: {len(self.review_events)} | Duration: {total_time:.2f}s\n")
        self.review_output.insert(END, f"Key presses: {len(presses)} | Clicks: {len(clicks)}\n")
        if self.review_shot_paths:
            self.review_output.insert(END, f"\nVisual frames: {len(self.review_shot_paths)} captured screenshots\n")
            self.show_review_frame(0)
        else:
            self.review_output.insert(END, "\nNo screenshots saved for this recording yet.\n")
            self.review_image_label.configure(image="", text="No captured frames for this recording.")
        self.review_timeline.delete("1.0", END)
        for event in self.review_events:
            self.review_timeline.insert(END, event_line(event) + "\n")
        self.virtual_keys.delete("1.0", END)
        self.virtual_keys.insert(END, "Loaded. Press Play.\n")

    def show_review_frame(self, index):
        if not self.review_shot_paths:
            return
        index = max(0, min(index, len(self.review_shot_paths) - 1))
        self.review_shot_index = index
        path = Path(self.review_shot_paths[index])
        if Image is None or ImageTk is None:
            self.review_image_label.configure(text=f"Frame {index + 1}/{len(self.review_shot_paths)}\n{path}", image="")
            return
        try:
            image = Image.open(path).convert("RGB")
            max_w = max(360, self.review_image_label.winfo_width() or 640)
            max_h = max(240, self.review_image_label.winfo_height() or 360)
            image.thumbnail((max_w, max_h))
            self.review_photo = ImageTk.PhotoImage(image)
            self.review_image_label.configure(
                image=self.review_photo,
                text=f"Frame {index + 1}/{len(self.review_shot_paths)}",
                compound="top",
            )
        except Exception as exc:
            self.review_image_label.configure(text=f"Could not load frame:\n{path}\n{exc}", image="")

    def review_next_frame(self):
        if self.review_shot_paths:
            self.show_review_frame((self.review_shot_index + 1) % len(self.review_shot_paths))

    def review_prev_frame(self):
        if self.review_shot_paths:
            self.show_review_frame((self.review_shot_index - 1) % len(self.review_shot_paths))

    def play_review(self):
        if not getattr(self, "review_events", None):
            self.load_review_recording()
        if not self.review_events:
            return
        if self.review_playing and self.review_paused:
            self.review_paused = False
            return
        if self.review_playing:
            return
        self.review_playing = True
        self.review_replaying = True
        self.review_paused = False
        if self.review_play_index >= len(self.review_events):
            self.review_play_index = 0
        self.virtual_keys.delete("1.0", END)
        threading.Thread(target=self.visual_replay_worker, daemon=True).start()

    def pause_review(self):
        if self.review_playing:
            self.review_paused = True
            self.status.set("Replay paused")

    def rewind_review(self):
        self.review_play_index = 0
        self.review_shot_index = 0
        if self.review_shot_paths:
            self.show_review_frame(0)
        self.set_virtual_keys("Rewound to start. Press Play.\n")

    def start_visual_replay(self):
        self.play_review()

    def stop_visual_replay(self):
        self.review_replaying = False
        self.review_playing = False
        self.review_paused = False
        self.review_play_index = 0
        self.status.set("Replay stopped")

    def visual_replay_worker(self):
        if not self.review_events:
            return
        active = set()
        replay_started = time.perf_counter()
        base_event_time = float(self.review_events[self.review_play_index].get("time", 0)) if self.review_play_index < len(self.review_events) else 0.0
        last_frame_index = -1
        while self.review_play_index < len(self.review_events):
            if not self.review_replaying:
                break
            while self.review_paused and self.review_replaying:
                time.sleep(0.05)
            if not self.review_replaying:
                break
            event = self.review_events[self.review_play_index]
            t = float(event.get("time", 0))
            try:
                speed = max(0.05, float(self.review_speed.get()))
            except Exception:
                speed = 1.0
            target = replay_started + max(0, (t - base_event_time) / speed)
            while self.review_replaying and not self.review_paused:
                remaining = target - time.perf_counter()
                if remaining <= 0:
                    break
                time.sleep(min(0.01, max(0.001, remaining)))
            kind = event.get("type")
            key = str(event.get("key", event.get("char", "")))
            if kind in ("key_press", "key_char"):
                active.add(key)
            elif kind == "key_release" and key in active:
                active.remove(key)
            event_speed = (self.review_play_index + 1) / max(0.1, time.perf_counter() - replay_started)
            text = f"Time: {t:.2f}s | Speed: {speed:.1f} events/sec\n"
            text = f"Time: {t:.2f}s | Playback: {speed:.2f}x | Event rate: {event_speed:.1f}/sec\n"
            text += f"Now: {event_line(event)}\n"
            text += "Pressed: " + (", ".join(sorted(active)) if active else "none") + "\n"
            text += "Pressure: keyboards do not expose pressure; hold duration is preserved.\n"
            self.root.after(0, lambda value=text: self.set_virtual_keys(value))
            if self.review_shot_paths:
                frame_index = min(len(self.review_shot_paths) - 1, int((t / max(0.1, self.review_events[-1].get("time", 0.1))) * len(self.review_shot_paths)))
                if frame_index != last_frame_index:
                    last_frame_index = frame_index
                    self.root.after(0, lambda idx=frame_index: self.show_review_frame(idx))
            self.review_play_index += 1
        self.review_replaying = False
        self.review_playing = False
        self.review_paused = False

    def set_virtual_keys(self, text):
        self.virtual_keys.delete("1.0", END)
        self.virtual_keys.insert(END, text)

    def selected_file_path(self):
        item = self.file_tree.focus()
        if not item:
            messagebox.showinfo(APP_NAME, "Select a script file first.")
            return None
        return Path(item)

    def open_selected_file(self):
        path = self.selected_file_path()
        if path:
            self.load_script(path)

    def run_selected_file(self):
        path = self.selected_file_path()
        if path:
            self.run_script(path)

    def run_open_script(self):
        if not self.current_editor_file:
            messagebox.showinfo(APP_NAME, "Open or save a script before running it.")
            return
        self.save_script()
        self.run_script(Path(self.current_editor_file))

    def run_script(self, path):
        path = Path(path)
        if not path.exists():
            messagebox.showerror(APP_NAME, f"Script does not exist:\n{path}")
            self.refresh_files()
            return
        try:
            if path.suffix.lower() == ".py":
                self.status.set(f"Loading {path.name}...")
                self.root.update_idletasks()
                proc = subprocess.Popen(
                    pythonw_command() + [str(path)],
                    cwd=str(path.parent),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags(),
                )
            elif path.suffix.lower() == ".ahk":
                ahk = find_ahk_exe()
                if ahk:
                    self.status.set(f"Loading {path.name}...")
                    self.root.update_idletasks()
                    proc = subprocess.Popen(
                        [ahk, str(path)],
                        cwd=str(path.parent),
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=hidden_process_flags(),
                    )
                else:
                    messagebox.showwarning(
                        APP_NAME,
                        "AutoHotkey was not found in PATH or Program Files. Windows will open the .ahk file normally, so a launcher window may flash.",
                    )
                    proc = subprocess.Popen(
                        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", f"Start-Process -FilePath {json.dumps(str(path))} -Wait"],
                        cwd=str(path.parent),
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=hidden_process_flags(),
                    )
            else:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", f"Start-Process -FilePath {json.dumps(str(path))} -Wait"],
                    cwd=str(path.parent),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags(),
                )
            self.status.set(f"Running {path.name}")
            self.lock_for_macro(proc, path.name)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not run script:\n{exc}")

    def lock_for_macro(self, proc, label):
        self.macro_locked = True
        self.macro_process = proc
        self.macro_lock_kind = "process"
        self.show_lock_overlay(label)
        self.root.after(700, self.poll_macro_process)

    def lock_for_external_macro(self, pids, paths):
        if self.macro_locked:
            return
        self.macro_locked = True
        self.macro_process = None
        self.macro_lock_kind = "external"
        self.external_macro_pids = set(pids)
        self.external_macro_paths = {str(path) for path in paths}
        label = ", ".join(sorted(Path(path).name for path in self.external_macro_paths)) or "external macro"
        self.status.set(f"Detected running macro: {label}")
        self.show_lock_overlay(label)
        self.root.after(900, self.poll_macro_process)

    def show_lock_overlay(self, label):
        if self.lock_overlay and self.lock_overlay.winfo_exists():
            return
        overlay = ttk.Frame(self.main_container, style="Lock.TFrame")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.bind("<Button>", lambda _event: "break")
        overlay.bind("<Key>", lambda _event: "break")
        self.root.update_idletasks()
        frame = ttk.Frame(overlay, padding=24, style="LockPanel.TFrame")
        frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.46)
        ttk.Label(frame, text="LOCKED", font=("Segoe UI", 22, "bold"), style="LockPanel.TLabel").pack(anchor="center")
        ttk.Label(
            frame,
            text=f"Running macro: {label}\nClose/stop the macro to continue using CodeHub.\nCodeHub hotkeys are disabled while locked.",
            style="LockMuted.TLabel",
            justify="center",
        ).pack(anchor="center", pady=(10, 0))
        overlay.focus_set()
        try:
            overlay.grab_set()
        except Exception:
            pass
        self.lock_overlay = overlay
        self.lock_window = overlay

    def poll_macro_process(self):
        if not self.macro_locked:
            return
        if self.macro_lock_kind == "external":
            running = self.find_running_export_macros()
            active = {pid for pid, _path in running}
            if active & self.external_macro_pids:
                self.external_macro_pids = active & self.external_macro_pids
                self.root.after(900, self.poll_macro_process)
                return
            self.unlock_after_macro()
            return
        if self.macro_process and self.macro_process.poll() is None:
            self.root.after(700, self.poll_macro_process)
            return
        self.unlock_after_macro()

    def unlock_after_macro(self):
        self.macro_locked = False
        self.macro_process = None
        self.macro_lock_kind = "process"
        self.external_macro_pids = set()
        self.external_macro_paths = set()
        if self.lock_overlay and self.lock_overlay.winfo_exists():
            try:
                self.lock_overlay.grab_release()
            except Exception:
                pass
            self.lock_overlay.destroy()
        self.lock_overlay = None
        self.lock_window = None
        self.status.set("Macro closed")

    def watch_external_macros(self):
        if self.macro_locked:
            return
        now = time.time()
        if self._process_scan_running or now - self._last_process_scan < 5.0:
            return
        self._last_process_scan = now
        self._process_scan_running = True

        def scan():
            try:
                running = self.find_running_export_macros()
            except Exception:
                running = []
            self.root.after(0, lambda value=running: self.finish_external_macro_scan(value))

        threading.Thread(target=scan, daemon=True).start()

    def finish_external_macro_scan(self, running):
        self._process_scan_running = False
        if running and not self.macro_locked:
            self.lock_for_external_macro({pid for pid, _path in running}, {path for _pid, path in running})

    def export_script_paths(self):
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        paths = [path.resolve() for path in export_dir.iterdir() if path.is_file() and path.suffix.lower() in {".py", ".ahk", ".exe"}]
        for rec in self.recordings.get("recordings", []):
            try:
                path = Path(rec.get("export_path", "")).resolve()
                if path.exists():
                    paths.append(path)
            except Exception:
                pass
        return sorted(set(paths))

    def process_snapshot(self):
        if os.name != "nt":
            return []
        command = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,ExecutablePath,CommandLine | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=hidden_process_flags(),
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                return [data]
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def find_running_export_macros(self):
        targets = self.export_script_paths()
        if not targets:
            return []
        target_text = {str(path).lower(): path for path in targets}
        own_pid = os.getpid()
        found = []
        for proc in self.process_snapshot():
            try:
                pid = int(proc.get("ProcessId", 0))
            except Exception:
                continue
            if not pid or pid == own_pid:
                continue
            command_line = str(proc.get("CommandLine") or "")
            executable = str(proc.get("ExecutablePath") or "")
            haystack = f"{command_line} {executable}".lower()
            for text, path in target_text.items():
                if text in haystack:
                    found.append((pid, path))
                    break
        return found

    def rename_selected_file(self):
        path = self.selected_file_path()
        if not path:
            return
        dialog = SaveRecordingDialog(self.root, path.stem, self.default_export_kind.get())
        if not dialog.result:
            return
        new_path = path.with_name(safe_name(dialog.result["name"]) + path.suffix)
        if new_path.exists():
            messagebox.showerror(APP_NAME, "A file with that name already exists.")
            return
        path.rename(new_path)
        if self.current_editor_file == path:
            self.current_editor_file = new_path
            self.editor_path.set(str(new_path))
        self.refresh_files()

    def delete_selected_file(self):
        path = self.selected_file_path()
        if not path:
            return
        if messagebox.askyesno(APP_NAME, f"Delete script file?\n{path}"):
            try:
                path.unlink()
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Could not delete file:\n{exc}")
                return
            if self.current_editor_file == path:
                self.current_editor_file = None
                self.editor.delete("1.0", END)
                self.editor_path.set("No file open")
            self.refresh_files()

    def open_script(self):
        path = filedialog.askopenfilename(initialdir=str(resolve_app_path(self.export_dir_var.get())), filetypes=[("Scripts", "*.py *.ahk *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.load_script(Path(path))

    def load_script(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            self.editor.delete("1.0", END)
            self.editor.insert(END, handle.read())
        self.current_editor_file = Path(path)
        self.editor_path.set(str(path))

    def save_script(self):
        path = self.current_editor_file
        if not path:
            self.save_script_as()
            return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.editor.get("1.0", END))
        self.current_editor_file = path
        self.editor_path.set(str(path))
        self.refresh_files()
        messagebox.showinfo(APP_NAME, f"Saved:\n{path}")

    def save_script_as(self):
        path = filedialog.asksaveasfilename(initialdir=str(resolve_app_path(self.export_dir_var.get())), filetypes=[("Scripts", "*.py *.ahk *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.current_editor_file = Path(path)
        self.save_script()

    def insert_notes(self):
        prefix = ";" if self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk" else "#"
        self.editor.insert(
            END,
            f"\n{prefix} CodeHub notes\n"
            f"{prefix} F1 starts, F2 stops, Numpad 5 exits generated scripts.\n"
            f"{prefix} Remove the watermark function/class if you do not want the transparent label.\n"
            f"{prefix} JSON saves are in the data folder next to this app.\n",
        )

    def insert_ahk_hotkeys(self):
        self.editor.insert(END, '\n; AHK v2 hotkey skeleton\n; F1 starts, F2 stops, Numpad5 exits.\nglobal running := false\nF1::{\n    global running\n    running := true\n}\nF2::{\n    global running\n    running := false\n}\nNumpad5::ExitApp\n')

    def insert_python_macro_base(self):
        self.editor.insert(END, '\n# Python macro skeleton\n# Uses pynput for keyboard/mouse events.\nimport time\nfrom pynput.keyboard import Controller as KeyboardController\nfrom pynput.mouse import Controller as MouseController\n\nkeys = KeyboardController()\nmouse = MouseController()\n\ndef wait(seconds):\n    \"\"\"Delay between actions so playback feels human.\"\"\"\n    time.sleep(seconds)\n')

    def insert_json_helper(self):
        self.editor.insert(END, '\n# JSON helper\n# Stores settings or macro metadata in a readable file.\nimport json\nfrom pathlib import Path\n\ndef load_json(path, fallback):\n    path = Path(path)\n    if not path.exists():\n        return fallback\n    with open(path, "r", encoding="utf-8") as handle:\n        return json.load(handle)\n\ndef save_json(path, data):\n    path = Path(path)\n    path.parent.mkdir(parents=True, exist_ok=True)\n    with open(path, "w", encoding="utf-8") as handle:\n        json.dump(data, handle, indent=2)\n')

    def editor_autocomplete(self, event):
        line = self.editor.get("insert linestart", "insert")
        token = re.findall(r"[A-Za-z_#;]+$", line)
        prefix = token[0].lower() if token else ""
        completions = {
            "imp": "import ",
            "def": "def function_name():\n    ",
            "json": "json.dump(data, handle, indent=2)",
            "sleep": "time.sleep(0.1)",
            "send": 'Send("{Enter}")',
            "click": "Click(0, 0)",
            "hot": "F1::\n{\n    ; start here\n}\n",
        }
        for key, value in completions.items():
            if prefix and key.startswith(prefix):
                self.editor.delete(f"insert-{len(prefix)}c", "insert")
                self.editor.insert("insert", value)
                return "break"
        self.editor.insert("insert", "    ")
        return "break"

    def ask_helper(self):
        question = self.helper_question.get("1.0", END).lower()
        answers = []
        for topic, facts in self.knowledge.items():
            if topic in question:
                answers.extend(facts)
        if "hotkey" in question or "f1" in question or "f2" in question or "numpad" in question:
            answers.append("Generated scripts use F1 start, F2 stop, and Numpad 5 exit.")
        if "json" in question or "save" in question or "cache" in question:
            answers.append(f"Recordings are saved in {RECORDINGS_PATH}, and settings are saved in {SETTINGS_PATH}.")
        if "game" in question or "roblox" in question or "currency" in question or "read" in question:
            answers.extend(self.knowledge.get("ocr", []))
        if not answers:
            answers = [
                "This helper is local and rule-based. It can guide script edits, but it is not a cloud AI model.",
                "Paste code into the Editor tab to edit it directly, or paste snippets here for conversion notes.",
            ]
        if self.ai_can_edit.get():
            answers.append("Edit permission is enabled, so the safe header tool can modify the currently open script.")
        else:
            answers.append("Edit permission is off. Enable it in Permissions before letting tools change scripts.")
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "\n".join(f"- {line}" for line in dict.fromkeys(answers)))

    def refresh_ai_targets(self):
        if not hasattr(self, "ai_target_combo"):
            return
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        files = [path for path in export_dir.iterdir() if path.is_file() and path.suffix.lower() in {".py", ".ahk"}]
        current = self.ai_target_var.get()
        values = [str(path) for path in sorted(files)]
        self.ai_target_combo.configure(values=values)
        if current in values:
            self.ai_target_var.set(current)
        elif self.current_editor_file and str(self.current_editor_file) in values:
            self.ai_target_var.set(str(self.current_editor_file))
        elif values:
            self.ai_target_var.set(values[0])

    def ai_target_path(self):
        value = self.ai_target_var.get() if hasattr(self, "ai_target_var") else ""
        if value:
            path = Path(value)
        elif self.current_editor_file:
            path = Path(self.current_editor_file)
        else:
            messagebox.showinfo(APP_NAME, "Pick a script for the assistant first.")
            return None
        if not path.exists():
            messagebox.showerror(APP_NAME, f"Script does not exist:\n{path}")
            self.refresh_ai_targets()
            return None
        return path

    def build_ai_edit(self, text, path, request):
        is_ahk = path.suffix.lower() == ".ahk"
        request = request.lower()
        notes = []
        new_text = text
        if "convert" in request and ("python" in request or "ahk" in request or "autohotkey" in request):
            if is_ahk and "python" in request and "autohotkey" not in request and "ahk" not in request:
                new_text, conv_notes = self.ahk_to_python(text)
                notes.extend(conv_notes)
            elif not is_ahk and ("ahk" in request or "autohotkey" in request):
                new_text, conv_notes = self.python_to_ahk(text)
                notes.extend(conv_notes)
        if "timing" in request or "drift" in request or "bpm" in request or "adofai" in request or "lag" in request:
            if is_ahk:
                if "WaitUntil(" not in new_text:
                    new_text += "\n; CodeHub timing note: regenerate this recording to get absolute WaitUntil timing.\n"
                notes.append("checked for absolute timing drift controls")
            else:
                if "time.perf_counter" not in new_text:
                    new_text = new_text.replace("time.time()", "time.perf_counter()")
                    notes.append("changed wall-clock timing to perf_counter where possible")
        if "watermark" in request and is_ahk:
            new_text = re.sub(r'AddText\("w\d+ Center", "Made by Cat"\)', 'AddText("w150 Center", "Made by Cat")', new_text)
            new_text = re.sub(r"w140 h20", "w168 h26", new_text)
            notes.append("resized watermark box")
        new_text, norm_notes = self.normalize_macro_script(new_text, is_ahk)
        notes.extend(norm_notes)
        if new_text == text:
            prefix = ";" if is_ahk else "#"
            new_text = text.rstrip() + f"\n\n{prefix} CodeHub assistant reviewed this script; no automatic rewrite rule matched the request.\n"
            notes.append("added review note because no safe rewrite matched")
        return new_text, sorted(set(notes))

    def generate_ai_review(self):
        path = self.ai_target_path()
        if not path:
            return
        request = self.helper_question.get("1.0", END).strip()
        if not request:
            messagebox.showinfo(APP_NAME, "Type what you want changed first.")
            return
        old_text = path.read_text(encoding="utf-8")
        new_text, notes = self.build_ai_edit(old_text, path, request)
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"{path.name} before",
            tofile=f"{path.name} proposed",
            lineterm="",
        )
        self.ai_pending_path = path
        self.ai_pending_text = new_text
        self.ai_diff_view.delete("1.0", END)
        self.ai_diff_view.insert(END, "\n".join(diff) or "No textual diff.")
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "Proposed changes:\n" + "\n".join(f"- {item}" for item in notes))

    def apply_ai_review(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Permission needed", "Enable edit permission in Settings first.")
            return
        if not self.ai_pending_path or not self.ai_pending_text:
            messagebox.showinfo(APP_NAME, "Generate a review first.")
            return
        old_text = self.ai_pending_path.read_text(encoding="utf-8") if self.ai_pending_path.exists() else ""
        self.ai_undo_stack.append((self.ai_pending_path, old_text))
        self.ai_pending_path.write_text(self.ai_pending_text, encoding="utf-8")
        self.load_script(self.ai_pending_path)
        self.status.set(f"Applied AI change to {self.ai_pending_path.name}")

    def undo_ai_change(self):
        if not self.ai_undo_stack:
            messagebox.showinfo(APP_NAME, "No AI change to undo.")
            return
        path, old_text = self.ai_undo_stack.pop()
        path.write_text(old_text, encoding="utf-8")
        self.load_script(path)
        self.status.set(f"Undid AI change in {path.name}")

    def rewrite_open_script_from_helper(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Permission needed", "Enable edit permission in Settings first.")
            return
        current = self.editor.get("1.0", END).rstrip()
        if not current.strip():
            messagebox.showinfo(APP_NAME, "Open or paste a script in the editor first.")
            return
        request = self.helper_question.get("1.0", END).lower()
        path = Path(self.current_editor_file) if self.current_editor_file else None
        is_ahk = (path and path.suffix.lower() == ".ahk") or "autohotkey" in request or "ahk" in request
        if "python" in request and "autohotkey" not in request and "ahk" not in request:
            is_ahk = False
        changed = []
        rewritten = current
        if "convert" in request:
            rewritten = self.python_to_ahk(current)[0] if is_ahk else self.ahk_to_python(current)[0]
            changed.append("converted syntax")
        rewritten, notes = self.normalize_macro_script(rewritten, is_ahk)
        changed.extend(notes)
        if not changed:
            changed.append("normalized comments and macro controls")
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", rewritten.rstrip() + "\n")
        self.tabs.select(1)
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "Edited the open editor text:\n" + "\n".join(f"- {item}" for item in dict.fromkeys(changed)))

    def apply_ai_header(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Permission needed", "Enable edit permission in Settings first.")
            return
        is_ahk = self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk"
        comment = ";" if is_ahk else "#"
        header = (
            f"{comment} Edited with CodeHub assistant tools\n"
            f"{comment} F1 starts, F2 stops, and Numpad 5 exits generated macros.\n"
            f"{comment} Review app/game rules before using automation.\n\n"
        )
        current = self.editor.get("1.0", END)
        if "Edited with CodeHub assistant tools" not in current:
            self.editor.insert("1.0", header)
        self.tabs.select(1)

    def convert_code(self):
        source = self.converter_input.get("1.0", END).rstrip()
        if self.converter_mode.get() == "Python to AutoHotkey":
            converted, notes = self.python_to_ahk(source)
        else:
            converted, notes = self.ahk_to_python(source)
        self.converter_output.delete("1.0", END)
        self.converter_output.insert(END, converted.rstrip() + "\n\n")
        self.converter_output.insert(END, "Changes:\n" + "\n".join(f"- {item}" for item in notes))

    def apply_converter_output_to_editor(self):
        output = self.converter_output.get("1.0", END).strip()
        if not output:
            self.convert_code()
            output = self.converter_output.get("1.0", END).strip()
        script = output.split("\n\nChanges:\n", 1)[0].rstrip()
        if not script:
            return
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Permission needed", "Enable edit permission in Settings first.")
            return
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", script + "\n")
        self.tabs.select(1)
        self.status.set("Converted code placed in editor")

    def python_to_ahk(self, source):
        notes = []
        lines = ["#Requires AutoHotkey v2.0", "#SingleInstance Force", "", "global running := false", "", "F1::{", "    global running", "    running := true", "}", "", "F2::{", "    global running", "    running := false", "}", "", "Numpad5::ExitApp", "", "; Converted by CodeHub. Review coordinates and timing before use."]
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                lines.append("")
                continue
            indent = "    " if raw.startswith((" ", "\t")) else ""
            converted = None
            if stripped.startswith("#"):
                converted = "; " + stripped.lstrip("#").strip()
                notes.append("converted Python comments to AHK comments")
            elif re.match(r"time\.sleep\(([^)]+)\)", stripped):
                value = re.findall(r"time\.sleep\(([^)]+)\)", stripped)[0]
                try:
                    ms = int(float(value) * 1000)
                except ValueError:
                    ms = 100
                converted = f"Sleep({ms})"
                notes.append("converted time.sleep to Sleep")
            elif "mouse.position" in stripped and "=" in stripped:
                nums = re.findall(r"-?\d+", stripped)
                converted = f"MouseMove({nums[0]}, {nums[1]}, 0)" if len(nums) >= 2 else "; TODO: MouseMove(x, y, 0)"
                notes.append("converted mouse.position to MouseMove")
            elif re.search(r"mouse\.(click|press|release)", stripped):
                nums = re.findall(r"-?\d+", stripped)
                if "release" in stripped:
                    action = "Up"
                elif "press" in stripped:
                    action = "Down"
                else:
                    action = ""
                coord = f", {nums[0]}, {nums[1]}" if len(nums) >= 2 else ""
                converted = f"Click(\"{action}\"{coord})" if action else f"Click({coord.lstrip(', ')})"
                notes.append("converted mouse click/press/release")
            elif re.search(r"keyboard\.(type|press|release)", stripped) or ".press(" in stripped or ".type(" in stripped:
                text = re.findall(r"[\"'](.+?)[\"']", stripped)
                converted = f"Send({text[0]!r})" if text else "; TODO: Send key/text"
                converted = converted.replace("'", '"')
                notes.append("converted keyboard call to Send")
            elif stripped.startswith(("import ", "from ", "def ", "class ")):
                converted = "; " + stripped
            else:
                converted = "; TODO: " + stripped
            lines.append(indent + converted)
        return "\n".join(lines), sorted(set(notes or ["wrapped Python snippet in runnable AHK hotkey shell"]))

    def ahk_to_python(self, source):
        notes = []
        lines = [
            "# Converted by CodeHub. Review coordinates and timing before use.",
            "import time",
            "from pynput.keyboard import Controller as KeyboardController",
            "from pynput.mouse import Button, Controller as MouseController",
            "",
            "keyboard = KeyboardController()",
            "mouse = MouseController()",
            "running = False",
            "",
        ]
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                lines.append("")
                continue
            converted = None
            if stripped.startswith(";"):
                converted = "# " + stripped.lstrip(";").strip()
                notes.append("converted AHK comments to Python comments")
            elif stripped.lower().startswith("#requires") or stripped.lower().startswith("#singleinstance"):
                converted = "# " + stripped
            elif re.match(r"Sleep\(?\s*(\d+)\s*\)?", stripped, re.I):
                ms = int(re.findall(r"\d+", stripped)[0])
                converted = f"time.sleep({ms / 1000:.3f})"
                notes.append("converted Sleep to time.sleep")
            elif re.match(r"MouseMove\(", stripped, re.I):
                nums = re.findall(r"-?\d+", stripped)
                converted = f"mouse.position = ({nums[0]}, {nums[1]})" if len(nums) >= 2 else "# TODO: mouse.position = (x, y)"
                notes.append("converted MouseMove to mouse.position")
            elif re.match(r"Click\(", stripped, re.I) or stripped.lower().startswith("click"):
                nums = re.findall(r"-?\d+", stripped)
                if "down" in stripped.lower():
                    converted = "mouse.press(Button.left)"
                elif "up" in stripped.lower():
                    converted = "mouse.release(Button.left)"
                elif len(nums) >= 2:
                    converted = f"mouse.position = ({nums[0]}, {nums[1]})\nmouse.click(Button.left)"
                else:
                    converted = "mouse.click(Button.left)"
                notes.append("converted Click to pynput mouse action")
            elif stripped.lower().startswith("send"):
                text = re.findall(r"[\"'](.+?)[\"']|\{(.+?)\}", stripped)
                value = next((a or b for a, b in text), "")
                converted = f"keyboard.type({value!r})" if value else "# TODO: keyboard press/type"
                notes.append("converted Send to keyboard.type")
            elif stripped.endswith("::") or stripped in ("{", "}"):
                converted = "# " + stripped
            else:
                converted = "# TODO: " + stripped
            lines.append(converted)
        return "\n".join(lines), sorted(set(notes or ["wrapped AHK snippet in runnable Python macro shell"]))

    def normalize_macro_script(self, source, is_ahk):
        notes = []
        text = source
        if is_ahk:
            text = re.sub(r"(?m)^(\s*)#(?!Requires|SingleInstance)(.*)$", r"\1;\2", text)
            if "#Requires AutoHotkey v2.0" not in text:
                text = "#Requires AutoHotkey v2.0\n#SingleInstance Force\n" + text
                notes.append("added AHK v2 header")
            if "Numpad5::ExitApp" not in text and "Numpad5::" not in text:
                text += "\n\nNumpad5::ExitApp\n"
                notes.append("added Numpad5 exit hotkey")
            if "F1::" not in text:
                text += "\nF1::{\n    global running := true\n}\n"
                notes.append("added F1 start hotkey")
            if "F2::" not in text:
                text += "\nF2::{\n    global running := false\n}\n"
                notes.append("added F2 stop hotkey")
        else:
            text = re.sub(r"(?m)^(\s*);(.*)$", r"\1#\2", text)
            if "from pynput" not in text and ("mouse." in text or "keyboard." in text):
                text = "import time\nfrom pynput.keyboard import Controller as KeyboardController\nfrom pynput.mouse import Button, Controller as MouseController\n\nkeyboard = KeyboardController()\nmouse = MouseController()\n\n" + text
                notes.append("added Python pynput imports/controllers")
        if "Edited with CodeHub assistant tools" not in text:
            prefix = ";" if is_ahk else "#"
            text = f"{prefix} Edited with CodeHub assistant tools\n" + text
            notes.append("added assistant edit marker")
        return text, notes

    def root_contains_screen_point(self, x, y):
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def start_position_logging(self):
        if self.position_logging:
            return
        self.position_logging = True
        self.position_status.set(f"Logging | {len(self.position_log_events)} clicks")
        self.position_listener = mouse.Listener(on_click=self.on_position_log_click)
        self.position_listener.start()

    def stop_position_logging(self):
        self.position_logging = False
        if self.position_listener:
            self.position_listener.stop()
            self.position_listener = None
        self.position_status.set(f"Stopped | {len(self.position_log_events)} clicks")

    def clear_position_log(self):
        self.position_log_events.clear()
        self.position_output.delete("1.0", END)
        self.position_status.set("Logging | 0 clicks" if self.position_logging else "Stopped | 0 clicks")

    def on_position_log_click(self, x, y, button, pressed):
        if not self.position_logging or not pressed or button != mouse.Button.left:
            return
        if self.root_contains_screen_point(x, y):
            return
        event = {"x": int(x), "y": int(y), "time": time.time(), "index": len(self.position_log_events) + 1}
        self.position_log_events.append(event)
        self.root.after(0, lambda e=event: self.append_position_log(e))

    def append_position_log(self, event):
        stamp = datetime.fromtimestamp(event["time"]).strftime("%H:%M:%S")
        self.position_output.insert(END, f"{event['index']:03d}  {stamp}  left click @ {event['x']}, {event['y']}\n")
        self.position_output.see(END)
        self.position_status.set(f"Logging | {len(self.position_log_events)} clicks")

    def insert_position_log_into_editor(self):
        if not self.position_log_events:
            messagebox.showinfo(APP_NAME, "No logged clicks yet.")
            return
        is_ahk = self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk"
        lines = []
        for event in self.position_log_events:
            if is_ahk:
                lines.append(f"Click({event['x']}, {event['y']})")
            else:
                lines.append(f"mouse.position = ({event['x']}, {event['y']})")
                lines.append("mouse.click(Button.left)")
        self.editor.insert(END, "\n" + "\n".join(lines) + "\n")
        self.tabs.select(1)

    def choose_export_dir(self):
        path = filedialog.askdirectory(initialdir=self.export_dir_var.get())
        if path:
            self.export_dir_var.set(path)
            self.settings["export_dir"] = path
            write_json(SETTINGS_PATH, self.settings)
            self.refresh_files()

    def save_permissions(self):
        self.settings["ai_can_edit"] = self.ai_can_edit.get()
        self.settings["ai_can_delete"] = self.ai_can_delete.get()
        self.settings["ai_can_run"] = self.ai_can_run.get()
        self.settings["record_screenshots"] = self.record_screenshots.get()
        write_json(SETTINGS_PATH, self.settings)
        self.status.set("Settings saved")

    def save_ui_settings(self):
        try:
            size = int(self.ui_font_size.get())
        except ValueError:
            size = 9
        self.settings["ui_font_size"] = max(8, min(12, size))
        self.settings["ui_density"] = self.ui_density.get()
        write_json(SETTINGS_PATH, self.settings)
        self.configure_style()
        self.status.set("UI settings saved")

    def toggle_fullscreen(self):
        self.fullscreen.set(not self.fullscreen.get())
        self.root.attributes("-fullscreen", self.fullscreen.get())

    def close(self):
        if self.is_recording:
            self.recorder.stop()
        self.stop_position_logging()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    CodeHubApp().run()
