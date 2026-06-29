import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import difflib
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path
from tkinter import (
    BOTH, END, HORIZONTAL, LEFT, RIGHT, X, Y, BooleanVar, DoubleVar,
    PhotoImage, StringVar, Tk, Toplevel, Canvas, Frame
)
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

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#080c12",
    "bg2":       "#0b1018",
    "panel":     "#0f1620",
    "panel2":    "#131d2a",
    "border":    "#1e2d3d",
    "border2":   "#243040",
    "text":      "#e8f0f8",
    "text2":     "#7a98b8",
    "text3":     "#3a5060",
    "accent":    "#176bff",
    "accent2":   "#0d4fd8",
    "green":     "#27c96e",
    "green2":    "#1a9550",
    "orange":    "#f09030",
    "red":       "#f04040",
    "purple":    "#9060f0",
    "yellow":    "#e8c040",
    "cyan":      "#30c8e8",
    "teal":      "#20a890",
    "selection": "#1a3a60",
    "hl":        "#0d2240",
}

APP_NAME = "CodeHub"
MAKER_NAME = "Macro Maker"
GITHUB_REPO = "Catchallcat5382/CodeHub"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
GITHUB_EXE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/CodeHub.exe"
BUILD_COMMIT = "local-build"
if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
    if APP_ROOT.name == ".codehub_runtime":
        APP_ROOT = APP_ROOT.parent
    USER_ROOT = Path(os.environ.get("LOCALAPPDATA", str(APP_ROOT))) / APP_NAME
else:
    APP_ROOT = Path(__file__).resolve().parent
    USER_ROOT = APP_ROOT
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_ROOT = Path(sys._MEIPASS)
else:
    BUNDLE_ROOT = APP_ROOT
ASSET_DIR = BUNDLE_ROOT / "assets"
DATA_DIR = USER_ROOT / "data"
EXPORT_DIR = USER_ROOT / "exports"
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
    "review_capture_fps": 60,
    "review_capture_interval_ms": 1000 // 60,
    "auto_update": False,
    "last_update_sha": "",
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


def hide_console_if_present():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def startup_console():
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        os.system("color 0A")
        os.system(f"title {APP_NAME} Loader")
    except Exception:
        pass
    lines = [
        "[BOOT] CodeHub package loader",
        "[PY] unpacking embedded Python runtime and Tk UI packages",
        "[PY] loading pynput, pillow, mss, psutil, requests",
        "[CACHE] preparing LocalAppData JSON cache",
        "[GIT] public update channel armed",
        "[PACK] mounting embedded assets and compiled source",
        "[UI] waiting for every package before showing CodeHub",
        "[SAFE] paths, names, and IPs are redacted in loader output",
        "[READY] package load complete; opening interface",
        "[NOTE] Do NOT close this console window while CodeHub is running. It will close CodeHub if you do.",
    ]
    total = len(lines)
    for i, line in enumerate(lines, 1):
        print(line, flush=True)
        width = 28
        done = int(width * i / total)
        bar = "#" * done + "-" * (width - done)
        print(f"[LOAD] [{bar}] {int(i * 100 / total):3d}% packages ready", flush=True)
        time.sleep(0.025)


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
        "Key.space": "Space", "Key.enter": "Enter", "Key.tab": "Tab",
        "Key.backspace": "Backspace", "Key.delete": "Delete",
        "Key.esc": "Escape", "Key.escape": "Escape",
        "Key.up": "Up", "Key.down": "Down", "Key.left": "Left", "Key.right": "Right",
        "Key.home": "Home", "Key.end": "End",
        "Key.page_up": "PgUp", "Key.page_down": "PgDn",
        "Key.shift": "Shift", "Key.shift_l": "LShift", "Key.shift_r": "RShift",
        "Key.ctrl": "Ctrl", "Key.ctrl_l": "LCtrl", "Key.ctrl_r": "RCtrl",
        "Key.alt": "Alt", "Key.alt_l": "LAlt", "Key.alt_r": "RAlt",
        "Key.cmd": "LWin", "Key.cmd_l": "LWin", "Key.cmd_r": "RWin",
        "Key.caps_lock": "CapsLock", "Key.num_lock": "NumLock",
        "Key.insert": "Insert", "Key.print_screen": "PrintScreen",
        "Key.f1": "F1",  "Key.f2": "F2",  "Key.f3": "F3",  "Key.f4": "F4",
        "Key.f5": "F5",  "Key.f6": "F6",  "Key.f7": "F7",  "Key.f8": "F8",
        "Key.f9": "F9",  "Key.f10": "F10","Key.f11": "F11","Key.f12": "F12",
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
                "type": "mouse_click", "x": x, "y": y,
                "button": str(button).replace("Button.", "").lower(),
                "pressed": pressed, "time": self.now(),
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


# ── Custom dialog helper ──────────────────────────────────────────────────────

class StyledDialog(Toplevel):
    """Base class for all custom dialogs — dark themed, no default chrome."""
    def __init__(self, parent, title, width=480, height=280):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        # Center over parent
        parent.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - width // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - height // 2
        self.geometry(f"{width}x{height}+{max(0,px)}+{max(0,py)}")
        # Header strip
        hdr = Frame(self, bg=C["panel"], height=44)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        ttk.Label(hdr, text=title, style="DialogTitle.TLabel").pack(side=LEFT, padx=16, pady=10)
        # Body
        self.body = Frame(self, bg=C["bg"], padx=20, pady=16)
        self.body.pack(fill=BOTH, expand=True)

    def btn_row(self):
        row = Frame(self.body, bg=C["bg"])
        row.pack(fill=X, pady=(12, 0))
        return row


class SaveRecordingDialog:
    def __init__(self, parent, default_name, default_export):
        self.result = None
        self.window = StyledDialog(parent, "Save Recording", 500, 270)
        self.name_var = StringVar(value=default_name)
        self.export_var = StringVar(value="Default")
        b = self.window.body
        ttk.Label(b, text="Save this macro", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(b, text=f"Default export folder: {default_export}", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        ttk.Label(b, text="Macro name", style="FieldLabel.TLabel").pack(anchor="w")
        name_e = ttk.Entry(b, textvariable=self.name_var, style="Dark.TEntry")
        name_e.pack(fill=X, pady=(4, 10))
        ttk.Label(b, text="Create script as", style="FieldLabel.TLabel").pack(anchor="w")
        ttk.Combobox(b, textvariable=self.export_var, values=["Default", "AutoHotkey v2", "Python"],
                     state="readonly", style="Dark.TCombobox").pack(fill=X, pady=(4, 0))
        row = self.window.btn_row()
        ttk.Button(row, text="Cancel", style="Ghost.TButton", command=self.cancel).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(row, text="Save Macro", style="Accent.TButton", command=self.accept).pack(side=RIGHT)
        self.window.bind("<Return>", lambda _: self.accept())
        self.window.bind("<Escape>", lambda _: self.cancel())
        name_e.focus_set()
        self.window.wait_window()

    def accept(self):
        name = safe_name(self.name_var.get())
        if not name:
            messagebox.showerror(APP_NAME, "Give the macro a name.", parent=self.window)
            return
        self.result = {"name": name, "export_kind": self.export_var.get()}
        self.window.destroy()

    def cancel(self):
        self.window.destroy()


# ── Custom title bar ──────────────────────────────────────────────────────────

class TitleBar(Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["panel"], height=50)
        self.app = app
        self.pack_propagate(False)
        self._drag_x = 0
        self._drag_y = 0

        # Logo diamond
        logo_lbl = ttk.Label(self, text="◈", style="Logo.TLabel")
        logo_lbl.pack(side=LEFT, padx=(14, 6), pady=10)

        name_lbl = ttk.Label(self, text="CodeHub", style="AppTitle.TLabel")
        name_lbl.pack(side=LEFT, padx=(0, 4))

        sep_lbl = ttk.Label(self, text="·", style="TitleSep.TLabel")
        sep_lbl.pack(side=LEFT, padx=4)

        sub_lbl = ttk.Label(self, text="Recorder · Scripts · Tools · Automation", style="AppSub.TLabel")
        sub_lbl.pack(side=LEFT)

        # Window controls (right side)
        Frame(self, bg=C["panel"], width=10).pack(side=RIGHT)

        close_btn = self._wbtn("✕", C["red"], self.app.close)
        close_btn.pack(side=RIGHT, padx=2, pady=10)

        max_btn = self._wbtn("⬜", C["green"], self._toggle_max)
        max_btn.pack(side=RIGHT, padx=2, pady=10)

        min_btn = self._wbtn("─", C["yellow"], self.app.minimize_window)
        min_btn.pack(side=RIGHT, padx=2, pady=10)

        Frame(self, bg=C["panel"], width=10).pack(side=RIGHT)

        # Hotkey pills
        for txt, col in [("F9 Exit", C["red"]), ("F2 Stop", C["orange"]), ("F1 Record", C["green"])]:
            pill = ttk.Label(self, text=txt, style="Pill.TLabel",
                             foreground=col, background=C["panel"])
            pill.pack(side=RIGHT, padx=4, pady=14)

        Frame(self, bg=C["border"], width=1).pack(side=RIGHT, fill=Y, pady=8)
        Frame(self, bg=C["panel"], width=6).pack(side=RIGHT)

        # Status var display
        self.status_var = None  # set later

        # Drag bindings on all children
        for widget in [self, logo_lbl, name_lbl, sep_lbl, sub_lbl]:
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
            widget.bind("<Double-Button-1>", lambda _e: self._toggle_max())

    def _wbtn(self, sym, hover_col, cmd):
        btn = ttk.Label(self, text=sym, style="WinBtn.TLabel", cursor="hand2")
        btn.bind("<Button-1>", lambda _e: cmd())
        btn.bind("<Enter>", lambda _e, b=btn, col=hover_col: b.configure(foreground=col))
        btn.bind("<Leave>", lambda _e, b=btn: b.configure(foreground=C["text2"]))
        return btn

    def _toggle_max(self):
        root = self.winfo_toplevel()
        if root.state() == "zoomed":
            root.state("normal")
        else:
            root.state("zoomed")

    def _start_drag(self, event):
        self._drag_x = event.x_root
        self._drag_y = event.y_root

    def _do_drag(self, event):
        root = self.winfo_toplevel()
        if root.state() == "zoomed":
            return
        dx = event.x_root - self._drag_x
        dy = event.y_root - self._drag_y
        x = root.winfo_x() + dx
        y = root.winfo_y() + dy
        root.geometry(f"+{x}+{y}")
        self._drag_x = event.x_root
        self._drag_y = event.y_root


# ── Status bar ────────────────────────────────────────────────────────────────

class StatusBar(Frame):
    def __init__(self, parent, status_var):
        super().__init__(parent, bg=C["panel"], height=28)
        self.pack_propagate(False)
        Frame(self, bg=C["accent"], width=3).pack(side=LEFT, fill=Y)
        self._dot = ttk.Label(self, text="●", style="StatusDot.TLabel", foreground=C["text3"])
        self._dot.pack(side=LEFT, padx=(10, 4))
        self._lbl = ttk.Label(self, textvariable=status_var, style="StatusText.TLabel")
        self._lbl.pack(side=LEFT)
        # right side info
        self._info = ttk.Label(self, text="F1 Record · F2 Stop · F9 Exit", style="StatusRight.TLabel")
        self._info.pack(side=RIGHT, padx=14)

    def set_color(self, color):
        self._dot.configure(foreground=color)


# ── Main App ──────────────────────────────────────────────────────────────────

class CodeHubApp:
    def __init__(self):
        ensure_files()
        self.settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        self.recordings = read_json(RECORDINGS_PATH, {"recordings": []})
        self.knowledge = read_json(KNOWLEDGE_PATH, DEFAULT_KNOWLEDGE)
        set_windows_app_id()

        self.root = Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.geometry(self.center_geometry(1120, 720))
        self.root.minsize(860, 540)
        self.root.resizable(True, True)
        self.root.configure(bg=C["bg"])
        self.root.overrideredirect(True)

        # Try to load assets
        self.logo_image = None
        self.logo_small = None
        logo_path = ASSET_DIR / "CodeHub Logo transparent.png"
        if not logo_path.exists():
            logo_path = ASSET_DIR / "CodeHub Logo.png"
        icon_path = ASSET_DIR / "CodeHub Logo.ico"
        if logo_path.exists():
            try:
                self.logo_image = PhotoImage(file=str(logo_path))
                self.logo_small = self.logo_image.subsample(26, 26)
                self.root.iconphoto(True, self.logo_image)
            except Exception:
                pass
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # State vars
        self.is_recording = False
        self.current_editor_file = None
        self.recorder = Recorder(self.on_event)
        self.fullscreen = BooleanVar(value=False)
        self.mode = StringVar(value="normal")
        self.default_export_kind = StringVar(value=self.settings.get("default_export_kind", "AutoHotkey v2"))
        self.export_dir_var = StringVar(value=self.settings.get("export_dir", str(EXPORT_DIR)))
        self.status = StringVar(value="Ready")
        self.ai_can_edit = BooleanVar(value=bool(self.settings.get("ai_can_edit", False)))
        self.ai_can_delete = BooleanVar(value=bool(self.settings.get("ai_can_delete", False)))
        self.ai_can_run = BooleanVar(value=bool(self.settings.get("ai_can_run", False)))
        self.ui_font_size = StringVar(value=str(self.settings.get("ui_font_size", 9)))
        self.ui_density = StringVar(value=self.settings.get("ui_density", "compact"))
        self.record_screenshots = BooleanVar(value=bool(self.settings.get("record_screenshots", True)))
        self.auto_update = BooleanVar(value=bool(self.settings.get("auto_update", False)))
        self.review_fps = StringVar(value=str(self.settings.get("review_capture_fps", 60)))
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
        self._capture_busy = False
        self.ai_pending_path = None
        self.ai_pending_text = ""
        self.ai_undo_stack = []

        self._configure_styles()
        self._build()
        self.start_hotkeys()
        self.start_auto_refresh()
        self.root.bind("<Map>", self.restore_borderless_after_minimize)
        self.root.after(100, self.show_ready_window)
        if self.auto_update.get():
            self.root.after(1200, lambda: self.check_for_updates(auto=True))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def show_ready_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.update_idletasks()
        self.force_taskbar_icon()
        self.root.after(150, hide_console_if_present)

    def center_geometry(self, width, height):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(20, int((screen_w - width) / 2))
        y = max(20, int((screen_h - height) / 2))
        return f"{width}x{height}+{x}+{y}"

    def restore_borderless_after_minimize(self, _event=None):
        if self.root.state() == "normal":
            self.root.after(20, self.restore_window_style)

    def restore_window_style(self):
        try:
            self.root.overrideredirect(True)
            self.force_taskbar_icon()
        except Exception:
            pass

    def minimize_window(self):
        self.root.overrideredirect(False)
        self.root.iconify()

    def force_taskbar_icon(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            gwl_exstyle = -20
            ws_ex_appwindow = 0x00040000
            ws_ex_toolwindow = 0x00000080
            style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
            style = (style | ws_ex_appwindow) & ~ws_ex_toolwindow
            ctypes.windll.user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        except Exception:
            pass

    # ── Styles ────────────────────────────────────────────────────────────────

    def _configure_styles(self):
        s = ttk.Style()
        s.theme_use("clam")
        F = ("Segoe UI", 9)
        FB = ("Segoe UI", 9, "bold")
        FM = ("Segoe UI", 11, "bold")
        FL = ("Segoe UI", 14, "bold")
        FC = ("Consolas", 9)

        # Base
        s.configure(".", background=C["bg"], foreground=C["text"], font=F,
                     fieldbackground=C["panel2"], troughcolor=C["panel"],
                     selectbackground=C["selection"], selectforeground=C["text"],
                     borderwidth=0, relief="flat")
        s.configure("TFrame", background=C["bg"])
        s.configure("TLabel", background=C["bg"], foreground=C["text"], font=F)

        # Title bar labels
        s.configure("Logo.TLabel", background=C["panel"], foreground=C["accent"],
                     font=("Segoe UI", 18, "bold"))
        s.configure("AppTitle.TLabel", background=C["panel"], foreground=C["text"],
                     font=("Segoe UI", 13, "bold"))
        s.configure("TitleSep.TLabel", background=C["panel"], foreground=C["text3"], font=FM)
        s.configure("AppSub.TLabel", background=C["panel"], foreground=C["text2"], font=F)
        s.configure("WinBtn.TLabel", background=C["panel"], foreground=C["text2"],
                     font=("Segoe UI", 11, "bold"), padding=(6, 0))
        s.configure("Pill.TLabel", background=C["panel"], font=("Consolas", 8, "bold"),
                     padding=(6, 2), relief="flat")
        s.configure("DialogTitle.TLabel", background=C["panel"], foreground=C["text"],
                     font=FM)

        # Status bar
        s.configure("StatusDot.TLabel", background=C["panel"], font=("Segoe UI", 14))
        s.configure("StatusText.TLabel", background=C["panel"], foreground=C["text2"], font=F)
        s.configure("StatusRight.TLabel", background=C["panel"], foreground=C["text3"],
                     font=("Consolas", 8))

        # Section / field labels
        s.configure("SectionTitle.TLabel", background=C["bg"], foreground=C["text"], font=FM)
        s.configure("SectionTitle2.TLabel", background=C["panel2"], foreground=C["text"], font=FM)
        s.configure("FieldLabel.TLabel", background=C["bg"], foreground=C["text2"], font=F)
        s.configure("Muted.TLabel", background=C["bg"], foreground=C["text2"], font=F)
        s.configure("PanelMuted.TLabel", background=C["panel"], foreground=C["text2"], font=F)
        s.configure("PanelLabel.TLabel", background=C["panel2"], foreground=C["text"], font=F)
        s.configure("PanelMuted2.TLabel", background=C["panel2"], foreground=C["text2"], font=F)
        s.configure("Accent.TLabel", background=C["bg"], foreground=C["accent"], font=FB)
        s.configure("Green.TLabel", background=C["bg"], foreground=C["green"], font=FB)
        s.configure("Red.TLabel", background=C["bg"], foreground=C["red"], font=FB)

        # Notebook
        s.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab", background=C["panel"], foreground=C["text2"],
                     font=FB, padding=[16, 8], borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", C["bg2"])],
              foreground=[("selected", C["accent"])])

        # Buttons
        s.configure("TButton", background=C["accent2"], foreground="#ffffff",
                     font=FB, padding=(10, 5), borderwidth=0, relief="flat")
        s.map("TButton",
              background=[("active", C["accent"]), ("disabled", C["panel"])],
              foreground=[("disabled", C["text3"])])
        s.configure("Accent.TButton", background=C["accent2"], foreground="#ffffff",
                     font=FB, padding=(10, 5), borderwidth=0)
        s.map("Accent.TButton", background=[("active", C["accent"])])
        s.configure("Green.TButton", background=C["green2"], foreground="#ffffff",
                     font=FB, padding=(10, 5), borderwidth=0)
        s.map("Green.TButton", background=[("active", C["green"])])
        s.configure("Red.TButton", background="#3a1010", foreground=C["red"],
                     font=FB, padding=(10, 5), borderwidth=0)
        s.map("Red.TButton", background=[("active", "#5a1818")])
        s.configure("Ghost.TButton", background=C["panel2"], foreground=C["text2"],
                     font=F, padding=(10, 5), borderwidth=0)
        s.map("Ghost.TButton",
              background=[("active", C["border2"])],
              foreground=[("active", C["text"])])
        s.configure("Small.TButton", background=C["panel2"], foreground=C["text2"],
                     font=("Segoe UI", 8), padding=(6, 3), borderwidth=0)
        s.map("Small.TButton", background=[("active", C["border"])])

        # Entry / combobox
        s.configure("Dark.TEntry", fieldbackground=C["panel2"], foreground=C["text"],
                     insertcolor=C["text"], borderwidth=1, relief="flat",
                     padding=(8, 5))
        s.configure("TEntry", fieldbackground=C["panel2"], foreground=C["text"],
                     insertcolor=C["text"], borderwidth=0, padding=(8, 5))
        s.configure("Dark.TCombobox", fieldbackground=C["panel2"], foreground=C["text"],
                     selectbackground=C["panel2"], selectforeground=C["text"],
                     arrowcolor=C["text2"], borderwidth=0, padding=(8, 5))
        s.configure("TCombobox", fieldbackground=C["panel2"], foreground=C["text"],
                     selectbackground=C["panel2"], selectforeground=C["text"],
                     arrowcolor=C["text2"], borderwidth=0, padding=(6, 4))
        s.map("TCombobox",
              fieldbackground=[("readonly", C["panel2"])],
              foreground=[("readonly", C["text"])],
              selectbackground=[("readonly", C["panel2"])],
              selectforeground=[("readonly", C["text"])])
        s.map("Dark.TCombobox",
              fieldbackground=[("readonly", C["panel2"])],
              foreground=[("readonly", C["text"])])

        # Treeview
        s.configure("Treeview", background=C["bg2"], fieldbackground=C["bg2"],
                     foreground=C["text"], rowheight=24, borderwidth=0, font=F)
        s.configure("Treeview.Heading", background=C["panel"], foreground=C["text2"],
                     borderwidth=0, font=FB, padding=(8, 4))
        s.map("Treeview",
              background=[("selected", C["selection"])],
              foreground=[("selected", C["text"])])

        # Scrollbar
        s.configure("Vertical.TScrollbar", background=C["panel2"], troughcolor=C["bg2"],
                     arrowcolor=C["text3"], borderwidth=0, width=8)
        s.configure("Horizontal.TScrollbar", background=C["panel2"], troughcolor=C["bg2"],
                     arrowcolor=C["text3"], borderwidth=0, width=8)

        # Checkbutton
        s.configure("TCheckbutton", background=C["bg"], foreground=C["text2"], font=F)
        s.map("TCheckbutton", background=[("active", C["bg"])], foreground=[("active", C["text"])])

        # Separator
        s.configure("TSeparator", background=C["border"])

        # Lock styles
        s.configure("Lock.TFrame", background="#030608")
        s.configure("LockPanel.TFrame", background=C["panel2"])
        s.configure("LockPanel.TLabel", background=C["panel2"], foreground=C["text"], font=FL)
        s.configure("LockMuted.TLabel", background=C["panel2"], foreground=C["text2"], font=F)

        # PanedWindow
        s.configure("TPanedwindow", background=C["border"])

        # Progressbar
        s.configure("Accent.Horizontal.TProgressbar", troughcolor=C["panel2"],
                     background=C["accent"], borderwidth=0)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        self.title_bar = TitleBar(self.root, self)
        self.title_bar.pack(fill=X, side="top")

        # Top separator line
        Frame(self.root, bg=C["border"], height=1).pack(fill=X)

        # Status bar at bottom
        self.status_bar = StatusBar(self.root, self.status)
        self.status_bar.pack(fill=X, side="bottom")

        Frame(self.root, bg=C["border"], height=1).pack(fill=X, side="bottom")

        # Main body
        body = Frame(self.root, bg=C["bg"])
        body.pack(fill=BOTH, expand=True)

        self.tabs = ttk.Notebook(body)
        self.tabs.pack(fill=BOTH, expand=True, padx=0, pady=0)

        self.tabs.add(self._recorder_tab(), text="  Recorder  ")
        self.tabs.add(self._workspace_tab(), text="  Workspace  ")
        self.tabs.add(self._tools_tab(), text="  Tools  ")
        self.tabs.add(self._review_tab(), text="  Review  ")
        self.tabs.add(self._settings_tab(), text="  Settings  ")

    def _pad_frame(self, parent, bg=None):
        """Return a padded content frame."""
        bg = bg or C["bg"]
        f = Frame(parent, bg=bg, padx=14, pady=12)
        f.pack(fill=BOTH, expand=True)
        return f

    def _section(self, parent, text, bg=None):
        bg = bg or C["bg"]
        row = Frame(parent, bg=bg)
        row.pack(fill=X, pady=(10, 4))
        Frame(row, bg=C["accent"], width=3, height=16).pack(side=LEFT, padx=(0, 8))
        ttk.Label(row, text=text, style="SectionTitle.TLabel").pack(side=LEFT)
        return row

    def _code_box(self, parent, height=14):
        box = ScrolledText(parent, height=height,
                           bg="#060c14", fg=C["cyan"], insertbackground=C["text"],
                           selectbackground=C["selection"], font=("Consolas", 9),
                           relief="flat", bd=0, wrap="none",
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["accent"])
        return box

    def _text_box(self, parent, height=8, fg=None):
        fg = fg or C["text"]
        box = ScrolledText(parent, height=height,
                           bg=C["bg2"], fg=fg, insertbackground=C["text"],
                           selectbackground=C["selection"], font=("Segoe UI", 9),
                           relief="flat", bd=0, wrap="word",
                           highlightthickness=1, highlightbackground=C["border"],
                           highlightcolor=C["accent"])
        return box

    def _btn_row(self, parent, bg=None):
        bg = bg or C["bg"]
        return Frame(parent, bg=bg)

    def _tag_label(self, parent, text, color, bg=None):
        """Small colored badge label."""
        bg = bg or C["panel"]
        lbl = ttk.Label(parent, text=f" {text} ", foreground=color,
                         background=bg, font=("Consolas", 8, "bold"))
        return lbl

    # ── Recorder tab ──────────────────────────────────────────────────────────

    def _recorder_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)

        # Top controls bar
        ctrl = Frame(pad, bg=C["panel2"], padx=12, pady=10)
        ctrl.pack(fill=X, pady=(0, 10))

        # Mode
        ttk.Label(ctrl, text="Mode", style="PanelMuted2.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(ctrl, textvariable=self.mode,
                     values=["normal", "advanced", "minimal"],
                     width=12, state="readonly").grid(row=0, column=1, padx=(0, 16))

        ttk.Label(ctrl, text="Export as", style="PanelMuted2.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Combobox(ctrl, textvariable=self.default_export_kind,
                     values=["AutoHotkey v2", "Python"],
                     width=14, state="readonly").grid(row=0, column=3, padx=(0, 16))

        self.start_button = ttk.Button(ctrl, text="▶  F1  Start Recording",
                                        style="Green.TButton", command=self.start_recording)
        self.stop_button = ttk.Button(ctrl, text="■  F2  Stop & Save",
                                       style="Ghost.TButton", command=self.stop_recording)
        self.stop_button.state(["disabled"])
        self.start_button.grid(row=0, column=4, padx=(8, 6))
        self.stop_button.grid(row=0, column=5, padx=(0, 8))
        ttk.Button(ctrl, text="Re-Export Selected", style="Small.TButton",
                   command=self.export_selected).grid(row=0, column=6)

        # Recording status strip
        self.rec_status_frame = Frame(pad, bg=C["bg2"], height=3)
        self.rec_status_frame.pack(fill=X, pady=(0, 8))

        # Split pane
        panes = ttk.PanedWindow(pad, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)

        left = Frame(panes, bg=C["bg"])
        right = Frame(panes, bg=C["bg"])
        panes.add(left, weight=3)
        panes.add(right, weight=2)

        # Live feed
        self._section(left, "Live Event Feed")
        self.feed = self._code_box(left, height=16)
        self.feed.pack(fill=BOTH, expand=True)

        # Recordings list
        self._section(right, "Saved Recordings")
        rec_box = Frame(right, bg=C["bg"])
        rec_box.pack(fill=BOTH, expand=True)

        self.recording_list = ttk.Treeview(
            rec_box,
            columns=("name", "export", "mode", "events", "file", "created"),
            show="headings", height=12
        )
        rsb = ttk.Scrollbar(rec_box, orient="vertical", command=self.recording_list.yview)
        self.recording_list.configure(yscrollcommand=rsb.set)
        for col, w in [("name", 120), ("export", 100), ("mode", 72), ("events", 60), ("file", 56), ("created", 150)]:
            self.recording_list.heading(col, text=col.title())
            self.recording_list.column(col, width=w, stretch=True)
        self.recording_list.pack(side=LEFT, fill=BOTH, expand=True)
        rsb.pack(side=RIGHT, fill=Y)

        br = Frame(right, bg=C["bg"], pady=6)
        br.pack(fill=X)
        ttk.Button(br, text="Rename", style="Ghost.TButton", command=self.rename_recording).pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        ttk.Button(br, text="Delete", style="Red.TButton", command=self.delete_recording).pack(side=LEFT, fill=X, expand=True)

        self.refresh_recordings()
        return tab

    # ── Workspace tab ─────────────────────────────────────────────────────────

    def _workspace_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)

        panes = ttk.PanedWindow(pad, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)

        files_frame = Frame(panes, bg=C["bg"])
        edit_frame = Frame(panes, bg=C["bg"])
        panes.add(files_frame, weight=1)
        panes.add(edit_frame, weight=3)

        # Files panel
        self._section(files_frame, "Script Files")
        ft_box = Frame(files_frame, bg=C["bg"])
        ft_box.pack(fill=BOTH, expand=True)

        self.file_tree = ttk.Treeview(ft_box, columns=("path", "size"), show="headings", height=18)
        fsb = ttk.Scrollbar(ft_box, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=fsb.set)
        self.file_tree.heading("path", text="Name")
        self.file_tree.heading("size", text="Size")
        self.file_tree.column("path", width=190, stretch=True)
        self.file_tree.column("size", width=60, stretch=False)
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        fsb.pack(side=RIGHT, fill=Y)
        self.file_tree.bind("<Double-1>", lambda _: self.open_selected_file())

        fb1 = Frame(files_frame, bg=C["bg"], pady=4)
        fb1.pack(fill=X)
        ttk.Button(fb1, text="Refresh", style="Ghost.TButton", command=self.refresh_files).pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
        ttk.Button(fb1, text="Open", style="Ghost.TButton", command=self.open_selected_file).pack(side=LEFT, fill=X, expand=True)

        fb2 = Frame(files_frame, bg=C["bg"], pady=0)
        fb2.pack(fill=X)
        ttk.Button(fb2, text="Rename", style="Ghost.TButton", command=self.rename_selected_file).pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
        ttk.Button(fb2, text="Delete", style="Red.TButton", command=self.delete_selected_file).pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
        ttk.Button(fb2, text="Run ▶", style="Green.TButton", command=self.run_selected_file).pack(side=LEFT, fill=X, expand=True)

        # Editor panel
        etop = Frame(edit_frame, bg=C["bg"], pady=4)
        etop.pack(fill=X)
        ttk.Button(etop, text="Open Script", style="Ghost.TButton", command=self.open_script).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Save", style="Accent.TButton", command=self.save_script).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Save As", style="Ghost.TButton", command=self.save_script_as).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Run ▶", style="Green.TButton", command=self.run_open_script).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Notes", style="Small.TButton", command=self.insert_notes).pack(side=LEFT)

        epre = Frame(edit_frame, bg=C["bg"], pady=2)
        epre.pack(fill=X)
        ttk.Label(epre, text="Insert:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Button(epre, text="AHK Hotkeys", style="Small.TButton", command=self.insert_ahk_hotkeys).pack(side=LEFT, padx=(0, 4))
        ttk.Button(epre, text="Python Base", style="Small.TButton", command=self.insert_python_macro_base).pack(side=LEFT, padx=(0, 4))
        ttk.Button(epre, text="JSON Helper", style="Small.TButton", command=self.insert_json_helper).pack(side=LEFT)

        self.editor_path = StringVar(value="No file open")
        path_lbl = ttk.Label(edit_frame, textvariable=self.editor_path, style="Muted.TLabel")
        path_lbl.pack(anchor="w", pady=(4, 2))

        self.editor = self._code_box(edit_frame, height=30)
        self.editor.configure(fg=C["text"])
        self.editor.pack(fill=BOTH, expand=True)
        self.editor.bind("<Tab>", self.editor_autocomplete)

        self.refresh_files()
        return tab

    # ── Tools tab ─────────────────────────────────────────────────────────────

    def _tools_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)

        tool_nb = ttk.Notebook(pad)
        tool_nb.pack(fill=BOTH, expand=True)

        tool_nb.add(self._assistant_tool(tool_nb), text="  Assistant  ")
        tool_nb.add(self._converter_tool(tool_nb), text="  Converter  ")
        tool_nb.add(self._builder_tool(tool_nb), text="  Code Builder  ")
        tool_nb.add(self._position_tool(tool_nb), text="  Position Logger  ")

        return tab

    def _builder_tool(self, parent):
        tab = Frame(parent, bg=C["bg"])
        pad = self._pad_frame(tab)

        self.builder_blocks = []
        self.builder_kind = StringVar(value="Button")
        self.builder_export = StringVar(value="AutoHotkey v2")
        self.builder_text = StringVar(value="Run")
        self.builder_x = StringVar(value="20")
        self.builder_y = StringVar(value="20")
        self.builder_w = StringVar(value="140")
        self.builder_h = StringVar(value="32")

        self._section(pad, "Visual Code Builder")
        ttk.Label(
            pad,
            text="Add UI blocks, preview the layout list, then generate script code into the output or editor.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        controls = Frame(pad, bg=C["panel2"], padx=10, pady=8)
        controls.pack(fill=X, pady=(0, 8))
        for label, var, values, width in [
            ("Block", self.builder_kind, ["Label", "Button", "Input", "Checkbox", "Slider"], 12),
            ("Code", self.builder_export, ["AutoHotkey v2", "Python Tkinter"], 16),
        ]:
            ttk.Label(controls, text=f"{label}:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(0, 4))
            ttk.Combobox(controls, textvariable=var, values=values, state="readonly", width=width).pack(side=LEFT, padx=(0, 8))
        ttk.Label(controls, text="Text:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Entry(controls, textvariable=self.builder_text, width=18).pack(side=LEFT, padx=(0, 8))
        for label, var in [("X", self.builder_x), ("Y", self.builder_y), ("W", self.builder_w), ("H", self.builder_h)]:
            ttk.Label(controls, text=f"{label}:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(0, 3))
            ttk.Entry(controls, textvariable=var, width=5).pack(side=LEFT, padx=(0, 6))

        buttons = Frame(pad, bg=C["bg"], pady=4)
        buttons.pack(fill=X)
        ttk.Button(buttons, text="Add Block", style="Green.TButton", command=self.builder_add_block).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Clear", style="Red.TButton", command=self.builder_clear).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Generate", style="Accent.TButton", command=self.builder_generate).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Send to Editor", style="Ghost.TButton", command=self.builder_send_to_editor).pack(side=LEFT)

        panes = ttk.PanedWindow(pad, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True, pady=(8, 0))
        left = Frame(panes, bg=C["bg"])
        right = Frame(panes, bg=C["bg"])
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        self._section(left, "Blocks")
        self.builder_list = self._code_box(left, height=22)
        self.builder_list.configure(fg=C["cyan"])
        self.builder_list.pack(fill=BOTH, expand=True)

        self._section(right, "Generated Code")
        self.builder_output = self._code_box(right, height=22)
        self.builder_output.configure(fg=C["green"])
        self.builder_output.pack(fill=BOTH, expand=True)
        self.builder_refresh_list()
        return tab

    def _assistant_tool(self, parent):
        tab = Frame(parent, bg=C["bg"])
        pad = self._pad_frame(tab)

        self._section(pad, "AI Script Assistant")
        ttk.Label(pad, text="Pick a script, describe your change, preview the diff, then apply or undo.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        tr = Frame(pad, bg=C["bg"])
        tr.pack(fill=X, pady=(0, 6))
        ttk.Label(tr, text="Target script:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        self.ai_target_var = StringVar(value="")
        self.ai_target_combo = ttk.Combobox(tr, textvariable=self.ai_target_var, values=[], state="readonly")
        self.ai_target_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        ttk.Button(tr, text="Refresh", style="Small.TButton", command=self.refresh_ai_targets).pack(side=LEFT)

        self._section(pad, "Your Request")
        self.helper_question = self._text_box(pad, height=4)
        self.helper_question.pack(fill=X, pady=(4, 0))

        ar = Frame(pad, bg=C["bg"], pady=6)
        ar.pack(fill=X)
        ttk.Button(ar, text="Ask Helper", style="Accent.TButton", command=self.ask_helper).pack(side=LEFT, padx=(0, 6))
        ttk.Button(ar, text="Preview Change", style="Ghost.TButton", command=self.generate_ai_review).pack(side=LEFT, padx=(0, 6))
        ttk.Button(ar, text="Apply Change", style="Green.TButton", command=self.apply_ai_review).pack(side=LEFT, padx=(0, 6))
        ttk.Button(ar, text="↩ Undo", style="Ghost.TButton", command=self.undo_ai_change).pack(side=LEFT, padx=(0, 6))
        ttk.Button(ar, text="Safe Header", style="Small.TButton", command=self.apply_ai_header).pack(side=LEFT)

        self._section(pad, "Response")
        self.helper_answer = self._text_box(pad, height=5, fg=C["cyan"])
        self.helper_answer.pack(fill=X, pady=(4, 0))

        self._section(pad, "Diff Preview")
        self.ai_diff_view = self._code_box(pad, height=8)
        self.ai_diff_view.configure(fg=C["yellow"])
        self.ai_diff_view.pack(fill=BOTH, expand=True, pady=(4, 0))

        self.root.after(100, self.refresh_ai_targets)
        return tab

    def _converter_tool(self, parent):
        tab = Frame(parent, bg=C["bg"])
        pad = self._pad_frame(tab)

        self._section(pad, "Code Converter")
        ttk.Label(pad, text="Convert between Python and AutoHotkey v2 syntax automatically.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        mr = Frame(pad, bg=C["bg"])
        mr.pack(fill=X, pady=(0, 8))
        ttk.Label(mr, text="Direction:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 8))
        self.converter_mode = StringVar(value="Python to AutoHotkey")
        ttk.Combobox(mr, textvariable=self.converter_mode,
                     values=["Python to AutoHotkey", "AutoHotkey to Python"],
                     state="readonly", width=26).pack(side=LEFT)

        self._section(pad, "Input")
        self.converter_input = self._code_box(pad, height=9)
        self.converter_input.pack(fill=BOTH, expand=True, pady=(4, 0))

        cr = Frame(pad, bg=C["bg"], pady=6)
        cr.pack(fill=X)
        ttk.Button(cr, text="Convert ▶", style="Accent.TButton", command=self.convert_code).pack(side=LEFT, padx=(0, 8))
        ttk.Button(cr, text="Send to Editor", style="Ghost.TButton", command=self.apply_converter_output_to_editor).pack(side=LEFT)

        self._section(pad, "Output")
        self.converter_output = self._code_box(pad, height=9)
        self.converter_output.configure(fg=C["green"])
        self.converter_output.pack(fill=BOTH, expand=True, pady=(4, 0))

        return tab

    def _position_tool(self, parent):
        tab = Frame(parent, bg=C["bg"])
        pad = self._pad_frame(tab)

        self._section(pad, "Click Position Logger")
        ttk.Label(pad, text="Records left-click coordinates outside this window while enabled. Use to grab coordinates for your scripts.",
                  style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(0, 10))

        pr = Frame(pad, bg=C["bg"])
        pr.pack(fill=X, pady=(0, 6))
        ttk.Button(pr, text="▶  Start Logging", style="Green.TButton", command=self.start_position_logging).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="■  Stop", style="Ghost.TButton", command=self.stop_position_logging).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="Clear", style="Red.TButton", command=self.clear_position_log).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="Insert into Editor", style="Accent.TButton", command=self.insert_position_log_into_editor).pack(side=LEFT)

        self.position_status = StringVar(value="Stopped  ·  0 clicks")
        ttk.Label(pad, textvariable=self.position_status, style="Accent.TLabel").pack(anchor="w", pady=(0, 6))

        self.position_output = self._code_box(pad, height=24)
        self.position_output.configure(fg=C["green"])
        self.position_output.pack(fill=BOTH, expand=True)

        return tab

    # ── Review tab ────────────────────────────────────────────────────────────

    def _review_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)

        top = Frame(pad, bg=C["panel2"], padx=10, pady=8)
        top.pack(fill=X, pady=(0, 10))

        ttk.Label(top, text="Recording:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(0, 6))
        self.review_recording_var = StringVar(value="")
        self.review_recording_combo = ttk.Combobox(top, textvariable=self.review_recording_var,
                                                    values=[], state="readonly", width=36)
        self.review_recording_combo.pack(side=LEFT, padx=(0, 8))

        for txt, cmd in [("Load", self.load_review_recording), ("▶ Play", self.play_review),
                          ("⏸ Pause", self.pause_review), ("■ Stop", self.stop_visual_replay),
                          ("⏮ Rewind", self.rewind_review)]:
            ttk.Button(top, text=txt, style="Ghost.TButton", command=cmd).pack(side=LEFT, padx=3)

        ttk.Label(top, text="Speed:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(10, 4))
        ttk.Combobox(top, textvariable=self.review_speed,
                     values=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
                     state="readonly", width=6).pack(side=LEFT)

        panes = ttk.PanedWindow(pad, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)

        left = Frame(panes, bg=C["bg"])
        right = Frame(panes, bg=C["bg"])
        panes.add(left, weight=2)
        panes.add(right, weight=3)

        self._section(left, "Replay Stats")
        self.review_output = self._text_box(left, height=10, fg=C["text"])
        self.review_output.pack(fill=BOTH, expand=True)

        self._section(left, "Input Monitor")
        self.virtual_keys = self._code_box(left, height=8)
        self.virtual_keys.pack(fill=BOTH, expand=True, pady=(4, 0))

        self._section(right, "Frame Preview")
        self.review_image_label = ttk.Label(right, text="Load a recording to preview frames.",
                                             anchor="center", background=C["bg2"])
        self.review_image_label.pack(fill=BOTH, expand=True, pady=(4, 8))

        self._section(right, "Event Timeline")
        self.review_timeline = self._code_box(right, height=10)
        self.review_timeline.pack(fill=BOTH, expand=True, pady=(4, 0))

        self.review_events = []
        self.review_replaying = False
        self.refresh_review_options()
        return tab

    # ── Settings tab ─────────────────────────────────────────────────────────

    def _settings_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)

        self._section(pad, "Export Folder")
        er = Frame(pad, bg=C["bg"], pady=4)
        er.pack(fill=X)
        ttk.Entry(er, textvariable=self.export_dir_var).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(er, text="Browse", style="Ghost.TButton", command=self.choose_export_dir).pack(side=RIGHT)

        self._section(pad, "Appearance")
        ar = Frame(pad, bg=C["bg"], pady=4)
        ar.pack(fill=X)
        ttk.Label(ar, text="Font size:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(ar, textvariable=self.ui_font_size, values=["8","9","10","11","12"],
                     state="readonly", width=6).pack(side=LEFT, padx=(0, 12))
        ttk.Label(ar, text="Density:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(ar, textvariable=self.ui_density, values=["compact","comfortable"],
                     state="readonly", width=12).pack(side=LEFT, padx=(0, 12))
        ttk.Button(ar, text="Apply", style="Accent.TButton", command=self.save_ui_settings).pack(side=LEFT)
        ttk.Button(ar, text="Toggle Fullscreen", style="Ghost.TButton", command=self.toggle_fullscreen).pack(side=LEFT, padx=(8, 0))

        self._section(pad, "Updates")
        ur = Frame(pad, bg=C["bg"], pady=4)
        ur.pack(fill=X)
        ttk.Checkbutton(ur, text="Auto update on startup", variable=self.auto_update, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Button(ur, text="Check for Updates", style="Accent.TButton", command=self.check_for_updates).pack(side=LEFT, padx=(0, 8))
        ttk.Button(ur, text="Run Local Updater", style="Ghost.TButton", command=self.run_local_updater).pack(side=LEFT)

        self._section(pad, "Replay Capture")
        rr = Frame(pad, bg=C["bg"], pady=4)
        rr.pack(fill=X)
        ttk.Checkbutton(rr, text="Capture review screenshots while recording", variable=self.record_screenshots, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Label(rr, text="FPS:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(rr, textvariable=self.review_fps, values=["10", "15", "24", "30", "60"],
                     state="readonly", width=6).pack(side=LEFT, padx=(0, 8))
        ttk.Button(rr, text="Save Replay FPS", style="Ghost.TButton", command=self.save_permissions).pack(side=LEFT)

        self._section(pad, "Permissions")
        pr = Frame(pad, bg=C["bg"], pady=4)
        pr.pack(fill=X)
        ttk.Checkbutton(pr, text="Allow assistant to edit the open script", variable=self.ai_can_edit, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(pr, text="Allow assistant to delete selected files", variable=self.ai_can_delete, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(pr, text="Allow assistant to run script commands", variable=self.ai_can_run, command=self.save_permissions).pack(anchor="w", pady=2)

        self._section(pad, "Data Paths")
        info = self._text_box(pad, height=8, fg=C["text2"])
        info.pack(fill=BOTH, expand=True, pady=(4, 0))
        info.insert(END, f"Settings  : {SETTINGS_PATH}\n")
        info.insert(END, f"Recordings: {RECORDINGS_PATH}\n")
        info.insert(END, f"Knowledge : {KNOWLEDGE_PATH}\n")
        info.insert(END, f"Exports   : {self.export_dir_var.get()}\n\n")
        info.insert(END, "Generated scripts include comments for hotkeys, editing, and watermark removal.\n")
        info.insert(END, "All recordings persist as JSON — they survive app restarts.\n")
        info.configure(state="disabled")
        return tab

    # ═══════════════════════════════════════════════════════════════════════════
    # All the original logic methods — completely unchanged
    # ═══════════════════════════════════════════════════════════════════════════

    def start_hotkeys(self):
        def on_press(key):
            if key == Key.f9:
                self.root.after(0, self.close)
                return
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
        if self.macro_locked or self.is_recording:
            return
        self.is_recording = True
        self.review_shots = []
        self.feed.delete("1.0", END)
        self.settings["default_export_kind"] = self.default_export_kind.get()
        write_json(SETTINGS_PATH, self.settings)
        self.feed.insert(END, f"▶  Recording started — mode: {self.mode.get()} — export: {self.default_export_kind.get()}\n")
        self.status.set("● Recording")
        self.status_bar.set_color(C["red"])
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        self.rec_status_frame.configure(bg=C["red"])
        self.recorder.start(self.mode.get())
        self.capture_review_snapshot("start")
        fps = self.builder_number(self.review_fps.get(), int(self.settings.get("review_capture_fps", 60)))
        self.root.after(max(16, int(1000 / max(1, fps))), self.capture_review_tick)

    def stop_recording(self):
        if self.macro_locked or not self.is_recording:
            return
        self.is_recording = False
        self.capture_review_snapshot("stop")
        events = self.recorder.stop()
        self.rec_status_frame.configure(bg=C["border"])
        self.status_bar.set_color(C["text3"])
        default_name = self.settings.get("default_script_name", "MyMacro")
        dialog = SaveRecordingDialog(self.root, default_name, self.default_export_kind.get())
        self.start_button.state(["!disabled"])
        self.stop_button.state(["disabled"])
        if not dialog.result:
            self.status.set(f"Discarded  ({len(events)} events)")
            self.feed.insert(END, "■  Stopped — discarded (save cancelled)\n")
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
        self.status.set(f"Saved  {record['name']}  ·  {len(events)} events")
        self.feed.insert(END, f"■  Stopped — saved '{record['name']}' ({len(events)} events) as {export_kind}\n")
        self.refresh_recordings()
        self.export_recording(record, export_kind)

    def on_event(self, event):
        self.root.after(0, lambda: self.feed.insert(END, event_line(event) + "\n"))

    def capture_review_snapshot(self, label):
        if not self.record_screenshots.get():
            return
        if self._capture_busy:
            return

        def worker():
            self._capture_busy = True
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
                    image.save(path, optimize=True)
                self.review_shots.append(str(path))
            except Exception:
                pass
            finally:
                self._capture_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def capture_review_tick(self):
        if not self.is_recording:
            return
        self.capture_review_snapshot("tick")
        fps = self.builder_number(self.review_fps.get(), int(self.settings.get("review_capture_fps", 60)))
        interval = max(16, int(1000 / max(1, fps)))
        self.root.after(interval, self.capture_review_tick)

    def refresh_recordings(self):
        if not hasattr(self, "recording_list"):
            return
        old_focus = self.recording_list.focus()
        old_sel = self.recording_list.selection()
        self.recordings = read_json(RECORDINGS_PATH, {"recordings": []})
        self._last_recordings_signature = json.dumps(self.recordings, sort_keys=True)
        try:
            self._last_recordings_mtime = RECORDINGS_PATH.stat().st_mtime
        except OSError:
            self._last_recordings_mtime = None
        for row in self.recording_list.get_children():
            self.recording_list.delete(row)
        for i, rec in enumerate(self.recordings.get("recordings", [])):
            self.recording_list.insert("", END, iid=str(i), values=(
                rec.get("name"),
                rec.get("export_kind", "AutoHotkey v2"),
                rec.get("mode"),
                len(rec.get("events", [])),
                "Missing" if rec.get("export_missing") else "OK",
                rec.get("created"),
            ))
        if old_focus and self.recording_list.exists(old_focus):
            self.recording_list.focus(old_focus)
            self.recording_list.selection_set(old_sel or (old_focus,))
        self.refresh_review_options()

    def selected_recording(self):
        sel = self.recording_list.selection()
        item = sel[0] if sel else self.recording_list.focus()
        if not item:
            messagebox.showinfo(APP_NAME, "Select a recording first.")
            return None, None
        idx = int(item)
        return idx, self.recordings["recordings"][idx]

    def selected_review_recording(self):
        value = self.review_recording_var.get() if hasattr(self, "review_recording_var") else ""
        if value:
            try:
                idx = int(value.split(":", 1)[0])
                return idx, self.recordings["recordings"][idx]
            except Exception:
                pass
        return self.selected_recording()

    def refresh_review_options(self):
        if not hasattr(self, "review_recording_combo"):
            return
        values = [
            f"{i}: {rec.get('name','macro')} ({len(rec.get('events',[]))} events)"
            for i, rec in enumerate(self.recordings.get("recordings", []))
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
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
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
        idx, rec = self.selected_recording()
        if rec is None:
            return
        if messagebox.askyesno(APP_NAME, f"Delete cached recording '{rec.get('name')}'?"):
            ep = Path(rec.get("export_path", ""))
            if ep.exists() and messagebox.askyesno(APP_NAME, "Also delete the exported script file?"):
                try:
                    ep.unlink()
                except Exception as e:
                    messagebox.showerror(APP_NAME, f"Could not delete:\n{e}")
            self.recordings["recordings"].pop(idx)
            write_json(RECORDINGS_PATH, self.recordings)
            self.refresh_recordings()
            self.refresh_files()

    def rename_recording(self):
        idx, rec = self.selected_recording()
        if rec is None:
            return
        dialog = SaveRecordingDialog(self.root, rec.get("name","macro"), rec.get("export_kind", self.default_export_kind.get()))
        if not dialog.result:
            return
        export_kind = dialog.result["export_kind"]
        if export_kind == "Default":
            export_kind = self.default_export_kind.get()
        rec["name"] = dialog.result["name"]
        rec["export_kind"] = export_kind
        self.recordings["recordings"][idx] = rec
        write_json(RECORDINGS_PATH, self.recordings)
        self.refresh_recordings()

    def refresh_files(self):
        if not hasattr(self, "file_tree"):
            return
        old_focus = self.file_tree.focus()
        old_sel = self.file_tree.selection()
        for row in self.file_tree.get_children():
            self.file_tree.delete(row)
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        files = sorted([p for p in export_dir.iterdir() if p.is_file() and p.suffix.lower() in {".py",".ahk",".txt"}])
        self._last_file_snapshot = {f"{p}|{p.stat().st_mtime}|{p.stat().st_size}" for p in files}
        for p in files:
            self.file_tree.insert("", END, iid=str(p), values=(p.name, format_size(p.stat().st_size)))
        if old_focus and self.file_tree.exists(old_focus):
            self.file_tree.focus(old_focus)
            self.file_tree.selection_set(old_sel or (old_focus,))
        if self.sync_recording_exports(files):
            self.refresh_recordings()
        self.refresh_ai_targets()

    def sync_recording_exports(self, files):
        records = self.recordings.get("recordings", [])
        changed = False
        stems = {p.stem.lower(): p for p in files}
        linked_paths = set()
        for rec in records:
            current = Path(rec.get("export_path",""))
            if rec.get("export_path") and current.exists():
                linked_paths.add(str(current))
                if rec.get("name") != current.stem:
                    rec["name"] = current.stem
                    changed = True
                if rec.get("export_missing"):
                    rec["export_missing"] = False
                    changed = True
                continue
            expected = safe_name(rec.get("name","")).lower()
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
        missing_records = [r for r in records if r.get("export_missing")]
        unlinked_files = [p for p in files if str(p) not in linked_paths]
        if len(missing_records) == 1 and len(unlinked_files) == 1:
            rec = missing_records[0]
            p = unlinked_files[0]
            rec["name"] = p.stem
            rec["export_path"] = str(p)
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
            f"{p}|{p.stat().st_mtime}|{p.stat().st_size}"
            for p in export_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".py",".ahk",".txt"}
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
        total_time = max([float(e.get("time",0)) for e in self.review_events] or [0])
        presses = [e for e in self.review_events if e.get("type") in ("key_press","key_char")]
        clicks = [e for e in self.review_events if e.get("type") == "mouse_click" and e.get("pressed")]
        self.review_output.delete("1.0", END)
        self.review_output.insert(END, f"Macro : {rec.get('name')}\n")
        self.review_output.insert(END, f"Mode  : {rec.get('mode')}  ·  {len(self.review_events)} events  ·  {total_time:.2f}s\n")
        self.review_output.insert(END, f"Keys  : {len(presses)} presses  ·  {len(clicks)} clicks\n")
        if self.review_shot_paths:
            self.review_output.insert(END, f"Frames: {len(self.review_shot_paths)} screenshots\n")
            self.show_review_frame(0)
        else:
            self.review_output.insert(END, "\nNo screenshots saved for this recording.\n")
            self.review_image_label.configure(image="", text="No captured frames.")
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
            self.review_image_label.configure(text=f"Frame {index+1}/{len(self.review_shot_paths)}\n{path}", image="")
            return
        try:
            img = Image.open(path).convert("RGB")
            max_w = max(360, self.review_image_label.winfo_width() or 640)
            max_h = max(240, self.review_image_label.winfo_height() or 360)
            img.thumbnail((max_w, max_h))
            self.review_photo = ImageTk.PhotoImage(img)
            self.review_image_label.configure(image=self.review_photo,
                                               text=f"Frame {index+1}/{len(self.review_shot_paths)}",
                                               compound="top")
        except Exception as e:
            self.review_image_label.configure(text=f"Could not load frame:\n{e}", image="")

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
        self.set_virtual_keys("Rewound. Press Play.\n")

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
            text = f"Time: {t:.2f}s  ·  Speed: {speed:.2f}x  ·  Rate: {event_speed:.1f}/sec\n"
            text += f"Event: {event_line(event)}\n"
            text += "Held: " + (", ".join(sorted(active)) if active else "none") + "\n"
            self.root.after(0, lambda v=text: self.set_virtual_keys(v))
            if self.review_shot_paths:
                fi = min(len(self.review_shot_paths)-1,
                         int((t / max(0.1, self.review_events[-1].get("time",0.1))) * len(self.review_shot_paths)))
                if fi != last_frame_index:
                    last_frame_index = fi
                    self.root.after(0, lambda idx=fi: self.show_review_frame(idx))
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
        p = self.selected_file_path()
        if p:
            self.load_script(p)

    def run_selected_file(self):
        p = self.selected_file_path()
        if p:
            self.run_script(p)

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
                proc = subprocess.Popen(
                    pythonw_command() + [str(path)], cwd=str(path.parent),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags())
            elif path.suffix.lower() == ".ahk":
                ahk = find_ahk_exe()
                if ahk:
                    proc = subprocess.Popen(
                        [ahk, str(path)], cwd=str(path.parent),
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=hidden_process_flags())
                else:
                    messagebox.showwarning(APP_NAME, "AutoHotkey not found. Opening file normally.")
                    proc = subprocess.Popen(
                        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                         f"Start-Process -FilePath {json.dumps(str(path))} -Wait"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=hidden_process_flags())
            else:
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                     f"Start-Process -FilePath {json.dumps(str(path))} -Wait"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags())
            self.status.set(f"Running  {path.name}")
            self.lock_for_macro(proc, path.name)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not run script:\n{e}")

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
        self.external_macro_paths = {str(p) for p in paths}
        label = ", ".join(sorted(Path(p).name for p in self.external_macro_paths)) or "external macro"
        self.status.set(f"Detected: {label}")
        self.show_lock_overlay(label)
        self.root.after(900, self.poll_macro_process)

    def show_lock_overlay(self, label):
        if self.lock_overlay and self.lock_overlay.winfo_exists():
            return
        overlay = Frame(self.root, bg="#030608")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.bind("<Button>", lambda _: "break")
        overlay.bind("<Key>", lambda _: "break")
        self.root.update_idletasks()
        panel = Frame(overlay, bg=C["panel2"], padx=32, pady=28)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(panel, text="LOCKED", style="LockPanel.TLabel").pack()
        ttk.Label(panel, text=f"Running: {label}\n\nClose the macro to continue.",
                  style="LockMuted.TLabel", justify="center").pack(pady=(10,0))
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
            active = {pid for pid, _ in running}
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
        self.status.set("Ready")

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
            self.root.after(0, lambda v=running: self.finish_external_macro_scan(v))
        threading.Thread(target=scan, daemon=True).start()

    def finish_external_macro_scan(self, running):
        self._process_scan_running = False
        if running and not self.macro_locked:
            self.lock_for_external_macro({pid for pid, _ in running}, {path for _, path in running})

    def export_script_paths(self):
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        paths = [p.resolve() for p in export_dir.iterdir() if p.is_file() and p.suffix.lower() in {".py",".ahk",".exe"}]
        for rec in self.recordings.get("recordings", []):
            try:
                p = Path(rec.get("export_path","")).resolve()
                if p.exists():
                    paths.append(p)
            except Exception:
                pass
        return sorted(set(paths))

    def process_snapshot(self):
        if os.name != "nt":
            return []
        command = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True, text=True, timeout=3, creationflags=hidden_process_flags())
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
        target_text = {str(p).lower(): p for p in targets}
        own_pid = os.getpid()
        found = []
        for proc in self.process_snapshot():
            try:
                pid = int(proc.get("ProcessId", 0))
            except Exception:
                continue
            if not pid or pid == own_pid:
                continue
            cl = str(proc.get("CommandLine") or "")
            exe = str(proc.get("ExecutablePath") or "")
            haystack = f"{cl} {exe}".lower()
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
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not delete:\n{e}")
                return
            if self.current_editor_file == path:
                self.current_editor_file = None
                self.editor.delete("1.0", END)
                self.editor_path.set("No file open")
            self.refresh_files()

    def open_script(self):
        path = filedialog.askopenfilename(
            initialdir=str(resolve_app_path(self.export_dir_var.get())),
            filetypes=[("Scripts", "*.py *.ahk *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.load_script(Path(path))

    def load_script(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            self.editor.delete("1.0", END)
            self.editor.insert(END, f.read())
        self.current_editor_file = Path(path)
        self.editor_path.set(str(path))
        self.tabs.select(1)

    def save_script(self):
        if not self.current_editor_file:
            self.save_script_as()
            return
        with open(self.current_editor_file, "w", encoding="utf-8") as f:
            f.write(self.editor.get("1.0", END))
        self.editor_path.set(str(self.current_editor_file))
        self.refresh_files()
        messagebox.showinfo(APP_NAME, f"Saved:\n{self.current_editor_file}")

    def save_script_as(self):
        path = filedialog.asksaveasfilename(
            initialdir=str(resolve_app_path(self.export_dir_var.get())),
            filetypes=[("Scripts", "*.py *.ahk *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.current_editor_file = Path(path)
        self.save_script()

    def insert_notes(self):
        prefix = ";" if self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk" else "#"
        self.editor.insert(END,
            f"\n{prefix} CodeHub notes\n"
            f"{prefix} F1 starts, F2 stops, Numpad 5 exits generated scripts.\n"
            f"{prefix} Remove the watermark function/class if you do not want the overlay.\n"
            f"{prefix} JSON saves are in the data/ folder next to this app.\n")

    def insert_ahk_hotkeys(self):
        self.editor.insert(END,
            '\n; AHK v2 hotkey skeleton\nglobal running := false\n'
            'F1::{\n    global running\n    running := true\n}\n'
            'F2::{\n    global running\n    running := false\n}\n'
            'Numpad5::ExitApp\n')

    def insert_python_macro_base(self):
        self.editor.insert(END,
            '\n# Python macro skeleton\nimport time\n'
            'from pynput.keyboard import Controller as KeyboardController\n'
            'from pynput.mouse import Controller as MouseController\n\n'
            'keys = KeyboardController()\nmouse = MouseController()\n\n'
            'def wait(seconds):\n    """Delay between actions so playback feels human."""\n    time.sleep(seconds)\n')

    def insert_json_helper(self):
        self.editor.insert(END,
            '\n# JSON helper\nimport json\nfrom pathlib import Path\n\n'
            'def load_json(path, fallback):\n    path = Path(path)\n    if not path.exists():\n        return fallback\n'
            '    with open(path, "r", encoding="utf-8") as f:\n        return json.load(f)\n\n'
            'def save_json(path, data):\n    path = Path(path)\n    path.parent.mkdir(parents=True, exist_ok=True)\n'
            '    with open(path, "w", encoding="utf-8") as f:\n        json.dump(data, f, indent=2)\n')

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
        if any(k in question for k in ("hotkey","f1","f2","numpad")):
            answers.append("Generated scripts use F1 start, F2 stop, and Numpad 5 exit.")
        if any(k in question for k in ("json","save","cache")):
            answers.append(f"Recordings: {RECORDINGS_PATH}  ·  Settings: {SETTINGS_PATH}")
        if any(k in question for k in ("game","roblox","currency","read","ocr","screen")):
            answers.extend(self.knowledge.get("ocr", []))
        if not answers:
            answers = [
                "This helper is local and rule-based. It guides script edits but is not a cloud AI.",
                "Paste code into the Editor tab to edit it directly, or describe a change here.",
            ]
        if self.ai_can_edit.get():
            answers.append("Edit permission is ON — the safe header tool can modify the open script.")
        else:
            answers.append("Edit permission is OFF. Enable it in Settings → Permissions.")
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "\n".join(f"  • {l}" for l in dict.fromkeys(answers)))

    def refresh_ai_targets(self):
        if not hasattr(self, "ai_target_combo"):
            return
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        files = [p for p in export_dir.iterdir() if p.is_file() and p.suffix.lower() in {".py",".ahk"}]
        current = self.ai_target_var.get()
        values = [str(p) for p in sorted(files)]
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
        if is_ahk and any(k in request for k in ("ui", "gui", "window", "textbox", "text box", "button", "input")):
            new_text = self.default_ahk_ui_code()
            notes.append("generated a working AutoHotkey v2 GUI")
        elif not is_ahk and any(k in request for k in ("ui", "gui", "window", "textbox", "text box", "button", "input")):
            new_text = self.default_python_ui_code()
            notes.append("generated a working Python Tkinter UI")
        if "convert" in request and ("python" in request or "ahk" in request or "autohotkey" in request):
            if is_ahk and "python" in request:
                new_text, conv_notes = self.ahk_to_python(text)
                notes.extend(conv_notes)
            elif not is_ahk and ("ahk" in request or "autohotkey" in request):
                new_text, conv_notes = self.python_to_ahk(text)
                notes.extend(conv_notes)
        if any(k in request for k in ("timing","drift","bpm","lag")):
            if is_ahk:
                if "WaitUntil(" not in new_text:
                    new_text += "\n; CodeHub timing note: regenerate to get absolute WaitUntil timing.\n"
                notes.append("checked for absolute timing drift controls")
            else:
                if "time.perf_counter" not in new_text:
                    new_text = new_text.replace("time.time()", "time.perf_counter()")
                    notes.append("changed wall-clock timing to perf_counter")
        new_text, norm_notes = self.normalize_macro_script(new_text, is_ahk)
        notes.extend(norm_notes)
        if new_text == text:
            prefix = ";" if is_ahk else "#"
            new_text = text.rstrip() + f"\n\n{prefix} CodeHub assistant reviewed — no rewrite rule matched.\n"
            notes.append("added review note")
        return new_text, sorted(set(notes))

    def default_ahk_ui_code(self):
        return """#Requires AutoHotkey v2.0
#SingleInstance Force

; Built by CodeHub assistant.
; F9 exits this UI. Edit labels, sizes, and button actions below.
app := Gui('+AlwaysOnTop', 'CodeHub AHK UI')
app.BackColor := '101820'
app.SetFont('s10 cE8F0F8', 'Segoe UI')

app.AddText('x20 y18 w280 h24', 'CodeHub AutoHotkey v2 UI')
nameBox := app.AddEdit('x20 y52 w260 h30', 'Type here')
statusText := app.AddText('x20 y96 w320 h24', 'Ready')
runBtn := app.AddButton('x20 y134 w120 h34', 'Run')
clearBtn := app.AddButton('x150 y134 w120 h34', 'Clear')
enabled := app.AddCheckbox('x20 y184 w180 h28', 'Enable option')

runBtn.OnEvent('Click', (*) => statusText.Text := 'Ran with: ' nameBox.Value)
clearBtn.OnEvent('Click', (*) => (nameBox.Value := '', statusText.Text := 'Cleared'))

app.Show('w380 h250')
F9::ExitApp
"""

    def default_python_ui_code(self):
        return """import tkinter as tk
from tkinter import ttk

# Built by CodeHub assistant.
# Edit labels, sizes, and button actions below.
root = tk.Tk()
root.title('CodeHub Python UI')
root.geometry('380x250')
root.configure(bg='#101820')

title = tk.Label(root, text='CodeHub Python UI', bg='#101820', fg='#e8f0f8', font=('Segoe UI', 12, 'bold'))
title.place(x=20, y=18, width=280, height=24)
name_box = ttk.Entry(root)
name_box.insert(0, 'Type here')
name_box.place(x=20, y=52, width=260, height=30)
status = tk.Label(root, text='Ready', bg='#101820', fg='#30c8e8')
status.place(x=20, y=96, width=320, height=24)

def run():
    status.configure(text=f'Ran with: {name_box.get()}')

def clear():
    name_box.delete(0, 'end')
    status.configure(text='Cleared')

ttk.Button(root, text='Run', command=run).place(x=20, y=134, width=120, height=34)
ttk.Button(root, text='Clear', command=clear).place(x=150, y=134, width=120, height=34)
ttk.Checkbutton(root, text='Enable option').place(x=20, y=184, width=180, height=28)
root.mainloop()
"""

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
            old_text.splitlines(), new_text.splitlines(),
            fromfile=f"{path.name} (before)", tofile=f"{path.name} (proposed)", lineterm="")
        self.ai_pending_path = path
        self.ai_pending_text = new_text
        self.ai_diff_view.delete("1.0", END)
        self.ai_diff_view.insert(END, "\n".join(diff) or "No textual diff.")
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "Proposed:\n" + "\n".join(f"  • {i}" for i in notes))

    def apply_ai_review(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        if not self.ai_pending_path or not self.ai_pending_text:
            messagebox.showinfo(APP_NAME, "Generate a preview first.")
            return
        old_text = self.ai_pending_path.read_text(encoding="utf-8") if self.ai_pending_path.exists() else ""
        self.ai_undo_stack.append((self.ai_pending_path, old_text))
        self.ai_pending_path.write_text(self.ai_pending_text, encoding="utf-8")
        self.load_script(self.ai_pending_path)
        self.status.set(f"Applied change  ·  {self.ai_pending_path.name}")

    def undo_ai_change(self):
        if not self.ai_undo_stack:
            messagebox.showinfo(APP_NAME, "No AI change to undo.")
            return
        path, old_text = self.ai_undo_stack.pop()
        path.write_text(old_text, encoding="utf-8")
        self.load_script(path)
        self.status.set(f"Undid change  ·  {path.name}")

    def apply_ai_header(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        is_ahk = self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk"
        comment = ";" if is_ahk else "#"
        header = (f"{comment} Edited with CodeHub assistant\n"
                  f"{comment} F1 starts, F2 stops, Numpad 5 exits.\n\n")
        current = self.editor.get("1.0", END)
        if "Edited with CodeHub assistant" not in current:
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
        self.converter_output.insert(END, "Changes:\n" + "\n".join(f"  • {i}" for i in notes))

    def apply_converter_output_to_editor(self):
        output = self.converter_output.get("1.0", END).strip()
        if not output:
            self.convert_code()
            output = self.converter_output.get("1.0", END).strip()
        script = output.split("\n\nChanges:\n", 1)[0].rstrip()
        if not script:
            return
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", script + "\n")
        self.tabs.select(1)
        self.status.set("Converted code placed in editor")

    def builder_number(self, value, fallback):
        try:
            return max(0, int(float(str(value).strip())))
        except Exception:
            return fallback

    def builder_add_block(self):
        block = {
            "kind": self.builder_kind.get(),
            "text": self.builder_text.get().strip() or self.builder_kind.get(),
            "x": self.builder_number(self.builder_x.get(), 20),
            "y": self.builder_number(self.builder_y.get(), 20),
            "w": self.builder_number(self.builder_w.get(), 140),
            "h": self.builder_number(self.builder_h.get(), 32),
        }
        self.builder_blocks.append(block)
        self.builder_y.set(str(block["y"] + block["h"] + 10))
        self.builder_refresh_list()
        self.builder_generate()

    def builder_clear(self):
        self.builder_blocks = []
        self.builder_refresh_list()
        self.builder_output.delete("1.0", END)

    def builder_refresh_list(self):
        if not hasattr(self, "builder_list"):
            return
        self.builder_list.delete("1.0", END)
        if not self.builder_blocks:
            self.builder_list.insert(END, "No blocks yet. Add a Label, Button, Input, Checkbox, or Slider.\n")
            return
        for i, block in enumerate(self.builder_blocks, 1):
            self.builder_list.insert(
                END,
                f"{i:02d}. {block['kind']:<8} text={block['text']!r} "
                f"x={block['x']} y={block['y']} w={block['w']} h={block['h']}\n",
            )

    def builder_generate(self):
        if self.builder_export.get() == "Python Tkinter":
            code = self.builder_python_code()
        else:
            code = self.builder_ahk_code()
        self.builder_output.delete("1.0", END)
        self.builder_output.insert(END, code)

    def builder_send_to_editor(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        code = self.builder_output.get("1.0", END).strip()
        if not code:
            self.builder_generate()
            code = self.builder_output.get("1.0", END).strip()
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", code + "\n")
        self.tabs.select(1)
        self.status.set("Builder code sent to editor")

    def builder_ahk_code(self):
        lines = [
            "#Requires AutoHotkey v2.0",
            "#SingleInstance Force",
            "",
            "; Built with CodeHub Code Builder.",
            "; Edit block positions by changing x/y/w/h values below.",
            "ui := Gui('+AlwaysOnTop', 'CodeHub Built UI')",
            "ui.BackColor := '101820'",
            "ui.SetFont('s9 cE8F0F8', 'Segoe UI')",
        ]
        for i, b in enumerate(self.builder_blocks, 1):
            opts = f"x{b['x']} y{b['y']} w{b['w']} h{b['h']}"
            text = b["text"].replace("'", "\\'")
            kind = b["kind"]
            if kind == "Label":
                lines.append(f"ui.AddText('{opts}', '{text}')")
            elif kind == "Button":
                lines.append(f"btn{i} := ui.AddButton('{opts}', '{text}')")
                lines.append(f"btn{i}.OnEvent('Click', (*) => MsgBox('{text} clicked'))")
            elif kind == "Input":
                lines.append(f"edit{i} := ui.AddEdit('{opts}', '{text}')")
            elif kind == "Checkbox":
                lines.append(f"check{i} := ui.AddCheckbox('{opts}', '{text}')")
            elif kind == "Slider":
                lines.append(f"slider{i} := ui.AddSlider('{opts} Range0-100 ToolTip', 50)")
        lines.extend(["", "ui.Show('w520 h360')", "Esc::ExitApp"])
        return "\n".join(lines) + "\n"

    def builder_python_code(self):
        lines = [
            "import tkinter as tk",
            "from tkinter import ttk",
            "",
            "# Built with CodeHub Code Builder.",
            "# Edit block positions by changing x/y/width/height values below.",
            "root = tk.Tk()",
            "root.title('CodeHub Built UI')",
            "root.geometry('520x360')",
            "root.configure(bg='#101820')",
        ]
        for i, b in enumerate(self.builder_blocks, 1):
            text = b["text"].replace("\\", "\\\\").replace("'", "\\'")
            kind = b["kind"]
            if kind == "Label":
                widget = f"tk.Label(root, text='{text}', bg='#101820', fg='#e8f0f8')"
            elif kind == "Button":
                widget = f"ttk.Button(root, text='{text}', command=lambda: print('{text} clicked'))"
            elif kind == "Input":
                widget = f"ttk.Entry(root)"
            elif kind == "Checkbox":
                lines.append(f"var{i} = tk.BooleanVar(value=False)")
                widget = f"ttk.Checkbutton(root, text='{text}', variable=var{i})"
            else:
                widget = "ttk.Scale(root, from_=0, to=100, orient='horizontal')"
            lines.append(f"widget{i} = {widget}")
            lines.append(f"widget{i}.place(x={b['x']}, y={b['y']}, width={b['w']}, height={b['h']})")
        lines.extend(["", "root.mainloop()"])
        return "\n".join(lines) + "\n"

    def python_to_ahk(self, source):
        notes = []
        lines = ["#Requires AutoHotkey v2.0", "#SingleInstance Force", "",
                 "global running := false", "",
                 "F1::{\n    global running\n    running := true\n}", "",
                 "F2::{\n    global running\n    running := false\n}", "",
                 "Numpad5::ExitApp", "",
                 "; Converted by CodeHub. Review coordinates and timing before use."]
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                lines.append(""); continue
            indent = "    " if raw.startswith((" ","\t")) else ""
            converted = None
            if stripped.startswith("#"):
                converted = "; " + stripped.lstrip("#").strip()
                notes.append("converted Python comments to AHK comments")
            elif re.match(r"time\.sleep\(([^)]+)\)", stripped):
                val = re.findall(r"time\.sleep\(([^)]+)\)", stripped)[0]
                try: ms = int(float(val)*1000)
                except: ms = 100
                converted = f"Sleep({ms})"
                notes.append("converted time.sleep to Sleep")
            elif "mouse.position" in stripped and "=" in stripped:
                nums = re.findall(r"-?\d+", stripped)
                converted = f"MouseMove({nums[0]}, {nums[1]}, 0)" if len(nums)>=2 else "; TODO: MouseMove(x, y, 0)"
                notes.append("converted mouse.position to MouseMove")
            elif re.search(r"mouse\.(click|press|release)", stripped):
                nums = re.findall(r"-?\d+", stripped)
                action = "Up" if "release" in stripped else "Down" if "press" in stripped else ""
                coord = f", {nums[0]}, {nums[1]}" if len(nums)>=2 else ""
                converted = f"Click(\"{action}\"{coord})" if action else f"Click({coord.lstrip(', ')})"
                notes.append("converted mouse click/press/release")
            elif re.search(r"keyboard\.(type|press|release)", stripped) or ".press(" in stripped or ".type(" in stripped:
                text = re.findall(r"[\"'](.+?)[\"']", stripped)
                converted = f"Send({text[0]!r})".replace("'",'"') if text else "; TODO: Send key/text"
                notes.append("converted keyboard call to Send")
            elif stripped.startswith(("import ","from ","def ","class ")):
                converted = "; " + stripped
            else:
                converted = "; TODO: " + stripped
            lines.append(indent + converted)
        return "\n".join(lines), sorted(set(notes or ["wrapped Python snippet in AHK hotkey shell"]))

    def ahk_to_python(self, source):
        notes = []
        lines = ["# Converted by CodeHub. Review coordinates and timing before use.",
                 "import time",
                 "from pynput.keyboard import Controller as KeyboardController",
                 "from pynput.mouse import Button, Controller as MouseController",
                 "", "keyboard = KeyboardController()", "mouse = MouseController()",
                 "running = False", ""]
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                lines.append(""); continue
            converted = None
            if stripped.startswith(";"):
                converted = "# " + stripped.lstrip(";").strip()
                notes.append("converted AHK comments to Python comments")
            elif stripped.lower().startswith(("#requires","#singleinstance")):
                converted = "# " + stripped
            elif re.match(r"Sleep\(?\s*(\d+)\s*\)?", stripped, re.I):
                ms = int(re.findall(r"\d+", stripped)[0])
                converted = f"time.sleep({ms/1000:.3f})"
                notes.append("converted Sleep to time.sleep")
            elif re.match(r"MouseMove\(", stripped, re.I):
                nums = re.findall(r"-?\d+", stripped)
                converted = f"mouse.position = ({nums[0]}, {nums[1]})" if len(nums)>=2 else "# TODO: mouse.position = (x, y)"
                notes.append("converted MouseMove to mouse.position")
            elif re.match(r"Click\(", stripped, re.I):
                nums = re.findall(r"-?\d+", stripped)
                if "down" in stripped.lower(): converted = "mouse.press(Button.left)"
                elif "up" in stripped.lower(): converted = "mouse.release(Button.left)"
                elif len(nums)>=2: converted = f"mouse.position = ({nums[0]}, {nums[1]})\nmouse.click(Button.left)"
                else: converted = "mouse.click(Button.left)"
                notes.append("converted Click to pynput mouse action")
            elif stripped.lower().startswith("send"):
                text = re.findall(r"[\"'](.+?)[\"']|\{(.+?)\}", stripped)
                val = next((a or b for a,b in text),"")
                converted = f"keyboard.type({val!r})" if val else "# TODO: keyboard press/type"
                notes.append("converted Send to keyboard.type")
            elif stripped.endswith("::") or stripped in ("{","}"):
                converted = "# " + stripped
            else:
                converted = "# TODO: " + stripped
            lines.append(converted)
        return "\n".join(lines), sorted(set(notes or ["wrapped AHK snippet in Python macro shell"]))

    def normalize_macro_script(self, source, is_ahk):
        notes = []
        text = source
        if is_ahk:
            if "#Requires AutoHotkey v2.0" not in text:
                text = "#Requires AutoHotkey v2.0\n#SingleInstance Force\n" + text
                notes.append("added AHK v2 header")
            if "Numpad5::ExitApp" not in text:
                text += "\n\nNumpad5::ExitApp\n"
                notes.append("added Numpad5 exit hotkey")
            if "F1::" not in text:
                text += "\nF1::{\n    global running := true\n}\n"
                notes.append("added F1 start hotkey")
            if "F2::" not in text:
                text += "\nF2::{\n    global running := false\n}\n"
                notes.append("added F2 stop hotkey")
        else:
            if "from pynput" not in text and ("mouse." in text or "keyboard." in text):
                text = "import time\nfrom pynput.keyboard import Controller as KeyboardController\nfrom pynput.mouse import Button, Controller as MouseController\n\nkeyboard = KeyboardController()\nmouse = MouseController()\n\n" + text
                notes.append("added Python pynput imports")
        if "Edited with CodeHub" not in text:
            prefix = ";" if is_ahk else "#"
            text = f"{prefix} Edited with CodeHub assistant\n" + text
            notes.append("added edit marker")
        return text, notes

    def root_contains_screen_point(self, x, y):
        self.root.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        return rx <= x <= rx+rw and ry <= y <= ry+rh

    def start_position_logging(self):
        if self.position_logging:
            return
        self.position_logging = True
        self.position_status.set(f"▶ Logging  ·  {len(self.position_log_events)} clicks")
        self.position_listener = mouse.Listener(on_click=self.on_position_log_click)
        self.position_listener.start()

    def stop_position_logging(self):
        self.position_logging = False
        if self.position_listener:
            self.position_listener.stop()
            self.position_listener = None
        self.position_status.set(f"■ Stopped  ·  {len(self.position_log_events)} clicks")

    def clear_position_log(self):
        self.position_log_events.clear()
        self.position_output.delete("1.0", END)
        self.position_status.set("▶ Logging  ·  0 clicks" if self.position_logging else "■ Stopped  ·  0 clicks")

    def on_position_log_click(self, x, y, button, pressed):
        if not self.position_logging or not pressed or button != mouse.Button.left:
            return
        if self.root_contains_screen_point(x, y):
            return
        event = {"x": int(x), "y": int(y), "time": time.time(), "index": len(self.position_log_events)+1}
        self.position_log_events.append(event)
        self.root.after(0, lambda e=event: self._append_pos_log(e))

    def _append_pos_log(self, event):
        stamp = datetime.fromtimestamp(event["time"]).strftime("%H:%M:%S")
        self.position_output.insert(END, f"{event['index']:03d}  {stamp}  left @ {event['x']}, {event['y']}\n")
        self.position_output.see(END)
        self.position_status.set(f"▶ Logging  ·  {len(self.position_log_events)} clicks")

    def insert_position_log_into_editor(self):
        if not self.position_log_events:
            messagebox.showinfo(APP_NAME, "No logged clicks yet.")
            return
        is_ahk = self.current_editor_file and Path(self.current_editor_file).suffix.lower() == ".ahk"
        lines = []
        for e in self.position_log_events:
            if is_ahk:
                lines.append(f"Click({e['x']}, {e['y']})")
            else:
                lines.append(f"mouse.position = ({e['x']}, {e['y']})")
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
        self.settings["auto_update"] = self.auto_update.get()
        fps = max(1, min(60, self.builder_number(self.review_fps.get(), 60)))
        self.settings["review_capture_fps"] = fps
        self.settings["review_capture_interval_ms"] = max(16, int(1000 / fps))
        write_json(SETTINGS_PATH, self.settings)
        self.status.set("Settings saved")

    def latest_github_sha(self):
        request = urllib.request.Request(GITHUB_API_LATEST, headers={"User-Agent": "CodeHub-Updater"})
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("sha", "")).strip()

    def check_for_updates(self, auto=False):
        self.status.set("Checking GitHub for updates...")

        def worker():
            try:
                latest_sha = self.latest_github_sha()
                if not latest_sha:
                    raise RuntimeError("GitHub did not return a commit SHA.")
                current_sha = str(self.settings.get("last_update_sha", "") or BUILD_COMMIT)
                has_update = latest_sha != current_sha
                self.root.after(0, lambda: self.finish_update_check(latest_sha, has_update, auto))
            except Exception as exc:
                if not auto:
                    self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Update check failed:\n{exc}"))
                self.root.after(0, lambda: self.status.set("Update check failed" if not auto else "Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def finish_update_check(self, latest_sha, has_update, auto):
        short_sha = latest_sha[:7]
        if not has_update:
            self.status.set(f"Already up to date  ·  {short_sha}")
            if not auto:
                messagebox.showinfo(APP_NAME, f"CodeHub is already up to date.\nLatest: {short_sha}")
            return
        if auto:
            should_update = True
        else:
            should_update = messagebox.askyesno(
                APP_NAME,
                f"Update found on GitHub: {short_sha}\n\nDownload the latest one-file CodeHub.exe now?",
            )
        if should_update:
            self.download_and_apply_update(latest_sha)
        else:
            self.status.set(f"Update available  ·  {short_sha}")
            
    def download_and_apply_update(self, latest_sha):
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(APP_NAME, "Source mode detected. Use Run Local Updater to rebuild the exe.")
            return

        exe_path = Path(sys.executable).resolve()
        tmp_exe = Path(tempfile.gettempdir()) / "CodeHub_update.exe"
        bat_path = Path(tempfile.gettempdir()) / "CodeHub_apply_update.bat"
        current_pid = os.getpid()

        self.settings["last_update_sha"] = latest_sha
        write_json(SETTINGS_PATH, self.settings)

        script = f"""@echo off
    setlocal
    color 0A
    title CodeHub Update

    echo [CodeHub] downloading latest package from GitHub...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '{GITHUB_EXE_URL}' -OutFile '{tmp_exe}'"
    if errorlevel 1 (
        echo [CodeHub] download failed.
        pause
        exit /b 1
    )

    echo [CodeHub] waiting for old app to close...
    :WAIT_APP
    tasklist /FI "PID eq {current_pid}" | find "{current_pid}" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto WAIT_APP
    )

    echo [CodeHub] replacing executable...
    copy /y "{tmp_exe}" "{exe_path}" >nul
    if errorlevel 1 (
        echo [CodeHub] replace failed.
        pause
        exit /b 1
    )

    echo [CodeHub] restarting CodeHub...
    start "" /D "{exe_path.parent}" "{exe_path}"

    echo [CodeHub] cleaning temp files...
    del "{tmp_exe}" >nul 2>nul

    echo [CodeHub] updated and closing...
    timeout /t 1 /nobreak >nul
    exit
    """

        bat_path.write_text(script, encoding="utf-8")

        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_path)],
            cwd=str(exe_path.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )

        self.root.after(150, self.close)

    def run_local_updater(self):
        candidates = [
            APP_ROOT / "AppUpdater.bat",
            Path(r"F:\Auto Hotkey\Python\CodeHub\AppUpdater.bat"),
        ]

        updater = next((path for path in candidates if path.exists()), None)

        if not updater:
            messagebox.showerror(APP_NAME, "Could not find AppUpdater.bat.")
            return

        subprocess.Popen(
            ["cmd.exe", "/c", str(updater)],
            cwd=str(updater.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        )

        self.status.set("Local updater launched")
        self.root.after(150, self.close)

    def save_ui_settings(self):
        try:
            size = int(self.ui_font_size.get())
        except ValueError:
            size = 9
        self.settings["ui_font_size"] = max(8, min(12, size))
        self.settings["ui_density"] = self.ui_density.get()
        write_json(SETTINGS_PATH, self.settings)
        self._configure_styles()
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
    startup_console()
    CodeHubApp().run()
