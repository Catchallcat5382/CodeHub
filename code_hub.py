import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import difflib
import tempfile
import textwrap
import urllib.request
import webbrowser
import ssl
import hashlib
from datetime import datetime
from pathlib import Path
from tkinter import (
    BOTH, END, HORIZONTAL, LEFT, RIGHT, X, Y, BooleanVar, DoubleVar,
    PhotoImage, StringVar, Tk, Toplevel, Canvas, Frame
)
from tkinter import filedialog, messagebox, colorchooser
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk

from pynput import keyboard, mouse
from pynput.keyboard import Key

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

#  Palette 
C = {
    "bg":        "#050505",
    "bg2":       "#080808",
    "panel":     "#0b0b0b",
    "panel2":    "#101010",
    "border":    "#2a2a2a",
    "border2":   "#3a3a3a",
    "text":      "#e8f0f8",
    "text2":     "#7a98b8",
    "text3":     "#3a5060",
    "accent":    "#57a6ff",
    "accent2":   "#155ecf",
    "green":     "#33ff66",
    "green2":    "#159447",
    "orange":    "#ffcc00",
    "red":       "#f04040",
    "purple":    "#9060f0",
    "yellow":    "#e8c040",
    "cyan":      "#3aa8ff",
    "teal":      "#20a890",
    "selection": "#14263a",
    "hl":        "#111111",
}

APP_NAME = "CodeHub"
MAKER_NAME = "Macro Maker"
GITHUB_REPO = "Catchallcat5382/CodeHub"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
GITHUB_API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_API_MAIN_EXE = f"https://api.github.com/repos/{GITHUB_REPO}/contents/CodeHub.exe?ref=main"
GITHUB_API_MAIN_SOURCE = f"https://api.github.com/repos/{GITHUB_REPO}/contents/code_hub.py?ref=main"
GITHUB_EXE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/CodeHub.exe"
GITHUB_MAIN_EXE_URL = f"https://github.com/{GITHUB_REPO}/raw/main/CodeHub.exe"
BUILD_COMMIT = "local-build"
BUILD_NUMBER = 55
MAX_REPLAY_FPS = 240
REPLAY_FPS_CHOICES = ["15", "20", "24", "30", "60", "120", "144", "240"]


def build_version(build_number=None):
    try:
        n = int(build_number or BUILD_NUMBER)
    except Exception:
        n = 1

    n = max(1, n)
    major = ((n - 1) // 10) + 1
    minor = (n - 1) % 10

    if minor == 0:
        return f"v{major}"
    return f"v{major}.{minor}"

def get_live_build_number():
    # Versions are release-based, not commit-count-based.
    return BUILD_NUMBER

def current_update_sha():
    sha = str(BUILD_COMMIT or "").strip()
    if sha and sha != "local-build":
        return sha
    return ""

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
UPDATE_MARKER_PATH = DATA_DIR / "installed_commit.txt"


def saved_update_sha(settings=None):
    sha = current_update_sha()
    if sha:
        return sha
    if settings:
        sha = str(settings.get("last_update_sha", "") or "").strip()
        if sha:
            return sha
    try:
        sha = UPDATE_MARKER_PATH.read_text(encoding="utf-8", errors="replace").strip()
        if sha:
            return sha
    except Exception:
        pass
    return ""


def remember_update_sha(settings, sha, tag=None):
    sha = str(sha or "").strip()
    if not sha:
        return
    if settings is not None:
        settings["last_update_sha"] = sha
        if tag:
            settings["last_update_tag"] = str(tag)
        write_json(SETTINGS_PATH, settings)
    try:
        UPDATE_MARKER_PATH.write_text(sha, encoding="utf-8")
    except Exception:
        pass

DEFAULT_SETTINGS = {
    "export_dir": str(EXPORT_DIR),
    "default_script_name": "MyMacro",
    "ahk_version": "2",
    "ahk_path_v2": "",
    "watermark_corner": "top_right",
    "watermark_opacity": 0.46,
    "ocr_region": {"x": 0, "y": 0, "width": 420, "height": 160},
    "ai_can_edit": False,
    "ai_can_delete": False,
    "ai_can_run": False,
    "ui_font_size": 9,
    "ui_density": "compact",
    "theme_mode": "computer_auto",
    "custom_bg": "#050505",
    "custom_panel": "#0b0b0b",
    "custom_text": "#e8f0f8",
    "custom_accent": "#57a6ff",
    "ui_sounds_enabled": False,
    "click_sounds_enabled": False,
    "tab_sounds_enabled": False,
    "loading_sound_enabled": True,
    "show_data_paths": False,
    "record_screenshots": True,
    "review_capture_fps": 60,
    "review_capture_interval_ms": 1000 // 60,
    "record_replay_video": False,
    "record_replay_audio": False,
    "replay_audio_source": "Game/System",
    "replay_audio_device": "Default",
    "replay_speaker_device": "Default Speakers",
    "replay_mic_device": "Default Mic",
    "allow_headset_mic_audio": False,
    "builder_background_image": "",
    "auto_update": False,
    "last_update_sha": "",
    "last_update_tag": "",
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


def clamp_hex_color(value, fallback="#57a6ff"):
    value = str(value or "").strip()
    if not value.startswith("#"):
        value = "#" + value
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.upper()
    return fallback


def hex_to_rgb(hex_color):
    hex_color = clamp_hex_color(hex_color).lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def mix_hex(a, b, amount):
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    amount = max(0.0, min(1.0, float(amount)))
    return "#{:02X}{:02X}{:02X}".format(
        int(ar + (br - ar) * amount),
        int(ag + (bg - ag) * amount),
        int(ab + (bb - ab) * amount),
    )


def detect_windows_dark_mode():
    if sys.platform != "win32":
        return True
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except Exception:
        return True


def apply_theme_to_palette(settings):
    mode = str(settings.get("theme_mode", "computer_auto") or "computer_auto").lower()
    if mode == "computer_auto":
        mode = "dark" if detect_windows_dark_mode() else "light"

    if mode == "light":
        base = {
            "bg": "#F5F7FB", "bg2": "#EEF2F7", "panel": "#E8EDF5", "panel2": "#FFFFFF",
            "border": "#CBD5E1", "border2": "#94A3B8", "text": "#111827", "text2": "#475569",
            "text3": "#94A3B8", "accent": "#2563EB", "accent2": "#1D4ED8", "selection": "#DBEAFE", "hl": "#F8FAFC",
        }
    elif mode == "custom":
        bg = clamp_hex_color(settings.get("custom_bg", "#050505"), "#050505")
        panel = clamp_hex_color(settings.get("custom_panel", "#0B0B0B"), "#0B0B0B")
        text = clamp_hex_color(settings.get("custom_text", "#E8F0F8"), "#E8F0F8")
        accent = clamp_hex_color(settings.get("custom_accent", "#57A6FF"), "#57A6FF")
        base = {
            "bg": bg, "bg2": mix_hex(bg, "#000000", 0.15), "panel": panel, "panel2": mix_hex(panel, "#FFFFFF", 0.04),
            "border": mix_hex(panel, text, 0.25), "border2": mix_hex(panel, text, 0.35), "text": text,
            "text2": mix_hex(text, bg, 0.35), "text3": mix_hex(text, bg, 0.58), "accent": accent,
            "accent2": mix_hex(accent, "#000000", 0.28), "selection": mix_hex(accent, bg, 0.72), "hl": mix_hex(panel, text, 0.08),
        }
    else:
        base = {
            "bg": "#050505", "bg2": "#080808", "panel": "#0b0b0b", "panel2": "#101010",
            "border": "#2a2a2a", "border2": "#3a3a3a", "text": "#e8f0f8", "text2": "#7a98b8",
            "text3": "#3a5060", "accent": "#57a6ff", "accent2": "#155ecf", "selection": "#14263a", "hl": "#111111",
        }
    C.update(base)



def migrate_legacy_data():
    if not getattr(sys, "frozen", False):
        return
    legacy = APP_ROOT / "data"
    if not legacy.exists() or legacy == DATA_DIR:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("settings.json", "recordings.json", "knowledge.json"):
        src = legacy / name
        dst = DATA_DIR / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


def ensure_files():
    migrate_legacy_data()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        write_json(SETTINGS_PATH, DEFAULT_SETTINGS)
    else:
        existing_settings = read_json(SETTINGS_PATH, {})
        changed = False
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing_settings:
                existing_settings[key] = value
                changed = True
        if changed:
            write_json(SETTINGS_PATH, existing_settings)
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




def clear():
    """Clear the visible diagnostics console safely."""
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        # Never let a console-clear failure crash CodeHub.
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
    """Keep a visible diagnostics console open and print useful asset info."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            if not kernel32.GetConsoleWindow():
                kernel32.AllocConsole()
            try:
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stdin = open("CONIN$", "r", encoding="utf-8")
            except Exception:
                pass
            os.system("color 0A")
            os.system(f"title {APP_NAME} Diagnostics")
        except Exception:
            pass
    else:
        try:
            os.system(f"title {APP_NAME} Diagnostics")
        except Exception:
            pass

    clear()
    print("=" * 78, flush=True)
    print("                    CODEHUB SYSTEM BOOTSTRAP / DIAGNOSTICS", flush=True)
    print("=" * 78, flush=True)
    print(f"[APP ] {APP_NAME}", flush=True)
    print(f"[VER ] {build_version(get_live_build_number())}", flush=True)
    print(f"[PY  ] {sys.version.split()[0]}  exe={sys.executable}", flush=True)
    print(f"[ROOT] APP_ROOT    = {APP_ROOT}", flush=True)
    print(f"[ROOT] BUNDLE_ROOT = {BUNDLE_ROOT}", flush=True)
    print(f"[ROOT] ASSET_DIR   = {ASSET_DIR}", flush=True)
    print(f"[ROOT] DATA_DIR    = {DATA_DIR}", flush=True)
    print("[NOTE] This console stays open for .", flush=True)
    print("-" * 78, flush=True)

    lines = [
        "[BOOT] mounting CodeHub runtime",
        "[ASSET] mounting embedded assets",
        "[UI] waiting for splash before showing main interface",
        "[READY] startup diagnostics armed",
    ]
    total = len(lines)
    for i, msg in enumerate(lines, 1):
        width = 30
        done = int(width * i / total)
        bar = "#" * done + "-" * (width - done)
        print(f"{msg}\n[LOAD] [{bar}] {int(i * 100 / total):3d}%", flush=True)
        time.sleep(0.015)
    print("-" * 78, flush=True)

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
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "bytes":
                return f"{int(value)} bytes"
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
    return None


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


PYTHON_IMPORT_PACKAGES = {
    "pynput": "pynput",
    "PIL": "Pillow",
    "mss": "mss",
    "cv2": "opencv-python",
    "numpy": "numpy",
    "sounddevice": "sounddevice",
    "soundcard": "soundcard",
}


def required_packages_for_python_script(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        text = ""
    packages = []
    for module, package in PYTHON_IMPORT_PACKAGES.items():
        patterns = (
            f"import {module}",
            f"from {module} import",
        )
        if any(pattern in text for pattern in patterns):
            packages.append((module, package))
    if "from pynput import" in text and ("pynput", "pynput") not in packages:
        packages.append(("pynput", "pynput"))
    return packages


def command_to_cmdline(command):
    return subprocess.list2cmdline([str(part) for part in command])


def missing_python_modules(py_cmd, modules):
    missing = []
    for module, package in modules:
        try:
            result = subprocess.run(
                py_cmd + ["-c", f"import {module}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=hidden_process_flags(),
            )
            if result.returncode != 0:
                missing.append((module, package))
        except Exception:
            missing.append((module, package))
    return missing


def python_install_url():
    return "https://www.python.org/downloads/windows/"


def hidden_process_flags():
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def github_json_request(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": "CodeHub-Updater"})
    errors = []

    context = None
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        context = None

    try:
        kwargs = {"timeout": timeout}
        if context is not None:
            kwargs["context"] = context
        with urllib.request.urlopen(request, **kwargs) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        errors.append(f"Python HTTPS: {exc}")

    if os.name == "nt":
        ps_url = str(url).replace("'", "''")
        ps_cmd = (
            "$ErrorActionPreference='Stop'; "
            "$ProgressPreference='SilentlyContinue'; "
            "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; "
            f"$r=Invoke-RestMethod -Uri '{ps_url}' -Headers @{{'User-Agent'='CodeHub-Updater'}} -TimeoutSec {int(timeout)}; "
            "$r | ConvertTo-Json -Depth 30 -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=timeout + 8,
                creationflags=hidden_process_flags(),
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            errors.append(f"PowerShell HTTPS: {(result.stderr or result.stdout or '').strip()}")
        except Exception as exc:
            errors.append(f"PowerShell HTTPS: {exc}")

    raise RuntimeError("Could not reach GitHub for updates.\n\n" + "\n".join(errors[-3:]))


def git_blob_sha_for_file(path):
    path = Path(path)
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def first_asset_named(stem):
    preferred = (".mp3", ".wav", ".ogg", ".flac", ".aiff")
    for suffix in preferred:
        path = ASSET_DIR / f"{stem}{suffix}"
        if path.is_file():
            return path
    for path in sorted(ASSET_DIR.glob(f"{stem}.*")):
        if path.is_file():
            return path
    return None


def _ahk_version_from_output(output):
    text = str(output or "").lower()
    if "v2" in text or "version 2" in text:
        return "2"
    if "v1" in text or "version 1" in text or "1.1" in text:
        return "1"
    return ""


def detect_ahk_version(path):
    path = str(path or "").strip()
    if not path:
        return ""
    try:
        result = subprocess.run([path, "/ErrorStdOut", "*"], input="MsgBox % A_AhkVersion`n", capture_output=True, text=True, timeout=2, creationflags=hidden_process_flags())
        version_text = (result.stdout or "") + (result.stderr or "")
        if "1." in version_text:
            return "1"
        if "v2" in version_text.lower() or "requires" in version_text.lower():
            return "2"
    except Exception:
        pass
    name = Path(path).name.lower()
    full = str(path).lower()
    if "v2" in full or "autohotkey64.exe" in name:
        return "2"
    if "v1" in full or "autohotkeyu" in name:
        return "1"
    return ""


def find_ahk_exe(version=None, custom_path=None):
    version = str(version or "").strip()
    candidates = []

    if custom_path:
        candidates.append(Path(custom_path))

    if version == "2":
        names = ("AutoHotkey64.exe", "AutoHotkey.exe", "AutoHotkeyUX.exe")
        candidates.extend([
            Path("C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"),
            Path("C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"),
            Path("C:/Program Files/AutoHotkey/AutoHotkey64.exe"),
            Path("C:/Program Files/AutoHotkey/AutoHotkey.exe"),
        ])
    elif version == "1":
        names = ("AutoHotkeyU64.exe", "AutoHotkeyU32.exe", "AutoHotkeyA32.exe", "AutoHotkey.exe")
        candidates.extend([
            Path("C:/Program Files/AutoHotkey/v1.1/AutoHotkeyU64.exe"),
            Path("C:/Program Files/AutoHotkey/v1.1/AutoHotkey.exe"),
            Path("C:/Program Files/AutoHotkey/AutoHotkeyU64.exe"),
            Path("C:/Program Files (x86)/AutoHotkey/AutoHotkey.exe"),
        ])
    else:
        names = ("AutoHotkey64.exe", "AutoHotkey.exe", "AutoHotkeyU64.exe", "AutoHotkeyU32.exe")
        candidates.extend([
            Path("C:/Program Files/AutoHotkey/v2/AutoHotkey64.exe"),
            Path("C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"),
            Path("C:/Program Files/AutoHotkey/v1.1/AutoHotkeyU64.exe"),
            Path("C:/Program Files/AutoHotkey/AutoHotkey.exe"),
            Path("C:/Program Files/AutoHotkey/AutoHotkey64.exe"),
            Path("C:/Program Files (x86)/AutoHotkey/AutoHotkey.exe"),
        ])

    for name in names:
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    seen = set()
    for path in candidates:
        try:
            path = Path(path)
        except Exception:
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            if not version:
                return str(path)
            detected = detect_ahk_version(path)
            if detected == version or not detected:
                return str(path)
    return None


def selected_ahk_version_from_export(export_kind):
    text = str(export_kind or "").lower()
    if "v1" in text or "1" in text and "autohotkey" in text:
        return "1"
    return "2"


def ahk_required_version_for_file(path, fallback="2"):
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:1200].lower()
    except Exception:
        return str(fallback or "2")
    if "#requires autohotkey v1" in head or "autohotkey v1.1" in head:
        return "1"
    if "#requires autohotkey v2" in head or "autohotkey v2.0" in head:
        return "2"
    return str(fallback or "2")


def show_missing_ahk_and_exit():
    message = (
        "CodeHub requires AutoHotkey to run.\n\n"
        "AutoHotkey was not found on this PC, so CodeHub cannot open.\n\n"
        "Install AutoHotkey v2, then reopen CodeHub."
    )
    try:
        root = Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, message, parent=root)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
    sys.exit(1)


def require_autohotkey_or_exit():
    if not find_ahk_exe("2"):
        show_missing_ahk_and_exit()


def ahk_install_url(version=None):
    # Official AutoHotkey download page.
    return "https://www.autohotkey.com/"

def describe_missing_ahk(version=None):
    version = str(version or "").strip()
    if version == "1":
        return "AutoHotkey v1 is no longer supported. Re-export this script as AutoHotkey v2 or Python."
    if version == "2":
        return "AutoHotkey v2 is required to save or run this AHK v2 script."
    return "AutoHotkey is required to save or run AutoHotkey scripts."


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
        "    loader.AddText('w300 Center', 'AutoHotkey v2 · ' title)",
        "    loader.SetFont('s8 c8FD9FF', 'Segoe UI')",
        "    status := loader.AddText('w300 Center y+6', 'CodeHub AutoHotkey v2 loader')",
        "    barBg := loader.AddProgress('w300 h10 y+10 Background182434 c33FF66 Range0-100', 0)",
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
        '    wm.AddText("w180 Center", "Made by Cat · AutoHotkey v2")',
        "    WinSetTransparent(62, wm.Hwnd)",
        "    x := A_ScreenWidth - 174",
        "    y := 4",
        "    wm.Show('NoActivate x' x ' y' y ' w168 h26')",
        "}",
        "",
    ])
    return "\n".join(lines)



def generate_ahk_v1(events, mode, script_name):
    name = safe_name(script_name)
    load_ms = max(450, min(2400, 420 + len(events) * 7))
    lines = [
        "#Requires AutoHotkey v1.1",
        "#SingleInstance Force",
        "; Generated by CodeHub / Macro Maker.",
        f"; Script: {name}",
        f"; Mode: {mode}",
        f"; Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "; Hotkeys: F1 starts playback, F2 stops playback, Numpad 5 exits.",
        "SetKeyDelay, -1, -1",
        "SetMouseDelay, -1",
        "SetWinDelay, -1",
        "SetControlDelay, -1",
        "global running := false",
        f'global macroName := "{ahk_text(name)}"',
        "CreateWatermark()",
        f"ShowCodeHubLoader({load_ms}, \"Loading \" . macroName)",
        "",
        "F1::",
        "running := true",
        "ToolTip, Started %macroName%, 16, 16",
        "SetTimer, ClearToolTip, -900",
        f"ShowCodeHubLoader({load_ms}, \"Preparing playback\")",
        "PlayMacro()",
        "return",
        "",
        "F2::",
        "running := false",
        "ToolTip, Stopped %macroName%, 16, 16",
        "SetTimer, ClearToolTip, -900",
        "return",
        "",
        "Numpad5::ExitApp",
        "",
        "ClearToolTip:",
        "ToolTip",
        "return",
        "",
        "PlayMacro()",
        "{",
        "    global running",
        "    startTick := A_TickCount",
    ]
    for event in events:
        event_time = float(event.get("time", 0))
        target_ms = int(max(0, event_time) * 1000)
        lines.extend(["    if (!running)", "        return"])
        if target_ms > 0:
            lines.append(f"    WaitUntil(startTick + {target_ms})")
        kind = event.get("type")
        if kind == "mouse_move" and mode == "advanced":
            lines.append(f"    MouseMove, {int(event.get('x', 0))}, {int(event.get('y', 0))}, 0")
        elif kind == "mouse_click":
            x = int(event.get("x", 0)); y = int(event.get("y", 0))
            button = str(event.get("button", "left")).capitalize()
            pressed = event.get("pressed", True)
            if mode == "minimal":
                if pressed:
                    lines.append(f"    Click, {x}, {y}")
            else:
                action = "Down" if pressed else "Up"
                btn = "" if button == "Left" else button
                lines.append(f"    Click, {x}, {y}, {btn}, 1, 0, {action}".replace(", ,", ","))
        elif kind == "mouse_scroll" and mode != "minimal":
            wheel = "WheelUp" if int(event.get("dy", 0)) > 0 else "WheelDown"
            lines.append(f"    Send, {{{wheel}}}")
        elif kind == "key_char" and mode == "minimal":
            char = str(event.get("char", "")).replace("`", "``")
            lines.append(f"    SendRaw, {char}")
        elif kind in ("key_press", "key_release"):
            key = to_ahk_key(str(event.get("key", "")))
            if key and not (mode == "minimal" and kind == "key_release"):
                direction = " down" if kind == "key_press" else " up"
                lines.append(f"    Send, {{{key}{direction}}}")
    lines.extend([
        "    running := false",
        "}",
        "",
        "WaitUntil(targetTick)",
        "{",
        "    global running",
        "    while (running && A_TickCount < targetTick)",
        "    {",
        "        remaining := targetTick - A_TickCount",
        "        if (remaining > 3)",
        "            Sleep, 1",
        "        else",
        "            Sleep, 0",
        "    }",
        "}",
        "",
        "ShowCodeHubLoader(durationMs := 900, title := \"Loading macro\")",
        "{",
        "    Gui, Loader:New, +AlwaysOnTop -Caption +ToolWindow",
        "    Gui, Loader:Color, 081019",
        "    Gui, Loader:Font, s10 cEAF6FF, Segoe UI",
        "    Gui, Loader:Add, Text, w300 Center, AutoHotkey v1.1 - %title%",
        "    Gui, Loader:Font, s8 c8FD9FF, Segoe UI",
        "    Gui, Loader:Add, Text, HwndLoaderStatusHwnd w300 Center y+6, CodeHub AutoHotkey v1 loader",
        "    Gui, Loader:Add, Progress, HwndLoaderBarHwnd w300 h10 y+10 Background182434 c33FF66 Range0-100, 0",
        "    x := (A_ScreenWidth - 336) // 2",
        "    y := (A_ScreenHeight - 118) // 2",
        "    Gui, Loader:Show, NoActivate x%x% y%y% w336 h118",
        "    steps := 28",
        "    delay := Max(8, Floor(durationMs / steps))",
        "    Loop, %steps%",
        "    {",
        "        val := Floor((A_Index / steps) * 100)",
        "        GuiControl,, %LoaderBarHwnd%, %val%",
        "        GuiControl,, %LoaderStatusHwnd%, Indexing input timing... %val%`%",
        "        Sleep, %delay%",
        "    }",
        "    Sleep, 350",
        "    Gui, Loader:Destroy",
        "}",
        "",
        "CreateWatermark()",
        "{",
        "    Gui, WM:New, +AlwaysOnTop -Caption +ToolWindow +E0x20 +HwndWMHwnd",
        "    Gui, WM:Color, 101820",
        "    Gui, WM:Font, s8 cD6DEE8, Segoe UI",
        "    Gui, WM:Add, Text, w180 Center, Made by Cat · AutoHotkey v1",
        "    x := A_ScreenWidth - 174",
        "    Gui, WM:Show, NoActivate x%x% y4 w168 h26",
        "    WinSet, Transparent, 62, ahk_id %WMHwnd%",
        "}",
    ])
    return "\n".join(lines)


def generate_python(events, mode, script_name):
    name = safe_name(script_name)
    payload = json.dumps(events, indent=2)
    return f'''\"\"\"
Generated by CodeHub / Macro Maker.
Script: {name}
Engine: Python
Hotkeys: F1 starts playback, F2 stops playback, Numpad 5 exits.
Watermark: Made by Cat.
\"\"\"
import json
import os
import math
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox


def require_generated_script_packages():
    missing = []
    try:
        import pynput  # noqa: F401
    except Exception:
        missing.append("pynput")
    if not missing:
        return
    message = (
        "This CodeHub Python macro needs one missing package:\\n\\n"
        + "\\n".join(missing)
        + "\\n\\nInstall it with:\\n"
        + sys.executable
        + " -m pip install "
        + " ".join(missing)
        + "\\n\\nCodeHub can install this automatically when you run the script from the CodeHub app."
    )
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("CodeHub Python Macro", message)
        root.destroy()
    except Exception:
        print(message)
    raise SystemExit(1)


require_generated_script_packages()
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
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


class CodeHubLoader:
    def __init__(self, title="Preparing Python macro", duration_ms=1700):
        self.title = title
        self.duration_ms = max(900, int(duration_ms))
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#07101F")
        self.root.geometry(self._center_geometry(470, 210))
        self.canvas = tk.Canvas(self.root, width=470, height=210, bg="#07101F", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def _center_geometry(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return f"{{w}}x{{h}}+{{(sw-w)//2}}+{{(sh-h)//2}}"

    def run(self):
        steps = 34
        for i in range(steps + 1):
            pct = i / steps
            self.canvas.delete("all")
            self.canvas.create_rectangle(0, 0, 470, 210, fill="#07101F", outline="")
            self.canvas.create_text(235, 32, text="CodeHub Python Loader", fill="#57A6FF", font=("Segoe UI", 16, "bold"))
            self.canvas.create_text(235, 62, text=self.title, fill="#DDEBFF", font=("Segoe UI", 10))
            for n in range(18):
                x = 35 + n * 22
                h = 15 + ((i + n * 2) % 10) * 5
                self.canvas.create_rectangle(x, 128 - h, x + 10, 128, fill="#57A6FF", outline="")
            angle = i * 0.35
            for n in range(10):
                a = angle + n * 0.628
                r = 22 + (n % 3) * 5
                x = 235 + int(math.cos(a) * r)
                y = 151 + int(math.sin(a) * r)
                self.canvas.create_oval(x-3, y-3, x+3, y+3, fill="#57A6FF", outline="")
            self.canvas.create_rectangle(42, 172, 428, 186, outline="#24496E", width=1)
            self.canvas.create_rectangle(44, 174, 44 + int(382 * pct), 184, fill="#57A6FF", outline="")
            self.canvas.create_text(235, 199, text=f"Python engine initializing... {{int(pct * 100)}}%", fill="#9FCBFF", font=("Consolas", 9))
            self.root.update()
            time.sleep(self.duration_ms / 1000 / steps)
        time.sleep(0.18)
        self.root.destroy()


class Watermark:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.46)
        label = tk.Label(
            self.root,
            text="Made by Cat · Python",
            bg="#101820",
            fg="#57A6FF",
            font=("Segoe UI", 7, "bold"),
            padx=7,
            pady=3,
        )
        label.pack()
        self.root.update_idletasks()
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
    CodeHubLoader("Preparing playback for " + SCRIPT_NAME, 1500).run()
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
    CodeHubLoader("Starting " + SCRIPT_NAME, 1800).run()
    print("F1 start | F2 stop | Numpad 5 exit")
    global WATERMARK
    WATERMARK = Watermark()
    WATERMARK.show()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
'''


def generate_python_launcher(script_path):
    script_path = Path(script_path)
    fallback_packages = "pynput mss Pillow pytesseract opencv-python numpy pygame sounddevice soundcard certifi"
    return "\n".join([
        "@echo off",
        "setlocal EnableExtensions",
        f"title CodeHub Python Launcher - {script_path.name}",
        "color 0A",
        "echo ================================================================",
        "echo                    CodeHub Python Launcher",
        "echo ================================================================",
        f"echo Script: {script_path}",
        "echo.",
        "set \"PY_CMD=\"",
        "py -3 --version >nul 2>&1",
        "if not errorlevel 1 set \"PY_CMD=py -3\"",
        "if \"%PY_CMD%\"==\"\" (",
        "  python --version >nul 2>&1",
        "  if not errorlevel 1 set \"PY_CMD=python\"",
        ")",
        "if \"%PY_CMD%\"==\"\" (",
        "  echo [ERROR] Python 3 is not installed or not on PATH.",
        "  echo.",
        "  echo Install Python 3 from:",
        "  echo https://www.python.org/downloads/windows/",
        "  echo.",
        "  powershell -NoProfile -ExecutionPolicy Bypass -Command \"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python 3 is required to run this CodeHub macro. Click OK, then install Python from python.org/downloads/windows/.','CodeHub Python Macro')\" >nul 2>&1",
        "  start \"\" \"https://www.python.org/downloads/windows/\"",
        "  pause",
        "  exit /b 9009",
        ")",
        "echo [OK] Python found: %PY_CMD%",
        "set \"REQ_FILE=%~dp0..\\requirements.txt\"",
        "echo.",
        "echo [SETUP] Installing/checking CodeHub Python requirements...",
        "if exist \"%REQ_FILE%\" (",
        "  echo Using requirements: %REQ_FILE%",
        "  %PY_CMD% -m pip install --upgrade pip",
        "  %PY_CMD% -m pip install -r \"%REQ_FILE%\"",
        ") else (",
        "  echo requirements.txt not found next to CodeHub, using built-in package list.",
        f"  %PY_CMD% -m pip install --upgrade pip {fallback_packages}",
        ")",
        "if errorlevel 1 (",
        "  echo.",
        "  echo [ERROR] Requirement installation failed.",
        "  echo Make sure Python was installed with pip enabled and internet access is available.",
        "  echo If needed, run: %PY_CMD% -m ensurepip --upgrade",
        "  pause",
        "  exit /b 3",
        ")",
        "%PY_CMD% -c \"import pynput; import tkinter; print('runtime OK')\" >nul 2>&1",
        "if errorlevel 1 (",
        "  echo.",
        "  echo [MISSING] Python runtime check failed.",
        "  echo Trying ensurepip and full CodeHub requirements one more time...",
        "  %PY_CMD% -m ensurepip --upgrade",
        "  if exist \"%REQ_FILE%\" (",
        "    %PY_CMD% -m pip install -r \"%REQ_FILE%\"",
        "  ) else (",
        f"    %PY_CMD% -m pip install {fallback_packages}",
        "  )",
        "  if errorlevel 1 (",
        "    echo [ERROR] Package install failed or Python is missing tkinter.",
        "    echo Reinstall Python from python.org and make sure pip/tcl-tk are enabled.",
        "    pause",
        "    exit /b 4",
        "  )",
        ")",
        "echo.",
        "echo [RUN] Starting macro. F1 start ^| F2 stop ^| Numpad 5 exit",
        "echo ---------------------------------------------------------------",
        "%PY_CMD% \"%~dp0" + script_path.name + "\"",
        "set EXIT_CODE=%ERRORLEVEL%",
        "echo ---------------------------------------------------------------",
        "echo Script exited with code %EXIT_CODE%.",
        "if not \"%EXIT_CODE%\"==\"0\" pause",
        "exit /b %EXIT_CODE%",
        "",
    ])


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


#  Custom dialog helper 

class StyledDialog(Toplevel):
    """Base class for all custom dialogs  dark themed, no default chrome."""
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


#  Custom title bar 

class TitleBar(Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["panel"], height=50)
        self.app = app
        self.pack_propagate(False)
        self._drag_x = 0
        self._drag_y = 0

        # Logo diamond
        logo_lbl = ttk.Label(self, text="", style="Logo.TLabel")
        logo_lbl.pack(side=LEFT, padx=(14, 6), pady=10)

        name_lbl = ttk.Label(self, text="CodeHub", style="AppTitle.TLabel")
        name_lbl.pack(side=LEFT, padx=(0, 4))

        sep_lbl = ttk.Label(self, text="", style="TitleSep.TLabel")
        sep_lbl.pack(side=LEFT, padx=4)

        sub_lbl = ttk.Label(self, text="Recorder  Scripts  Tools  Automation", style="AppSub.TLabel")
        sub_lbl.pack(side=LEFT)

        # Window controls (right side)
        Frame(self, bg=C["panel"], width=10).pack(side=RIGHT)

        close_btn = self._wbtn("X", C["red"], self.app.close)
        close_btn.pack(side=RIGHT, padx=2, pady=10)

        max_btn = self._wbtn("[ ]", C["green"], self._toggle_max)
        max_btn.pack(side=RIGHT, padx=2, pady=10)

        min_btn = self._wbtn("_", C["yellow"], self.app.minimize_window)
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


#  Status bar 

class StatusBar(Frame):
    def __init__(self, parent, status_var):
        super().__init__(parent, bg=C["panel"], height=28)
        self.pack_propagate(False)
        Frame(self, bg=C["accent"], width=3).pack(side=LEFT, fill=Y)
        self._dot = ttk.Label(self, text="", style="StatusDot.TLabel", foreground=C["text3"])
        self._dot.pack(side=LEFT, padx=(10, 4))
        self._lbl = ttk.Label(self, textvariable=status_var, style="StatusText.TLabel")
        self._lbl.pack(side=LEFT)
        # right side info
        self._info = ttk.Label(self, text="F1 Record  F2 Stop  F9 Exit", style="StatusRight.TLabel")
        self._info.pack(side=RIGHT, padx=14)

    def set_color(self, color):
        self._dot.configure(foreground=color)


#  Main App 

class CodeHubApp:
    def __init__(self):
        ensure_files()
        self.settings = read_json(SETTINGS_PATH, DEFAULT_SETTINGS)
        if self.settings.get("default_export_kind") not in ("AutoHotkey v2", "Python"):
            self.settings["default_export_kind"] = "AutoHotkey v2"
        if "click_sounds_enabled" not in self.settings:
            self.settings["click_sounds_enabled"] = False
        if "tab_sounds_enabled" not in self.settings:
            self.settings["tab_sounds_enabled"] = False
        self.settings["loading_sound_enabled"] = True
        self.settings["ahk_version"] = "2"
        write_json(SETTINGS_PATH, self.settings)
        apply_theme_to_palette(self.settings)
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
        self.ahk_version = StringVar(value="2")
        self.ahk_path_v2 = StringVar(value=str(self.settings.get("ahk_path_v2", "")))
        self.export_dir_var = StringVar(value=self.settings.get("export_dir", str(EXPORT_DIR)))
        self.status = StringVar(value="Ready")
        self.ai_can_edit = BooleanVar(value=bool(self.settings.get("ai_can_edit", False)))
        self.ai_can_delete = BooleanVar(value=bool(self.settings.get("ai_can_delete", False)))
        self.ai_can_run = BooleanVar(value=bool(self.settings.get("ai_can_run", False)))
        self.ui_font_size = StringVar(value=str(self.settings.get("ui_font_size", 9)))
        self.ui_density = StringVar(value=self.settings.get("ui_density", "compact"))
        self.theme_mode = StringVar(value=self.settings.get("theme_mode", "computer_auto"))
        self.custom_bg = StringVar(value=self.settings.get("custom_bg", "#050505"))
        self.custom_panel = StringVar(value=self.settings.get("custom_panel", "#0B0B0B"))
        self.custom_text = StringVar(value=self.settings.get("custom_text", "#E8F0F8"))
        self.custom_accent = StringVar(value=self.settings.get("custom_accent", "#57A6FF"))
        self.record_screenshots = BooleanVar(value=bool(self.settings.get("record_screenshots", True)))
        self.record_replay_video = BooleanVar(value=bool(self.settings.get("record_replay_video", False)))
        self.record_replay_audio = BooleanVar(value=bool(self.settings.get("record_replay_audio", False)))
        self.replay_audio_source = StringVar(value=self.settings.get("replay_audio_source", "Game/System"))
        self.replay_audio_device = StringVar(value=self.settings.get("replay_audio_device", "Default"))
        self.replay_speaker_device = StringVar(value=self.settings.get("replay_speaker_device", "Default Speakers"))
        self.replay_mic_device = StringVar(value=self.settings.get("replay_mic_device", "Default Mic"))
        self.allow_headset_mic_audio = BooleanVar(value=bool(self.settings.get("allow_headset_mic_audio", False)))
        self.ui_sounds_enabled = BooleanVar(value=bool(self.settings.get("ui_sounds_enabled", True)))
        self.click_sounds_enabled = BooleanVar(value=bool(self.settings.get("click_sounds_enabled", self.settings.get("ui_sounds_enabled", True))))
        self.tab_sounds_enabled = BooleanVar(value=bool(self.settings.get("tab_sounds_enabled", self.settings.get("ui_sounds_enabled", True))))
        self.loading_sound_enabled = BooleanVar(value=True)
        self.show_data_paths = BooleanVar(value=bool(self.settings.get("show_data_paths", False)))
        self.builder_background_image = StringVar(value=str(self.settings.get("builder_background_image", "")))
        self.builder_background_photo = None
        self.builder_selected_index = None
        self.builder_drag_offset = (0, 0)
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
        self.review_photo_cache = {}
        self.review_playing = False
        self.review_paused = False
        self.review_play_index = 0
        self.review_speed = DoubleVar(value=1.0)
        self.review_video_path = None
        self.review_audio_path = None
        self.review_video_meta = {}
        self.review_video_playing = False
        self.review_video_paused = False
        self.review_video_thread = None
        self.review_audio_channel = None
        self.review_audio_error = ""
        self.replay_video_thread = None
        self.replay_video_stop_event = None
        self.replay_audio_thread = None
        self.replay_audio_stop_event = None
        self.replay_video_start_time = None
        self._audio_devices_cache = []
        self._speaker_devices_cache = []
        self._mic_devices_cache = []
        self._sound_ready = False
        self._sound_cache = {}
        self._sound_channels = {}
        self.custom_cursor_enabled = False
        self.cursor_window = None
        self._last_cursor_xy = None
        self._capture_busy = False
        self.ai_pending_path = None
        self.ai_pending_text = ""
        self.ai_undo_stack = []
        self.editor_undo_stack = []
        self.current_editor_saved_text = ""
        self.editor_dirty = False
        self._loading_editor = False

        if not self.ahk_path_v2.get():
            detected_v2 = find_ahk_exe("2")
            if detected_v2:
                self.ahk_path_v2.set(detected_v2)
                self.settings["ahk_path_v2"] = detected_v2
        write_json(SETTINGS_PATH, self.settings)

        self._configure_styles()
        self.init_sound_system()
        self._build()
        self.bind_ui_sounds()
        self.start_hotkeys()
        self.start_auto_refresh()
        self.root.bind("<Map>", self.restore_borderless_after_minimize)
        self.root.after(100, self.show_ready_window)
        self.root.protocol("WM_DELETE_WINDOW", self.close)




    def show_app_intro_animation(self):
        if getattr(self, "_intro_shown", False):
            return
        self._intro_shown = True

        try:
            self.root.withdraw()
            hide_console_if_present()
        except Exception:
            pass

        sound_duration = 4.0
        load_started = False
        if self.loading_sound_enabled.get():
            self.play_ui_sound("load", force=True, max_ms=int(sound_duration * 1000))
            load_started = bool(self._sound_channels.get("load"))

        intro = Toplevel(self.root)
        intro.overrideredirect(True)
        intro.attributes("-topmost", True)
        intro.configure(bg="#050006")

        w, h = 780, 440
        sw = intro.winfo_screenwidth()
        sh = intro.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        intro.geometry(f"{w}x{h}+{x}+{y}")

        canvas = Canvas(intro, width=w, height=h, bg="#050006", highlightthickness=0)
        canvas.pack(fill=BOTH, expand=True)

        fps = 30
        frames = max(60, int(sound_duration * fps))
        envelope = self.sound_envelope("load", frames, sound_duration)
        modules = [
            ("CORE", "boot shell"),
            ("REC", "input engine"),
            ("AHK", "hotkey bridge"),
            ("PY", "runtime pack"),
            ("WORK", "workspace"),
            ("REPLAY", "replay cache"),
            ("AUDIO", "sound bus"),
            ("UI", "interface"),
        ]
        spinner_frames = ["|", "/", "-", "\\"]

        def reveal_main_ui():
            try:
                channel = self._sound_channels.get("load")
                if channel:
                    channel.stop()
            except Exception:
                pass
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            try:
                intro.destroy()
            except Exception:
                pass
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.root.update_idletasks()
                self.force_taskbar_icon()
                self.ensure_desktop_shortcut()
                if self.auto_update.get():
                    self.root.after(1500, lambda: self.check_for_updates(auto=True))
            except Exception:
                pass

        anim_started = time.perf_counter()

        def draw(i=0):
            elapsed = time.perf_counter() - anim_started
            pct = min(1.0, elapsed / sound_duration)
            frame_index = min(len(envelope) - 1, max(0, int(pct * (len(envelope) - 1))))
            live = envelope[frame_index]
            nearby = envelope[max(0, frame_index - 2):min(len(envelope), frame_index + 3)]
            beat = max(live, max(nearby or [0.0]) * 0.82)
            canvas.delete("all")

            red = "#ff1744"
            red2 = "#a8002a"
            hot = "#ff4b6d"
            dim = "#24000b"
            bg = "#050006"

            canvas.create_rectangle(0, 0, w, h, fill=bg, outline="")
            for yy in range(-40, h + 60, 18):
                offset = int((i * 3 + yy) % 48)
                canvas.create_line(0, yy + offset, w, yy - 80 + offset, fill="#100007")
            for xx in range(40, w, 54):
                canvas.create_line(xx, 24, xx - 90, h - 24, fill="#0d0007")

            glow = int(70 + 120 * beat)
            border = hot if beat > 0.42 else red
            canvas.create_rectangle(18, 18, w - 18, h - 18, fill="#080008", outline=border, width=2)
            canvas.create_rectangle(32, 32, w - 32, h - 32, fill="#0d000d", outline="#3d0014", width=1)
            canvas.create_line(32, 32, 126, 32, fill=hot, width=3)
            canvas.create_line(w - 126, h - 32, w - 32, h - 32, fill=hot, width=3)
            canvas.create_polygon(32, 92, 70, 52, 144, 52, 114, 82, fill="#14000b", outline=red2)
            canvas.create_polygon(w - 32, h - 92, w - 70, h - 52, w - 144, h - 52, w - 114, h - 82, fill="#14000b", outline=red2)

            canvas.create_text(w // 2 + 2, 67 + 2, text="CODEHUB", fill="#3a000e", font=("Segoe UI", 34, "bold"))
            canvas.create_text(w // 2, 67, text="CODEHUB", fill="#fff4f7", font=("Segoe UI", 34, "bold"))
            canvas.create_text(w // 2, 100, text="macro maker / scripts / replay / tools", fill="#ff6b84", font=("Consolas", 10, "bold"))

            cx, cy = w // 2, 184
            pulse = 0.55 + 0.45 * math.sin(i * 0.16)
            core_r = 28 + int(10 * beat)
            for ring in range(6):
                rr = core_r + ring * 17 + int(pulse * 5)
                col = hot if ring < 2 or beat > 0.5 else red2
                canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=mix_hex(col, bg, ring * 0.11), width=2 if ring < 2 else 1)
            canvas.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r, fill=mix_hex(red, "#ffffff", min(0.35, beat * 0.35)), outline=hot, width=2)
            canvas.create_text(cx, cy, text="CH", fill="#120005", font=("Segoe UI", 18, "bold"))

            for n in range(40):
                a = (i * 0.055) + n * (math.pi * 2 / 40)
                rr = 78 + (n % 5) * 13 + int(beat * 9)
                x1 = cx + math.cos(a) * rr
                y1 = cy + math.sin(a) * rr
                x2 = cx + math.cos(a + 0.09) * (rr + 12)
                y2 = cy + math.sin(a + 0.09) * (rr + 12)
                col = hot if n % 4 == 0 else red
                canvas.create_line(x1, y1, x2, y2, fill=mix_hex(col, bg, 0.2), width=2 if beat > 0.55 else 1)

            wave_y = 286
            for n in range(52):
                bx = 52 + n * 13
                env_idx = min(len(envelope) - 1, max(0, frame_index - 26 + n))
                env = envelope[env_idx]
                long_buh = math.sin((n * 0.45) + i * 0.18) * 0.5 + 0.5
                impact = max(env, beat * 0.6)
                bh = 6 + int(12 * long_buh + 68 * impact)
                col = hot if env > 0.62 or n % 7 == 0 else red
                canvas.create_rectangle(bx, wave_y - bh, bx + 6, wave_y + bh // 4, fill=col, outline="")

            active_count = min(len(modules), max(1, int(pct * len(modules)) + 1))
            card_y = 314
            card_w = 82
            gap = 9
            start_x = (w - (len(modules) * card_w + (len(modules) - 1) * gap)) // 2
            for idx, (code, desc) in enumerate(modules):
                x0 = start_x + idx * (card_w + gap)
                loaded = idx < active_count - 1
                active = idx == active_count - 1
                border = hot if loaded else (red if active else "#3a0011")
                fill = "#1a0010" if active else "#0b0008"
                canvas.create_rectangle(x0, card_y, x0 + card_w, card_y + 42, fill=fill, outline=border, width=1)
                canvas.create_text(x0 + card_w // 2, card_y + 14, text=("OK " if loaded else "") + code, fill=border, font=("Consolas", 9, "bold"))
                canvas.create_text(x0 + card_w // 2, card_y + 30, text="READY" if loaded else ("SYNC" if active else "WAIT"), fill="#b65468", font=("Consolas", 7))

            active_desc = modules[min(len(modules) - 1, active_count - 1)][1]
            spinner = spinner_frames[i % len(spinner_frames)]
            canvas.create_rectangle(58, 366, w - 58, 392, fill="#120006", outline="#5a001d")
            canvas.create_text(76, 379, anchor="w", text=f"{spinner} {active_desc}...", fill="#ff6b84", font=("Consolas", 10, "bold"))
            canvas.create_text(w - 78, 379, anchor="e", text=f"{int(pct * 100):03d}%", fill="#ffffff", font=("Consolas", 10, "bold"))

            bar_x0, bar_y0 = 78, 406
            bar_x1, bar_y1 = w - 78, 421
            canvas.create_rectangle(bar_x0, bar_y0, bar_x1, bar_y1, outline="#5a001d", width=1)
            filled = int((bar_x1 - bar_x0 - 6) * pct)
            for chunk_x in range(0, filled, 20):
                x0 = bar_x0 + 3 + chunk_x
                x1 = min(bar_x0 + 3 + filled, x0 + 14)
                canvas.create_rectangle(x0, bar_y0 + 3, x1, bar_y1 - 3, fill=hot if chunk_x % 40 else red, outline="")

            if beat > 0.62:
                canvas.create_rectangle(0, 0, w, h, outline=hot, width=3)

            if pct < 1.0:
                intro.after(int(1000 / fps), lambda: draw(i + 1))
            else:
                intro.after(250, reveal_main_ui)

        intro.after(0, draw)

    def show_ready_window(self):
        # Keep the real app hidden until the splash animation is done.
        self.root.withdraw()
        self.root.update_idletasks()
        self.root.after(50, self.show_app_intro_animation)

    def init_sound_system(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            self._pygame = pygame
            self._sound_ready = True
            for name in ("load", "click", "tab"):
                self.load_sound(name)
        except Exception:
            self._pygame = None
            self._sound_ready = False

    def load_sound(self, name):
        if not self._sound_ready:
            return None
        if name in self._sound_cache:
            return self._sound_cache[name]
        path = first_asset_named(name)
        if not path:
            self._sound_cache[name] = None
            return None
        try:
            sound = self._pygame.mixer.Sound(str(path))
            self._sound_cache[name] = sound
            return sound
        except Exception:
            self._sound_cache[name] = None
            return None

    def sound_envelope(self, name, buckets=120, seconds=4.0):
        sound = self.load_sound(name)
        if not sound or not self._pygame:
            return [0.25] * buckets
        try:
            import array
            init = self._pygame.mixer.get_init() or (44100, -16, 2)
            freq = int(init[0] or 44100)
            channels = int(init[2] or 2)
            raw = sound.get_raw()
            samples = array.array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            total_frames = max(1, len(samples) // max(1, channels))
            limit_frames = min(total_frames, max(1, int(freq * seconds)))
            frames_per_bucket = max(1, limit_frames // buckets)
            envelope = []
            for b in range(buckets):
                start = b * frames_per_bucket * channels
                end = min(len(samples), start + frames_per_bucket * channels)
                if start >= end:
                    envelope.append(0.0)
                    continue
                peak = max(abs(v) for v in samples[start:end])
                envelope.append(min(1.0, peak / 32768.0))
            max_peak = max(envelope) or 1.0
            return [min(1.0, (v / max_peak) ** 0.55) for v in envelope]
        except Exception:
            return [0.25] * buckets

    def play_ui_sound(self, name, force=False, max_ms=None):
        if not force:
            if name == "click" and hasattr(self, "click_sounds_enabled") and not self.click_sounds_enabled.get():
                return
            if name == "tab" and hasattr(self, "tab_sounds_enabled") and not self.tab_sounds_enabled.get():
                return
            if name not in ("click", "tab") and hasattr(self, "ui_sounds_enabled") and not self.ui_sounds_enabled.get():
                return
        sound = self.load_sound(name)
        if not sound:
            return
        try:
            channel = sound.play()
            if channel:
                self._sound_channels[name] = channel
                if max_ms:
                    self.root.after(int(max_ms), lambda ch=channel: ch.stop())
        except Exception:
            pass

    def bind_ui_sounds(self):
        self.root.bind_all("<ButtonRelease-1>", self._on_global_click_sound, add="+")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self.play_ui_sound("tab"), add="+")
        if hasattr(self, "tools"):
            self.tools.bind("<<NotebookTabChanged>>", lambda _e: self.play_ui_sound("tab"), add="+")

    def _on_global_click_sound(self, event=None):
        widget = getattr(event, "widget", None)
        if not widget:
            return
        try:
            if widget == self.tabs or widget == getattr(self, "tools", None) or widget.winfo_class() == "TNotebook":
                return
        except Exception:
            pass
        if str(widget).startswith(str(self.root)):
            self.play_ui_sound("click")

    def install_custom_cursor(self):
        if not self.custom_cursor_enabled:
            return
        try:
            self.apply_hidden_cursor(self.root)
            cursor = Toplevel(self.root)
            cursor.overrideredirect(True)
            cursor.attributes("-topmost", True)
            cursor.configure(bg="#010101")
            try:
                cursor.attributes("-transparentcolor", "#010101")
            except Exception:
                pass
            canvas = Canvas(cursor, width=34, height=34, bg="#010101", highlightthickness=0)
            canvas.pack(fill=BOTH, expand=True)
            self.draw_codehub_cursor(canvas)
            cursor.geometry("34x34+-100+-100")
            self.cursor_window = cursor
            self.make_window_clickthrough(cursor)
            self.root.bind_all("<Motion>", self.move_custom_cursor, add="+")
            self.root.bind("<FocusOut>", lambda _e: self.hide_custom_cursor(), add="+")
            self.root.bind("<FocusIn>", lambda _e: self.show_custom_cursor(), add="+")
        except Exception:
            self.cursor_window = None

    def apply_hidden_cursor(self, widget):
        try:
            widget.configure(cursor="none")
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self.apply_hidden_cursor(child)
        except Exception:
            pass

    def draw_codehub_cursor(self, canvas):
        cyan = "#24f6ff"
        blue = "#0b77ff"
        dark = "#03121a"
        canvas.create_polygon(3, 2, 24, 12, 15, 16, 10, 30, fill=dark, outline=cyan, width=2)
        canvas.create_line(6, 6, 21, 13, fill="#b7fbff", width=1)
        canvas.create_polygon(15, 16, 25, 25, 20, 28, 11, 21, fill=blue, outline=cyan, width=1)
        canvas.create_line(4, 22, 10, 30, fill=cyan, width=2)
        canvas.create_oval(24, 3, 31, 10, outline=cyan, width=1)
        canvas.create_line(27, 1, 27, 12, fill=cyan, width=1)
        canvas.create_line(22, 6, 32, 6, fill=cyan, width=1)

    def make_window_clickthrough(self, window):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ex_style |= 0x00000020 | 0x00080000 | 0x00000080
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style)
        except Exception:
            pass

    def move_custom_cursor(self, event):
        if not self.cursor_window or not self.cursor_window.winfo_exists():
            return
        try:
            if self.root.state() == "iconic":
                self.hide_custom_cursor()
                return
            x = int(event.x_root) + 1
            y = int(event.y_root) + 1
            if self._last_cursor_xy == (x, y):
                return
            self._last_cursor_xy = (x, y)
            self.cursor_window.geometry(f"34x34+{x}+{y}")
            self.cursor_window.lift()
        except Exception:
            pass

    def hide_custom_cursor(self):
        try:
            if self.cursor_window and self.cursor_window.winfo_exists():
                self.cursor_window.geometry("34x34+-100+-100")
        except Exception:
            pass

    def show_custom_cursor(self):
        try:
            if self.cursor_window and self.cursor_window.winfo_exists():
                self.cursor_window.lift()
        except Exception:
            pass

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

    def ensure_desktop_shortcut(self):
        if os.name != "nt":
            return
        try:
            if getattr(sys, "frozen", False):
                exe_path = Path(sys.executable).resolve()
            else:
                exe_path = APP_ROOT / "CodeHub.exe"
                if not exe_path.exists():
                    exe_path = Path(r"F:\Auto Hotkey\Python\Apps\CodeHub.exe")
            if not exe_path.exists():
                return
            ps = (
                "$desktop=[Environment]::GetFolderPath('Desktop');"
                "$lnk=Join-Path $desktop 'CodeHub.lnk';"
                "$shell=New-Object -ComObject WScript.Shell;"
                "$s=$shell.CreateShortcut($lnk);"
                f"$s.TargetPath={json.dumps(str(exe_path))};"
                f"$s.WorkingDirectory={json.dumps(str(exe_path.parent))};"
                f"$s.IconLocation={json.dumps(str(exe_path) + ',0')};"
                "$s.Save();"
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden_process_flags(),
            )
        except Exception:
            pass

    #  Styles 

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

    #  Layout 

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
        self.body = Frame(self.root, bg=C["bg"])
        self.body.pack(fill=BOTH, expand=True)

        self.tabs = ttk.Notebook(self.body)
        self.tabs.pack(fill=BOTH, expand=True, padx=0, pady=0)

        self.tabs.add(self._recorder_tab(), text="  Recorder  ")
        self.tabs.add(self._workspace_tab(), text="  Workspace  ")
        self.tabs.add(self._tools_tab(), text="  Tools  ")
        self.tabs.add(self._review_tab(), text="  Replay  ")
        self.tabs.add(self._help_tab(), text="  Help  ")
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

    #  Recorder tab 

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
                     width=15, state="readonly").grid(row=0, column=3, padx=(0, 16))

        self.start_button = ttk.Button(ctrl, text="  F1  Start Recording",
                                        style="Green.TButton", command=self.start_recording)
        self.stop_button = ttk.Button(ctrl, text="  F2  Stop & Save",
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

    #  Workspace tab 

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
        self.file_tree.column("size", width=92, stretch=False)
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
        ttk.Button(fb2, text="Run ", style="Green.TButton", command=self.run_selected_file).pack(side=LEFT, fill=X, expand=True)

        # Editor panel
        etop = Frame(edit_frame, bg=C["bg"], pady=4)
        etop.pack(fill=X)
        ttk.Button(etop, text="Open Script", style="Ghost.TButton", command=self.open_script).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Save", style="Accent.TButton", command=self.save_script).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Save As", style="Ghost.TButton", command=self.save_script_as).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Undo", style="Ghost.TButton", command=self.undo_editor_change).pack(side=LEFT, padx=(0, 4))
        ttk.Button(etop, text="Run ", style="Green.TButton", command=self.run_open_script).pack(side=LEFT, padx=(0, 4))
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
        self.editor.bind("<Control-f>", self.show_editor_find)
        self.editor.bind("<Control-F>", self.show_editor_find)
        self.editor.bind("<Control-h>", self.show_editor_replace)
        self.editor.bind("<Control-H>", self.show_editor_replace)
        self.editor.bind("<<Modified>>", self.on_editor_modified)
        self.editor.bind("<Button-3>", self.editor_context_menu)
        self.editor.tag_configure("find_match", background=C["orange"], foreground="#000000")

        self.refresh_files()
        return tab

    #  Tools tab 

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
        self.builder_target_var = StringVar(value="")
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

        target_row = Frame(pad, bg=C["bg"], pady=4)
        target_row.pack(fill=X)
        ttk.Label(target_row, text="Target script:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        self.builder_target_combo = ttk.Combobox(target_row, textvariable=self.builder_target_var, values=[], state="readonly")
        self.builder_target_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        ttk.Button(target_row, text="Refresh", style="Small.TButton", command=self.refresh_builder_targets).pack(side=LEFT, padx=(0, 6))
        ttk.Button(target_row, text="Open Target", style="Ghost.TButton", command=self.builder_open_target).pack(side=LEFT)

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
        ttk.Button(buttons, text="Send to Editor", style="Ghost.TButton", command=self.builder_send_to_editor).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Screenshot BG", style="Small.TButton", command=self.builder_take_background_screenshot).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Choose BG", style="Small.TButton", command=self.builder_choose_background).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Clear BG", style="Small.TButton", command=self.builder_clear_background).pack(side=LEFT)

        panes = ttk.PanedWindow(pad, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True, pady=(8, 0))
        left = Frame(panes, bg=C["bg"])
        mid = Frame(panes, bg=C["bg"])
        right = Frame(panes, bg=C["bg"])
        panes.add(left, weight=2)
        panes.add(mid, weight=2)
        panes.add(right, weight=3)

        self._section(left, "Blocks")
        self.builder_list = self._code_box(left, height=22)
        self.builder_list.configure(fg=C["cyan"])
        self.builder_list.pack(fill=BOTH, expand=True)

        self._section(mid, "Drag Sandbox Preview")
        self.builder_canvas = Canvas(mid, bg="#0a0a0a", highlightthickness=1, highlightbackground=C["border"], width=720, height=460)
        self.builder_canvas.pack(fill=BOTH, expand=True)
        self.builder_canvas.bind("<ButtonPress-1>", self.builder_canvas_press)
        self.builder_canvas.bind("<B1-Motion>", self.builder_canvas_drag)
        self.builder_canvas.bind("<ButtonRelease-1>", self.builder_canvas_release)

        self._section(right, "Generated Code")
        self.builder_output = self._code_box(right, height=22)
        self.builder_output.configure(fg=C["green"])
        self.builder_output.pack(fill=BOTH, expand=True)
        self.builder_refresh_list()
        self.refresh_builder_targets()
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
        ttk.Button(ar, text=" Undo", style="Ghost.TButton", command=self.undo_ai_change).pack(side=LEFT, padx=(0, 6))
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
        ttk.Button(cr, text="Convert ", style="Accent.TButton", command=self.convert_code).pack(side=LEFT, padx=(0, 8))
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
        ttk.Button(pr, text="  Start Logging", style="Green.TButton", command=self.start_position_logging).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="  Stop", style="Ghost.TButton", command=self.stop_position_logging).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="Clear", style="Red.TButton", command=self.clear_position_log).pack(side=LEFT, padx=(0, 6))
        ttk.Button(pr, text="Insert into Editor", style="Accent.TButton", command=self.insert_position_log_into_editor).pack(side=LEFT)

        self.position_status = StringVar(value="Stopped    0 clicks")
        ttk.Label(pad, textvariable=self.position_status, style="Accent.TLabel").pack(anchor="w", pady=(0, 6))

        self.position_output = self._code_box(pad, height=24)
        self.position_output.configure(fg=C["green"])
        self.position_output.pack(fill=BOTH, expand=True)

        return tab

    #  Review tab 

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

        for txt, cmd in [("Load", self.load_review_recording), ("Play Preview", self.play_review),
                          ("Pause", self.pause_review), ("Stop", self.stop_visual_replay),
                          ("Rewind", self.rewind_review), ("Open Video", self.open_review_video),
                          ("Open Audio", self.open_review_audio)]:
            ttk.Button(top, text=txt, style="Ghost.TButton", command=cmd).pack(side=LEFT, padx=3)

        ttk.Label(top, text="Speed:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(10, 4))
        ttk.Combobox(top, textvariable=self.review_speed,
                     values=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
                     state="readonly", width=6).pack(side=LEFT)
        ttk.Label(top, text="FPS:", style="PanelMuted2.TLabel").pack(side=LEFT, padx=(10, 4))
        ttk.Combobox(top, textvariable=self.review_fps,
                     values=REPLAY_FPS_CHOICES,
                     state="readonly", width=6).pack(side=LEFT)
        ttk.Button(top, text="Save FPS", style="Ghost.TButton", command=self.save_permissions).pack(side=LEFT, padx=(6, 0))

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

    def _help_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])
        pad = self._pad_frame(tab)
        self._section(pad, "Help")
        ttk.Label(
            pad,
            text="Learn CodeHub step by step, open the full local guide, or jump to support.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        row = Frame(pad, bg=C["bg"], pady=8)
        row.pack(fill=X)
        ttk.Button(row, text="Start Tutorial", style="Accent.TButton", command=self.start_tutorial).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Open HTML Guide", style="Ghost.TButton", command=self.open_help_html).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Discord Support", style="Ghost.TButton", command=self.open_discord_support).pack(side=LEFT)
        self._section(pad, "Quick Notes")
        notes = self._text_box(pad, height=18, fg=C["text"])
        notes.pack(fill=BOTH, expand=True)
        notes.insert(END, "F1 starts recording. F2 stops and opens the save dialog. F9 exits CodeHub.\n")
        notes.insert(END, "Workspace edits are staged until you press Save. AI and builder changes do not auto-save.\n")
        notes.insert(END, "Right-click editor lines for copy, delete, ask assistant, or replay lookup.\n")
        notes.insert(END, "Replay FPS can be changed in Replay or Settings.\n")
        notes.configure(state="disabled")
        return tab

    #  Settings tab 

    def _settings_tab(self):
        tab = Frame(self.tabs, bg=C["bg"])

        # Scrollable settings page: fixes the hidden Data Paths section on smaller screens.
        outer = Frame(tab, bg=C["bg"])
        outer.pack(fill=BOTH, expand=True)
        canvas = Canvas(outer, bg=C["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        pad = Frame(canvas, bg=C["bg"], padx=14, pady=12)
        settings_window = canvas.create_window((0, 0), window=pad, anchor="nw")

        def _sync_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(settings_window, width=canvas.winfo_width())

        def _mousewheel(event):
            delta = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
            canvas.yview_scroll(delta, "units")

        pad.bind("<Configure>", _sync_scroll_region)
        canvas.bind("<Configure>", _sync_scroll_region)
        canvas.bind_all("<MouseWheel>", _mousewheel)

        self._section(pad, "Export Folder")
        ttk.Label(
            pad,
            text="This folder is where CodeHub saves generated/exported scripts. AutoHotkey itself is picked below as an .exe file.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(2, 6))
        er = Frame(pad, bg=C["bg"], pady=4)
        er.pack(fill=X)
        ttk.Entry(er, textvariable=self.export_dir_var).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(er, text="Browse", style="Ghost.TButton", command=self.choose_export_dir).pack(side=RIGHT)

        self._section(pad, "AutoHotkey Requirement")
        ahk_info = ttk.Label(
            pad,
            text="CodeHub supports AutoHotkey v2 and Python exports. AutoHotkey v1 is no longer supported because its GUI/runtime behavior is too unreliable across PCs.",
            style="Muted.TLabel",
            wraplength=900,
        )
        ahk_info.pack(anchor="w", pady=(2, 6))
        ahkr = Frame(pad, bg=C["bg"], pady=4)
        ahkr.pack(fill=X)
        ttk.Label(ahkr, text="Use: AutoHotkey v2", style="Muted.TLabel").pack(side=LEFT, padx=(0, 10))
        ttk.Button(ahkr, text="Auto Detect", style="Ghost.TButton", command=self.autodetect_ahk_paths).pack(side=LEFT, padx=(0, 8))
        ttk.Button(ahkr, text="Save AutoHotkey Settings", style="Accent.TButton", command=self.save_permissions).pack(side=LEFT)

        ahk2 = Frame(pad, bg=C["bg"], pady=4)
        ahk2.pack(fill=X)
        ttk.Label(ahk2, text="AHK v2:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Entry(ahk2, textvariable=self.ahk_path_v2).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        ttk.Button(ahk2, text="Browse", style="Ghost.TButton", command=lambda: self.choose_ahk_path("2")).pack(side=RIGHT)

        self._section(pad, "Appearance")
        ar = Frame(pad, bg=C["bg"], pady=4)
        ar.pack(fill=X)
        ttk.Label(ar, text="Theme:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(ar, textvariable=self.theme_mode,
                     values=["computer_auto", "dark", "light", "custom"],
                     state="readonly", width=15).pack(side=LEFT, padx=(0, 12))
        ttk.Label(ar, text="Font size:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(ar, textvariable=self.ui_font_size, values=["8", "9", "10", "11", "12"],
                     state="readonly", width=6).pack(side=LEFT, padx=(0, 12))
        ttk.Label(ar, text="Density:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(ar, textvariable=self.ui_density, values=["compact", "comfortable"],
                     state="readonly", width=12).pack(side=LEFT, padx=(0, 12))
        ttk.Button(ar, text="Apply", style="Accent.TButton", command=self.save_ui_settings).pack(side=LEFT)
        ttk.Button(ar, text="Toggle Fullscreen", style="Ghost.TButton", command=self.toggle_fullscreen).pack(side=LEFT, padx=(8, 0))

        cr = Frame(pad, bg=C["bg"], pady=4)
        cr.pack(fill=X)
        for label, var in [("BG", self.custom_bg), ("Panel", self.custom_panel), ("Text", self.custom_text), ("Accent", self.custom_accent)]:
            ttk.Label(cr, text=label + ":", style="Muted.TLabel").pack(side=LEFT, padx=(0, 4))
            ttk.Entry(cr, textvariable=var, width=10).pack(side=LEFT, padx=(0, 4))
            ttk.Button(cr, text="Pick", style="Small.TButton",
                       command=lambda v=var: self.pick_theme_color(v)).pack(side=LEFT, padx=(0, 8))
        ttk.Button(cr, text="Save Custom Theme", style="Ghost.TButton", command=self.save_ui_settings).pack(side=LEFT)

        self._section(pad, "Sounds")
        sr = Frame(pad, bg=C["bg"], pady=4)
        sr.pack(fill=X)
        ttk.Checkbutton(sr, text="Click sounds", variable=self.click_sounds_enabled, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Checkbutton(sr, text="Tab sounds", variable=self.tab_sounds_enabled, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Label(sr, text="Loading sound always on", style="Muted.TLabel").pack(side=LEFT, padx=(0, 12))
        ttk.Button(sr, text="Test Click", style="Ghost.TButton", command=lambda: self.play_ui_sound("click", force=True)).pack(side=LEFT, padx=(0, 6))
        ttk.Button(sr, text="Test Tab", style="Ghost.TButton", command=lambda: self.play_ui_sound("tab", force=True)).pack(side=LEFT)

        self._section(pad, "Updates")
        ur = Frame(pad, bg=C["bg"], pady=4)
        ur.pack(fill=X)
        ttk.Checkbutton(ur, text="Auto update on startup", variable=self.auto_update, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Button(ur, text="Check for Updates", style="Accent.TButton", command=self.check_for_updates).pack(side=LEFT, padx=(0, 8))
        ttk.Button(ur, text="Run Local Updater", style="Ghost.TButton", command=self.run_local_updater).pack(side=LEFT)

        self._section(pad, "Replay Capture")
        rr_hint = ttk.Label(
            pad,
            text="Replay is back to the original screenshot-frame preview. This is less smooth than video, but it reliably shows frames inside CodeHub without FFmpeg/OpenCV video playback issues.",
            style="Muted.TLabel",
            wraplength=900,
        )
        rr_hint.pack(anchor="w", pady=(2, 6))

        rr = Frame(pad, bg=C["bg"], pady=4)
        rr.pack(fill=X)
        ttk.Checkbutton(rr, text="Experimental OpenCV video capture", variable=self.record_replay_video, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Checkbutton(rr, text="Record replay audio WAV", variable=self.record_replay_audio, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Label(rr, text="Source:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(rr, textvariable=self.replay_audio_source,
                     values=["Game/System", "Microphone", "Both"],
                     state="readonly", width=13).pack(side=LEFT, padx=(0, 8))
        ttk.Button(rr, text="Refresh Devices", style="Small.TButton", command=self.refresh_audio_devices).pack(side=LEFT)

        rr_audio = Frame(pad, bg=C["bg"], pady=4)
        rr_audio.pack(fill=X)
        ttk.Label(rr_audio, text="Game/headphones:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        self.speaker_device_combo = ttk.Combobox(rr_audio, textvariable=self.replay_speaker_device,
                                                 values=self.speaker_device_names(), state="readonly", width=34)
        self.speaker_device_combo.pack(side=LEFT, padx=(0, 10))
        ttk.Label(rr_audio, text="Mic:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        self.mic_device_combo = ttk.Combobox(rr_audio, textvariable=self.replay_mic_device,
                                             values=self.mic_device_names(), state="readonly", width=34)
        self.mic_device_combo.pack(side=LEFT, padx=(0, 8))
        ttk.Label(
            pad,
            text="Game/headphones uses speaker loopback when available. Mic is only for voice. Choose Both if you want game sound plus mic mixed into one WAV.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(2, 6))
        ttk.Label(
            pad,
            text="CodeHub will not record microphone/headset devices here. Replay audio is only for game/system audio sources.",
            style="Muted.TLabel",
            wraplength=900,
        ).pack(anchor="w", pady=(0, 6))

        rr2 = Frame(pad, bg=C["bg"], pady=4)
        rr2.pack(fill=X)
        ttk.Checkbutton(rr2, text="Record screenshot frames for preview", variable=self.record_screenshots, command=self.save_permissions).pack(side=LEFT, padx=(0, 12))
        ttk.Label(rr2, text="FPS:", style="Muted.TLabel").pack(side=LEFT, padx=(0, 6))
        ttk.Combobox(rr2, textvariable=self.review_fps,
                    values=REPLAY_FPS_CHOICES,
                    state="readonly", width=6).pack(side=LEFT, padx=(0, 8))
        ttk.Button(rr2, text="Save Replay FPS", style="Ghost.TButton", command=self.save_permissions).pack(side=LEFT)

        self._section(pad, "Permissions")
        pr = Frame(pad, bg=C["bg"], pady=4)
        pr.pack(fill=X)
        ttk.Checkbutton(pr, text="Allow assistant to edit the open script", variable=self.ai_can_edit, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(pr, text="Allow assistant to delete selected files", variable=self.ai_can_delete, command=self.save_permissions).pack(anchor="w", pady=2)
        ttk.Checkbutton(pr, text="Allow assistant to run script commands", variable=self.ai_can_run, command=self.save_permissions).pack(anchor="w", pady=2)

        self._section(pad, "Data Paths")
        dr = Frame(pad, bg=C["bg"], pady=4)
        dr.pack(fill=X)
        self.data_paths_toggle_btn = ttk.Button(
            dr,
            text="Hide Data Paths" if self.show_data_paths.get() else "Show Data Paths",
            style="Ghost.TButton",
            command=self.toggle_data_paths,
        )
        self.data_paths_toggle_btn.pack(side=LEFT)
        info = self._text_box(pad, height=8, fg=C["text2"])
        self.data_paths_info = info
        info.pack(fill=BOTH, expand=True, pady=(4, 0))
        self.refresh_data_paths_info()

        return tab

    # 
    # All the original logic methods  completely unchanged
    # 

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
        self.review_video_path = None
        self.review_audio_path = None
        self.review_audio_error = ""
        self.review_video_meta = {}
        self.feed.delete("1.0", END)
        self.settings["default_export_kind"] = self.default_export_kind.get()
        write_json(SETTINGS_PATH, self.settings)
        self.feed.insert(END, f"  Recording started  mode: {self.mode.get()}  export: {self.default_export_kind.get()}\n")
        self.status.set(" Recording")
        self.status_bar.set_color(C["red"])
        self.start_button.state(["disabled"])
        self.stop_button.state(["!disabled"])
        self.rec_status_frame.configure(bg=C["red"])
        if self.record_replay_video.get():
            self.start_replay_video_capture()
        if self.record_replay_audio.get():
            self.start_replay_audio_capture()
        self.recorder.start(self.mode.get())
        self.capture_review_snapshot("start")
        if self.record_screenshots.get():
            screenshot_fps = self.review_screenshot_fps()
            self.root.after(max(16, int(1000 / screenshot_fps)), self.capture_review_tick)

    def stop_recording(self):
        if self.macro_locked or not self.is_recording:
            return
        self.is_recording = False
        self.capture_review_snapshot("stop")
        self.stop_replay_video_capture()
        self.stop_replay_audio_capture()
        events = self.recorder.stop()
        self.rec_status_frame.configure(bg=C["border"])
        self.status_bar.set_color(C["text3"])
        default_name = self.settings.get("default_script_name", "MyMacro")
        dialog = SaveRecordingDialog(self.root, default_name, self.default_export_kind.get())
        self.start_button.state(["!disabled"])
        self.stop_button.state(["disabled"])
        if not dialog.result:
            self.status.set(f"Discarded  ({len(events)} events)")
            self.feed.insert(END, "  Stopped  discarded (save cancelled)\n")
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
            "review_video": self.review_video_path or "",
            "review_video_meta": self.review_video_meta or {},
            "review_audio": self.review_audio_path or "",
            "review_audio_error": self.review_audio_error or "",
        }
        self.recordings.setdefault("recordings", []).append(record)
        write_json(RECORDINGS_PATH, self.recordings)
        self.settings["default_script_name"] = record["name"]
        self.settings["default_export_kind"] = self.default_export_kind.get()
        write_json(SETTINGS_PATH, self.settings)
        self.status.set(f"Saved  {record['name']}    {len(events)} events")
        self.feed.insert(END, f"  Stopped  saved '{record['name']}' ({len(events)} events) as {export_kind}\n")
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
                path = review_dir / f"{stamp}_{label}.jpg"
                with mss.mss() as grabber:
                    monitor = grabber.monitors[1]
                    shot = grabber.grab(monitor)
                    image = Image.frombytes("RGB", shot.size, shot.rgb)
                    image.thumbnail((960, 540))
                    image.save(path, quality=72)
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
        screenshot_fps = self.review_screenshot_fps()
        interval = max(16, int(1000 / screenshot_fps))
        self.root.after(interval, self.capture_review_tick)

    def review_screenshot_fps(self):
        requested = max(1, self.builder_number(self.review_fps.get(), 60))
        if self.record_replay_video.get():
            return min(12, requested)
        return min(30, requested)

    def start_replay_video_capture(self):
        self.review_video_path = None
        if not self.record_replay_video.get():
            return
        if self.replay_video_thread and self.replay_video_thread.is_alive():
            return
        try:
            replay_dir = DATA_DIR / "review_videos"
            replay_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = replay_dir / f"CodeHub_Replay_{stamp}.avi"
            fps = max(30, min(MAX_REPLAY_FPS, self.builder_number(self.review_fps.get(), 60)))
            self.review_video_path = str(out_path)
            self.review_video_meta = {
                "requested_fps": float(fps),
                "started": time.perf_counter(),
                "frames": 0,
                "duration": 0.0,
                "playback_fps": 30.0,
            }
            self.replay_video_stop_event = threading.Event()
            self.replay_video_start_time = time.perf_counter()
            self.replay_video_thread = threading.Thread(
                target=self._opencv_replay_worker,
                args=(str(out_path), fps, self.replay_video_stop_event),
                daemon=True,
            )
            self.replay_video_thread.start()
            self.status.set(f"Recording smooth replay video at {min(int(fps), 30)} FPS")
        except Exception as e:
            self.replay_video_thread = None
            self.review_video_path = None
            self.status.set(f"Replay video failed; screenshot fallback active: {e}")

    def _opencv_replay_worker(self, out_path, fps, stop_event):
        writer = None
        try:
            import cv2
            import mss
            import numpy as np

            # OpenCV recording is CPU-based, so keep it sane and reliable.
            fps = max(15, min(30, int(fps)))
            frame_delay = 1.0 / fps

            with mss.mss() as grabber:
                monitor = grabber.monitors[1]
                src_w = int(monitor.get("width", 0))
                src_h = int(monitor.get("height", 0))
                if src_w <= 0 or src_h <= 0:
                    raise RuntimeError("Could not detect screen size.")

                # Full 1080p/1440p at high FPS can create broken/laggy AVI files.
                # Downscale to 1280 wide by default for reliable smooth preview.
                max_w = 960
                if src_w > max_w:
                    scale = max_w / float(src_w)
                    width = max_w
                    height = int(src_h * scale)
                    if height % 2:
                        height -= 1
                else:
                    width, height = src_w, src_h

                # XVID is much lighter than raw screenshot playback and usually easier
                # for Windows to open than a huge MJPG file. MJPG is fallback.
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                writer = cv2.VideoWriter(str(out_path), fourcc, float(fps), (width, height))
                if not writer.isOpened():
                    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                    writer = cv2.VideoWriter(str(out_path), fourcc, float(fps), (width, height))
                if not writer.isOpened():
                    raise RuntimeError("OpenCV could not start video writer. Try reinstalling opencv-python.")

                next_frame = time.perf_counter()
                frames_written = 0
                while not stop_event.is_set():
                    shot = grabber.grab(monitor)
                    frame = np.array(shot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    if (width, height) != (src_w, src_h):
                        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                    writer.write(frame)
                    frames_written += 1

                    next_frame += frame_delay
                    sleep_for = next_frame - time.perf_counter()
                    if sleep_for > 0:
                        time.sleep(min(sleep_for, frame_delay))
                    else:
                        next_frame = time.perf_counter()

                duration = max(0.001, time.perf_counter() - self.replay_video_start_time) if self.replay_video_start_time else 0.0
                playback_fps = frames_written / duration if duration > 0 else fps
                self.review_video_meta = {
                    "requested_fps": float(fps),
                    "frames": int(frames_written),
                    "duration": float(duration),
                    "playback_fps": float(max(1.0, min(240.0, playback_fps))),
                    "width": int(width),
                    "height": int(height),
                }
                if frames_written < 3:
                    raise RuntimeError("Replay recording ended before enough frames were saved.")
        except Exception as e:
            self.root.after(0, lambda err=e: self.status.set(f"Replay video failed: {err}"))
            try:
                if out_path and Path(out_path).exists() and Path(out_path).stat().st_size < 8192:
                    Path(out_path).unlink(missing_ok=True)
            except Exception:
                pass
        finally:
            try:
                if writer:
                    writer.release()
            except Exception:
                pass
    def stop_replay_video_capture(self):
        event = self.replay_video_stop_event
        thread = self.replay_video_thread
        self.replay_video_stop_event = None
        self.replay_video_thread = None
        if event:
            event.set()
        if thread and thread.is_alive():
            try:
                thread.join(timeout=8)
            except Exception:
                pass
        # If OpenCV failed to create a playable file, do not save a fake video path.
        try:
            if self.review_video_path:
                p = Path(self.review_video_path)
                if not p.exists() or p.stat().st_size < 8192:
                    self.review_video_path = None
        except Exception:
            self.review_video_path = None

    def start_replay_audio_capture(self):
        self.review_audio_path = None
        self.review_audio_error = ""
        if self.replay_audio_thread and self.replay_audio_thread.is_alive():
            return
        try:
            source = self.replay_audio_source.get() if hasattr(self, "replay_audio_source") else "Game/System"
            speaker_name = self.replay_speaker_device.get() if hasattr(self, "replay_speaker_device") else "Default Speakers"
            mic_name = self.replay_mic_device.get() if hasattr(self, "replay_mic_device") else "Default Mic"
            audio_dir = DATA_DIR / "review_audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = audio_dir / f"CodeHub_ReplayAudio_{stamp}.wav"
            self.review_audio_path = str(out_path)
            self.replay_audio_stop_event = threading.Event()
            self.replay_audio_thread = threading.Thread(
                target=self._replay_audio_worker,
                args=(str(out_path), source, speaker_name, mic_name, self.replay_audio_stop_event),
                daemon=True,
            )
            self.replay_audio_thread.start()
            self.status.set(f"Recording replay audio: {source}")
        except Exception as e:
            self.review_audio_path = None
            self.review_audio_error = str(e)
            self.replay_audio_thread = None
            self.status.set(f"Replay audio failed: {e}")

    def _replay_audio_worker(self, out_path, source, speaker_name, mic_name, stop_event):
        try:
            self._soundcard_audio_worker(out_path, source, speaker_name, mic_name, stop_event)
        except Exception as e:
            error_text = str(e)
            self.review_audio_error = error_text
            self.root.after(0, lambda err=error_text: self.status.set(f"Replay audio failed: {err}"))
            try:
                if out_path and Path(out_path).exists() and Path(out_path).stat().st_size < 1024:
                    Path(out_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _soundcard_audio_worker(self, out_path, source, speaker_name, mic_name, stop_event):
        import wave
        import numpy as np
        import soundcard as sc

        sample_rate = 44100
        chunk = 1024
        source = str(source or "Game/System")

        loopback = self.resolve_soundcard_speaker(speaker_name)
        mic = self.resolve_soundcard_mic(mic_name)
        use_game = source in ("Game/System", "Both")
        use_mic = source in ("Microphone", "Both")

        if use_game and loopback is None:
            raise RuntimeError("No game/headphones loopback device found. Open Settings, press Refresh Devices, then choose a Game/headphones device.")
        if use_mic and mic is None:
            raise RuntimeError("No microphone device found. Try Refresh Devices or choose a different mic.")

        game_rec = loopback.recorder(samplerate=sample_rate, channels=[0, 1]) if use_game else None
        mic_rec = mic.recorder(samplerate=sample_rate, channels=[0, 1]) if use_mic else None

        def to_stereo(data):
            arr = np.asarray(data, dtype=np.float32)
            if arr.ndim == 1:
                arr = np.column_stack([arr, arr])
            if arr.shape[1] == 1:
                arr = np.repeat(arr, 2, axis=1)
            return arr[:, :2]

        managers = [rec for rec in (game_rec, mic_rec) if rec is not None]
        exits = []
        try:
            for rec in managers:
                exits.append(rec.__enter__())
            with wave.open(out_path, "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                while not stop_event.is_set():
                    mix = None
                    if use_game:
                        mix = to_stereo(exits[0].record(numframes=chunk))
                    if use_mic:
                        mic_index = 1 if use_game else 0
                        mic_data = to_stereo(exits[mic_index].record(numframes=chunk)) * 0.75
                        mix = mic_data if mix is None else mix + mic_data
                    mix = np.clip(mix if mix is not None else np.zeros((chunk, 2), dtype=np.float32), -1.0, 1.0)
                    wf.writeframes((mix * 32767.0).astype("<i2").tobytes())
        finally:
            for rec in reversed(managers):
                try:
                    rec.__exit__(None, None, None)
                except Exception:
                    pass

    def stop_replay_audio_capture(self):
        event = self.replay_audio_stop_event
        thread = self.replay_audio_thread
        self.replay_audio_stop_event = None
        self.replay_audio_thread = None
        if event:
            event.set()
        if thread and thread.is_alive():
            try:
                thread.join(timeout=5)
            except Exception:
                pass
        try:
            if self.review_audio_path:
                p = Path(self.review_audio_path)
                if not p.exists() or p.stat().st_size < 1024:
                    if not self.review_audio_error:
                        self.review_audio_error = "Replay audio was enabled, but no usable WAV was written. Pick a Game/headphones loopback device in Settings, press Refresh Devices, then record again."
                    self.review_audio_path = None
        except Exception:
            if not self.review_audio_error:
                self.review_audio_error = "Replay audio was enabled, but CodeHub could not verify the recorded WAV."
            self.review_audio_path = None

    def open_review_video(self):
        path = self.review_video_path
        if not path:
            _, rec = self.selected_review_recording()
            if rec:
                path = rec.get("review_video")
        if not path or not Path(path).exists():
            messagebox.showinfo(APP_NAME, "No replay video exists for this recording. Record a new macro with 'Record smooth replay video (no audio)' enabled.")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                webbrowser.open(Path(path).as_uri())
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open replay video.\n\n{e}")

    def open_review_audio(self):
        path = self.review_audio_path
        error_text = self.review_audio_error
        if not path:
            _, rec = self.selected_review_recording()
            if rec:
                path = rec.get("review_audio")
                error_text = error_text or rec.get("review_audio_error", "")
        if not path or not Path(path).exists():
            message = "No replay audio WAV exists for this recording."
            if error_text:
                message += f"\n\nLast audio capture error:\n{error_text}"
            else:
                message += "\n\nReplay audio is enabled for future recordings, but this saved recording does not have a WAV attached yet."
            message += "\n\nUse Settings > Replay audio, press Refresh Devices, choose your Game/headphones loopback device, then record a new macro."
            messagebox.showinfo(APP_NAME, message)
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                webbrowser.open(Path(path).as_uri())
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open replay audio.\n\n{e}")

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
        if export_kind == "Default":
            export_kind = self.default_export_kind.get()
        if export_kind == "AutoHotkey v2":
            if not self.ensure_ahk_available_for_action("2", "save an AutoHotkey v2 script"):
                return
            code = generate_ahk(rec["events"], rec["mode"], rec["name"])
            path = export_dir / f"{safe_name(rec['name'])}.ahk"
        else:
            code = generate_python(rec["events"], rec["mode"], rec["name"])
            path = export_dir / f"{safe_name(rec['name'])}.py"
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if path.suffix.lower() == ".py":
            launcher_path = path.with_suffix(".cmd")
            launcher_path.write_text(generate_python_launcher(path), encoding="utf-8", newline="\r\n")
            rec["python_launcher_path"] = str(launcher_path)
        rec["export_path"] = str(path)
        rec["export_missing"] = False
        write_json(RECORDINGS_PATH, self.recordings)
        self.current_editor_file = path
        self.editor.delete("1.0", END)
        self.editor.insert(END, code)
        self.editor_path.set(str(path))
        self.tabs.select(1)
        self.refresh_files()
        if path.suffix.lower() == ".py":
            messagebox.showinfo(APP_NAME, f"Exported:\n{path}\n\nPython launcher:\n{path.with_suffix('.cmd')}")
        else:
            messagebox.showinfo(APP_NAME, f"Exported:\n{path}")

    def delete_recording(self):
        idx, rec = self.selected_recording()
        if rec is None:
            return

        ep = Path(rec.get("export_path", ""))
        has_script = ep.exists()
        if has_script:
            result = messagebox.askyesnocancel(
                APP_NAME,
                f"Delete cached recording '{rec.get('name')}'?\n\n"
                f"Linked script file:\n{ep}\n\n"
                "Yes = delete cached recording AND exported script file\n"
                "No = delete cached recording only\n"
                "Cancel = do nothing",
            )
        else:
            result = messagebox.askyesnocancel(
                APP_NAME,
                f"Delete cached recording '{rec.get('name')}'?\n\n"
                "Yes = delete cached recording\n"
                "No = do nothing\n"
                "Cancel = do nothing",
            )

        if result is None or result is False:
            return

        if has_script:
            try:
                ep.unlink()
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not delete exported script file:\n{e}")
                return

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
        files = sorted([p for p in export_dir.iterdir() if p.is_file() and p.suffix.lower() in {".py",".ahk",".cmd",".txt"}])
        for p in files:
            if p.suffix.lower() == ".ahk":
                self.repair_generated_ahk_v1_loader(p, quiet=True)
        self._last_file_snapshot = {f"{p}|{p.stat().st_mtime}|{p.stat().st_size}" for p in files}
        for p in files:
            self.file_tree.insert("", END, iid=str(p), values=(p.name, format_size(p.stat().st_size)))
        if old_focus and self.file_tree.exists(old_focus):
            self.file_tree.focus(old_focus)
            self.file_tree.selection_set(old_sel or (old_focus,))
        if self.sync_recording_exports([p for p in files if p.suffix.lower() in {".py", ".ahk"}]):
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
                self.current_editor_saved_text = ""
                self.editor_dirty = False
                self.editor_undo_stack.clear()
                if hasattr(self, "editor"):
                    self.editor.delete("1.0", END)
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
            if p.is_file() and p.suffix.lower() in {".py",".ahk",".cmd",".txt"}
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
        self.review_video_path = rec.get("review_video") or None
        self.review_video_meta = rec.get("review_video_meta") or {}
        self.review_audio_path = rec.get("review_audio") or None
        self.review_audio_error = rec.get("review_audio_error") or ""
        self.review_shot_paths = [p for p in rec.get("review_screenshots", []) if Path(p).exists()]
        self.review_photo_cache.clear()
        self.review_shot_index = 0
        self.review_play_index = 0
        self.review_playing = False
        self.review_paused = False
        total_time = max([float(e.get("time",0)) for e in self.review_events] or [0])
        presses = [e for e in self.review_events if e.get("type") in ("key_press","key_char")]
        clicks = [e for e in self.review_events if e.get("type") == "mouse_click" and e.get("pressed")]
        self.review_output.delete("1.0", END)
        self.review_output.insert(END, f"Macro : {rec.get('name')}\n")
        self.review_output.insert(END, f"Mode  : {rec.get('mode')}    {len(self.review_events)} events    {total_time:.2f}s\n")
        self.review_output.insert(END, f"Keys  : {len(presses)} presses    {len(clicks)} clicks\n")
        video_exists = bool(self.review_video_path and Path(self.review_video_path).exists())
        if video_exists:
            self.review_output.insert(END, f"Video : {self.review_video_path}\n")
        if self.review_audio_path and Path(self.review_audio_path).exists():
            self.review_output.insert(END, f"Audio : {self.review_audio_path}\n")
        elif self.review_audio_error:
            self.review_output.insert(END, f"Audio : failed - {self.review_audio_error}\n")
        if self.review_shot_paths:
            self.review_output.insert(END, f"Frames: {len(self.review_shot_paths)} screenshots\n")
            self.show_review_frame(0)
        elif video_exists:
            self.review_output.insert(END, "\nVideo exists, but Play Preview uses screenshot frames. Press Open Video to watch the video.\n")
            self.review_image_label.configure(image="", text="No screenshot frames saved.\nPress Open Video for the AVI replay.")
        else:
            self.review_output.insert(END, "\nNo screenshots saved for this recording. Record again with screenshot frames enabled.\n")
            self.review_image_label.configure(image="", text="No replay screenshots saved.")
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
            cache_key = (str(path), max(360, self.review_image_label.winfo_width() or 640), max(240, self.review_image_label.winfo_height() or 360))
            if cache_key in self.review_photo_cache:
                self.review_photo = self.review_photo_cache[cache_key]
            else:
                img = Image.open(path).convert("RGB")
                img.thumbnail((cache_key[1], cache_key[2]))
                self.review_photo = ImageTk.PhotoImage(img)
                self.review_photo_cache[cache_key] = self.review_photo
                if len(self.review_photo_cache) > 90:
                    for old_key in list(self.review_photo_cache.keys())[:30]:
                        self.review_photo_cache.pop(old_key, None)
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

        video = self.review_video_path
        if not video:
            _, rec = self.selected_review_recording()
            if rec:
                video = rec.get("review_video")
        if video and Path(video).exists() and Image is not None and ImageTk is not None:
            meta_frames = int((getattr(self, "review_video_meta", {}) or {}).get("frames") or 0)
            if meta_frames == 0 or meta_frames >= 3:
                self.play_review_video(video)
                return

        # Screenshot/event preview is the default again. Open Video is separate.

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
        if self.review_video_playing:
            self.review_video_paused = not self.review_video_paused
            if self.review_audio_channel:
                try:
                    if self.review_video_paused:
                        self.review_audio_channel.pause()
                    else:
                        self.review_audio_channel.unpause()
                except Exception:
                    pass
            self.status.set("Video replay paused" if self.review_video_paused else "Video replay resumed")
            return
        if self.review_playing:
            self.review_paused = True
            self.status.set("Replay paused")

    def rewind_review(self):
        if self.review_video_playing:
            self.stop_visual_replay()
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
        self.review_video_playing = False
        self.review_video_paused = False
        if self.review_audio_channel:
            try:
                self.review_audio_channel.stop()
            except Exception:
                pass
            self.review_audio_channel = None
        self.review_play_index = 0
        self.status.set("Replay stopped")

    def play_review_video(self, video_path):
        if self.review_video_playing and self.review_video_paused:
            self.pause_review()
            return
        if self.review_video_playing:
            return
        self.stop_visual_replay()
        self.review_video_playing = True
        self.review_video_paused = False
        self.virtual_keys.delete("1.0", END)
        self.start_review_audio_if_available()
        self.review_video_thread = threading.Thread(target=self.review_video_worker, args=(str(video_path),), daemon=True)
        self.review_video_thread.start()

    def start_review_audio_if_available(self):
        path = self.review_audio_path
        if not path:
            _, rec = self.selected_review_recording()
            if rec:
                path = rec.get("review_audio")
        if not path or not Path(path).exists() or not self._sound_ready:
            return
        try:
            sound = self._pygame.mixer.Sound(str(path))
            self.review_audio_channel = sound.play()
        except Exception:
            self.review_audio_channel = None

    def review_video_worker(self, video_path):
        cap = None
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError("Could not open replay video.")
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            video_meta = getattr(self, "review_video_meta", {}) or {}
            macro_duration = max([float(e.get("time", 0)) for e in self.review_events] or [0.0])
            meta_duration = float(video_meta.get("duration") or 0.0)
            if frame_count > 1 and macro_duration > 0:
                fps = frame_count / macro_duration
            elif frame_count > 1 and meta_duration > 0:
                fps = frame_count / meta_duration
            else:
                fps = cap.get(cv2.CAP_PROP_FPS) or self.builder_number(self.review_fps.get(), 60)
            fps = max(1.0, min(240.0, float(fps)))
            frame_index = 0
            started = time.perf_counter()

            while self.review_video_playing:
                while self.review_video_paused and self.review_video_playing:
                    time.sleep(0.03)
                    started += 0.03
                if not self.review_video_playing:
                    break
                ok, frame = cap.read()
                if not ok:
                    break
                try:
                    speed = max(0.1, float(self.review_speed.get()))
                except Exception:
                    speed = 1.0
                target = started + (frame_index / fps) / speed
                wait = target - time.perf_counter()
                if wait > 0:
                    time.sleep(min(wait, 0.05))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                max_w = max(360, self.review_image_label.winfo_width() or 640)
                max_h = max(240, self.review_image_label.winfo_height() or 360)
                img.thumbnail((max_w, max_h))
                photo = ImageTk.PhotoImage(img)
                elapsed = frame_index / fps
                text = f"Video replay\nTime: {elapsed:.2f}s    Speed: {speed:.2f}x    Frame: {frame_index + 1}/{frame_count or '?'}"
                self.root.after(0, lambda p=photo, t=text: self.show_review_video_frame(p, t))
                self.root.after(0, lambda t=text: self.set_virtual_keys(t + "\n"))
                frame_index += 1
            self.root.after(0, lambda: self.status.set("Video replay finished"))
        except Exception as e:
            self.root.after(0, lambda err=e: self.status.set(f"Video replay failed, use Open Video: {err}"))
        finally:
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
            self.review_video_playing = False
            self.review_video_paused = False

    def show_review_video_frame(self, photo, text):
        self.review_photo = photo
        self.review_image_label.configure(image=self.review_photo, text=text, compound="top")

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
            text = f"Time: {t:.2f}s    Speed: {speed:.2f}x    Rate: {event_speed:.1f}/sec\n"
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

    def show_editor_find(self, event=None):
        self.open_find_replace(replace=False)
        return "break"

    def show_editor_replace(self, event=None):
        self.open_find_replace(replace=True)
        return "break"

    def open_find_replace(self, replace=False):
        if not hasattr(self, "editor"):
            return
        win = getattr(self, "find_window", None)
        if win and win.winfo_exists():
            win.lift()
            if replace and hasattr(self, "replace_row"):
                self.replace_row.pack(fill=X, pady=(6, 0))
            return

        win = Toplevel(self.root)
        self.find_window = win
        win.title("Find / Replace")
        win.configure(bg=C["panel"])
        win.resizable(False, False)
        win.transient(self.root)
        win.geometry("+{}+{}".format(self.root.winfo_rootx() + 80, self.root.winfo_rooty() + 80))

        pad = Frame(win, bg=C["panel"], padx=12, pady=12)
        pad.pack(fill=BOTH, expand=True)
        ttk.Label(pad, text="Find:", style="Muted.TLabel").pack(anchor="w")
        self.find_text_var = StringVar(value=getattr(self, "find_text_var", StringVar()).get() if hasattr(self, "find_text_var") else "")
        find_entry = ttk.Entry(pad, textvariable=self.find_text_var, width=42)
        find_entry.pack(fill=X, pady=(2, 6))

        self.replace_row = Frame(pad, bg=C["panel"])
        ttk.Label(self.replace_row, text="Replace:", style="Muted.TLabel").pack(anchor="w")
        self.replace_text_var = StringVar(value=getattr(self, "replace_text_var", StringVar()).get() if hasattr(self, "replace_text_var") else "")
        ttk.Entry(self.replace_row, textvariable=self.replace_text_var, width=42).pack(fill=X, pady=(2, 0))
        if replace:
            self.replace_row.pack(fill=X, pady=(6, 0))

        buttons = Frame(pad, bg=C["panel"], pady=8)
        buttons.pack(fill=X)
        ttk.Button(buttons, text="Find Next", style="Ghost.TButton", command=self.find_next_in_editor).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Replace", style="Ghost.TButton", command=self.replace_current_find).pack(side=LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Replace All", style="Accent.TButton", command=self.replace_all_in_editor).pack(side=LEFT)
        ttk.Button(buttons, text="Close", style="Ghost.TButton", command=win.destroy).pack(side=RIGHT)
        find_entry.bind("<Return>", lambda _e: self.find_next_in_editor())
        find_entry.focus_set()

    def clear_find_marks(self):
        if hasattr(self, "editor"):
            self.editor.tag_remove("find_match", "1.0", END)

    def find_next_in_editor(self):
        needle = self.find_text_var.get() if hasattr(self, "find_text_var") else ""
        if not needle:
            return
        self.clear_find_marks()
        start = self.editor.index("insert +1c")
        idx = self.editor.search(needle, start, END, nocase=False)
        if not idx:
            idx = self.editor.search(needle, "1.0", END, nocase=False)
        if not idx:
            self.status.set(f"Not found: {needle}")
            return
        end = f"{idx}+{len(needle)}c"
        self.editor.tag_add("find_match", idx, end)
        self.editor.mark_set("insert", end)
        self.editor.see(idx)
        self.status.set(f"Found: {needle}")

    def replace_current_find(self):
        needle = self.find_text_var.get() if hasattr(self, "find_text_var") else ""
        repl = self.replace_text_var.get() if hasattr(self, "replace_text_var") else ""
        ranges = self.editor.tag_ranges("find_match")
        if not needle or len(ranges) < 2:
            self.find_next_in_editor()
            ranges = self.editor.tag_ranges("find_match")
        if not needle or len(ranges) < 2:
            return
        old = self.editor_text()
        self.editor_undo_stack.append((old, "replace"))
        self.editor.delete(ranges[0], ranges[1])
        self.editor.insert(ranges[0], repl)
        self.clear_find_marks()
        self.on_editor_modified()
        self.find_next_in_editor()

    def replace_all_in_editor(self):
        needle = self.find_text_var.get() if hasattr(self, "find_text_var") else ""
        repl = self.replace_text_var.get() if hasattr(self, "replace_text_var") else ""
        if not needle:
            return
        old = self.editor_text()
        count = old.count(needle)
        if count <= 0:
            self.status.set(f"Not found: {needle}")
            return
        self.editor_undo_stack.append((old, f"replace all {needle}"))
        self.replace_editor_text(old.replace(needle, repl), "replace all")
        self.clear_find_marks()
        self.status.set(f"Replaced {count} match(es). Press Save to write the file.")

    def editor_text(self):
        return self.editor.get("1.0", "end-1c") if hasattr(self, "editor") else ""

    def on_editor_modified(self, _event=None):
        if not hasattr(self, "editor"):
            return
        try:
            self.editor.edit_modified(False)
        except Exception:
            pass
        if self._loading_editor:
            return
        self.editor_dirty = self.editor_text() != self.current_editor_saved_text
        if self.current_editor_file:
            suffix = "  * unsaved" if self.editor_dirty else ""
            self.editor_path.set(str(self.current_editor_file) + suffix)

    def mark_editor_saved(self):
        self.current_editor_saved_text = self.editor_text()
        self.editor_dirty = False
        if self.current_editor_file:
            self.editor_path.set(str(self.current_editor_file))

    def replace_editor_text(self, text, undo_label="edit"):
        old = self.editor_text()
        if old != text:
            self.editor_undo_stack.append((old, undo_label))
        self._loading_editor = True
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", text)
        self._loading_editor = False
        self.on_editor_modified()

    def undo_editor_change(self):
        if not self.editor_undo_stack:
            messagebox.showinfo(APP_NAME, "No editor change to undo.")
            return
        text, label = self.editor_undo_stack.pop()
        self._loading_editor = True
        self.editor.delete("1.0", END)
        self.editor.insert("1.0", text)
        self._loading_editor = False
        self.on_editor_modified()
        self.status.set(f"Undid {label}")

    def confirm_unsaved_editor(self):
        if not self.editor_dirty:
            return True
        result = messagebox.askyesnocancel(
            APP_NAME,
            "This script has unsaved changes.\n\nYes = save changes\nNo = discard changes\nCancel = stay on this script",
        )
        if result is None:
            return False
        if result:
            self.save_script(show_message=False)
            return not self.editor_dirty
        return True

    def editor_context_menu(self, event):
        index = self.editor.index(f"@{event.x},{event.y}")
        line_no = int(index.split(".")[0])
        import tkinter as tk
        menu = tk.Menu(self.root, tearoff=0, bg=C["panel"], fg=C["text"], activebackground=C["border2"], activeforeground=C["text"])
        menu.add_command(label="Copy this line", command=lambda: self.copy_editor_line(line_no))
        menu.add_command(label="Delete this line", command=lambda: self.delete_editor_line(line_no))
        menu.add_command(label="Ask assistant about this line", command=lambda: self.ask_ai_about_line(line_no))
        menu.add_separator()
        menu.add_command(label="Replay this line", command=lambda: self.review_line_in_replay(line_no))
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def editor_line_text(self, line_no):
        return self.editor.get(f"{line_no}.0", f"{line_no}.end")

    def copy_editor_line(self, line_no):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.editor_line_text(line_no))
        self.status.set(f"Copied line {line_no}")

    def delete_editor_line(self, line_no):
        old = self.editor_text()
        self.editor_undo_stack.append((old, f"delete line {line_no}"))
        self.editor.delete(f"{line_no}.0", f"{line_no + 1}.0")
        self.on_editor_modified()

    def ask_ai_about_line(self, line_no):
        line = self.editor_line_text(line_no)
        self.tabs.select(2)
        self.helper_question.delete("1.0", END)
        self.helper_question.insert(END, f"Explain or improve this line:\n{line}")
        self.ask_helper()

    def review_line_in_replay(self, line_no):
        self.tabs.select(3)
        self.load_review_recording()
        if not getattr(self, "review_events", []):
            return
        target_index = max(0, min(len(self.review_events) - 1, line_no - 1))
        event = self.review_events[target_index]
        self.review_play_index = target_index
        self.set_virtual_keys(f"Line {line_no} mapped near event {target_index + 1}:\n{event_line(event)}\n")
        if self.review_shot_paths:
            fi = min(len(self.review_shot_paths) - 1, int(target_index / max(1, len(self.review_events)) * len(self.review_shot_paths)))
            self.show_review_frame(fi)

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
        if self.editor_dirty and not self.confirm_unsaved_editor():
            return
        self.run_script(Path(self.current_editor_file))

    def run_script(self, path):
        path = Path(path)
        if not path.exists():
            messagebox.showerror(APP_NAME, f"Script does not exist:\n{path}")
            self.refresh_files()
            return
        try:
            if path.suffix.lower() == ".py":
                py_for_packages = python_command()
                if not py_for_packages:
                    self.missing_runtime_dialog("Python 3", python_install_url(), f"run {path.name}")
                    return
                if not self.ensure_python_script_requirements(path, py_for_packages):
                    return
                proc = self.launch_python_script_console(path, py_for_packages)
            elif path.suffix.lower() == ".ahk":
                version = ahk_required_version_for_file(path, self.ahk_version.get() or "2")
                if version == "1":
                    messagebox.showerror(
                        APP_NAME,
                        "AutoHotkey v1 scripts are no longer supported in CodeHub.\n\n"
                        "Re-export this macro as AutoHotkey v2 or Python.",
                        parent=self.root,
                    )
                    return
                ahk = self.selected_ahk_exe(version)
                if not ahk:
                    self.missing_ahk_dialog(version, f"run {path.name}")
                    return
                proc = subprocess.Popen(
                    [ahk, str(path)], cwd=str(path.parent),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags())
            elif path.suffix.lower() in {".cmd", ".bat"}:
                proc = subprocess.Popen(
                    ["cmd.exe", "/c", str(path)],
                    cwd=str(path.parent),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
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

    def launch_python_script_console(self, path, py_cmd):
        runner_dir = DATA_DIR / "script_runners"
        runner_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        runner = runner_dir / f"run_{safe_name(path.stem)}_{stamp}.cmd"
        py_line = command_to_cmdline(py_cmd)
        script_line = subprocess.list2cmdline([str(path)])
        req_path = APP_ROOT / "requirements.txt"
        fallback_packages = "pynput mss Pillow pytesseract opencv-python numpy pygame sounddevice soundcard certifi"
        runner.write_text(
            "\n".join([
                "@echo off",
                "setlocal",
                f"title CodeHub Script Runner - {path.name}",
                "color 0A",
                "echo ================================================================",
                "echo                    CodeHub Script Runner",
                "echo ================================================================",
                f"echo Script : {path}",
                f"echo Folder : {path.parent}",
                f"echo Python : {py_line}",
                "echo.",
                "echo [1/3] Checking Python...",
                f"{py_line} --version",
                "if errorlevel 1 (",
                "  echo.",
                "  echo [ERROR] Python could not start on this PC.",
                "  echo Install Python 3 from https://www.python.org/downloads/windows/",
                "  pause",
                "  exit /b 9009",
                ")",
                "echo.",
                "echo [2/3] Checking/installing CodeHub macro runtime...",
                f"if exist \"{req_path}\" (",
                f"  echo Using requirements: {req_path}",
                f"  {py_line} -m pip install --upgrade pip",
                f"  {py_line} -m pip install -r \"{req_path}\"",
                ") else (",
                "  echo requirements.txt not found, using built-in package list.",
                f"  {py_line} -m pip install --upgrade pip {fallback_packages}",
                ")",
                "if errorlevel 1 (",
                "  echo.",
                "  echo [ERROR] Requirement installation failed.",
                "  echo Make sure pip is enabled and this PC has internet access.",
                "  pause",
                "  exit /b 3",
                ")",
                f"{py_line} -c \"import pynput; import tkinter; print('runtime OK')\"",
                "if errorlevel 1 (",
                "  echo.",
                "  echo [ERROR] Runtime import check failed even after installing requirements.",
                "  echo Reinstall Python from python.org and make sure pip/tcl-tk are enabled.",
                "  pause",
                "  exit /b 4",
                ")",
                "echo.",
                "echo [3/3] Launching script...",
                "echo F1 start ^| F2 stop ^| Numpad 5 exit",
                "echo ---------------------------------------------------------------",
                f"{py_line} {script_line}",
                "set CODEHUB_SCRIPT_EXIT=%ERRORLEVEL%",
                "echo ---------------------------------------------------------------",
                "echo Script exited with code %CODEHUB_SCRIPT_EXIT%.",
                "if not \"%CODEHUB_SCRIPT_EXIT%\"==\"0\" (",
                "  echo.",
                "  echo The script crashed or Python rejected it. The error should be above.",
                "  pause",
                ")",
                "exit /b %CODEHUB_SCRIPT_EXIT%",
            ]),
            encoding="utf-8",
            newline="\r\n",
        )
        return subprocess.Popen(
            ["cmd.exe", "/c", str(runner)],
            cwd=str(path.parent),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )

    def repair_generated_ahk_v1_loader(self, path, quiet=False):
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        if "#Requires AutoHotkey v1.1" not in text:
            return
        original = text
        text = text.replace(
            "    global LoaderStatus, LoaderBar\n",
            "",
        )
        text = text.replace(
            "Gui, Loader:Add, Text, vLoaderStatus w300 Center y+6, CodeHub AutoHotkey v1 loader",
            "Gui, Loader:Add, Text, HwndLoaderStatusHwnd w300 Center y+6, CodeHub AutoHotkey v1 loader",
        )
        text = text.replace(
            "Gui, Loader:Add, Progress, vLoaderBar w300 h10 y+10 Background182434 c33FF66 Range0-100, 0",
            "Gui, Loader:Add, Progress, HwndLoaderBarHwnd w300 h10 y+10 Background182434 c33FF66 Range0-100, 0",
        )
        text = text.replace(
            "GuiControl, Loader:, LoaderBar, %val%",
            "GuiControl,, %LoaderBarHwnd%, %val%",
        )
        text = text.replace(
            "GuiControl, Loader:, LoaderStatus, Indexing input timing... %val%`%",
            "GuiControl,, %LoaderStatusHwnd%, Indexing input timing... %val%`%",
        )
        text = text.replace(
            "Gui, WM:New, +AlwaysOnTop -Caption +ToolWindow +E0x20\n",
            "Gui, WM:New, +AlwaysOnTop -Caption +ToolWindow +E0x20 +HwndWMHwnd\n",
        )
        text = text.replace(
            "WinSet, Transparent, 62, ahk_id %A_ScriptHwnd%",
            "WinSet, Transparent, 62, ahk_id %WMHwnd%",
        )
        if text == original:
            return
        try:
            Path(path).write_text(text, encoding="utf-8", newline="")
            if self.current_editor_file and Path(self.current_editor_file) == Path(path):
                self.current_editor_saved_text = text
                self.editor.delete("1.0", END)
                self.editor.insert(END, text)
                self.editor_dirty = False
            if not quiet:
                self.status.set(f"Repaired AHK v1 loader in {Path(path).name}")
        except Exception as e:
            if not quiet:
                messagebox.showwarning(APP_NAME, f"CodeHub found an old AHK v1 loader bug but could not repair it:\n{e}", parent=self.root)

    def ensure_python_script_requirements(self, path, py_cmd):
        requirements = required_packages_for_python_script(path)
        if not requirements:
            return True
        missing = missing_python_modules(py_cmd, requirements)
        if not missing:
            return True
        packages = sorted({package for _module, package in missing})
        command_text = " ".join(py_cmd + ["-m", "pip", "install"] + packages)
        ok = messagebox.askyesno(
            APP_NAME,
            "This Python script needs missing packages before it can run.\n\n"
            f"Script: {path.name}\n"
            f"Missing: {', '.join(packages)}\n\n"
            "Install them now?\n\n"
            f"Command:\n{command_text}",
            parent=self.root,
        )
        if not ok:
            self.status.set("Python requirements install cancelled")
            return False
        try:
            self.status.set(f"Installing Python packages: {', '.join(packages)}")
            self.root.update_idletasks()
            result = subprocess.run(
                py_cmd + ["-m", "pip", "install"] + packages,
                cwd=str(APP_ROOT),
                capture_output=True,
                text=True,
                timeout=240,
            )
            if result.returncode != 0:
                messagebox.showerror(
                    APP_NAME,
                    "Python package install failed.\n\n"
                    f"Command:\n{command_text}\n\n"
                    f"{(result.stderr or result.stdout or '').strip()[:2200]}",
                    parent=self.root,
                )
                self.status.set("Python requirements install failed")
                return False
            self.status.set("Python requirements installed")
            return True
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not install Python packages:\n{e}", parent=self.root)
            self.status.set("Python requirements install failed")
            return False

    def lock_for_macro(self, proc, label):
        self.macro_locked = True
        self.macro_process = proc
        self.macro_lock_kind = "process"
        self.show_lock_overlay(label)
        self.root.after(450, lambda: self.warn_if_macro_exited_immediately(proc, label))
        self.root.after(900, self.poll_macro_process)

    def warn_if_macro_exited_immediately(self, proc, label):
        if self.macro_process is not proc:
            return
        try:
            code = proc.poll()
        except Exception:
            return
        if code is None:
            return
        self.status.set(f"{label} exited immediately ({code})")
        messagebox.showwarning(
            APP_NAME,
            f"{label} closed immediately.\n\n"
            "That usually means Python/AutoHotkey rejected the script or a dependency is missing.\n\n"
            "For Python scripts, CodeHub now opens a Script Runner command prompt with the real error/logs.",
            parent=self.root,
        )

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
        parent = getattr(self, "body", self.root)
        overlay = Frame(parent, bg="#030608")
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.lift()
        overlay.bind("<Button>", lambda _: "break")
        overlay.bind("<Key>", lambda _: "break")
        parent.update_idletasks()
        panel = Frame(overlay, bg=C["panel2"], padx=32, pady=28)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(panel, text="LOCKED", style="LockPanel.TLabel").pack()
        ttk.Label(panel, text=f"Running: {label}\n\nClose the macro to continue.",
                  style="LockMuted.TLabel", justify="center").pack(pady=(10,0))
        overlay.focus_set()
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
        if getattr(self, "update_in_progress", False):
            return
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

    def cached_recordings_for_file(self, path):
        """Return indexes of cached recording entries that point at this exported script."""
        matches = []
        try:
            target = Path(path).resolve()
        except Exception:
            target = Path(path)
        for i, rec in enumerate(self.recordings.get("recordings", [])):
            ep = rec.get("export_path", "")
            if not ep:
                continue
            try:
                if Path(ep).resolve() == target:
                    matches.append(i)
            except Exception:
                if str(ep).lower() == str(path).lower():
                    matches.append(i)
        return matches

    def delete_selected_file(self):
        path = self.selected_file_path()
        if not path:
            return
        path = Path(path)
        if self.current_editor_file == path and self.editor_dirty and not self.confirm_unsaved_editor():
            return

        cached_indexes = self.cached_recordings_for_file(path)
        delete_cached = False
        if cached_indexes:
            names = []
            for i in cached_indexes:
                try:
                    names.append(self.recordings["recordings"][i].get("name", f"Recording {i + 1}"))
                except Exception:
                    names.append(f"Recording {i + 1}")
            result = messagebox.askyesnocancel(
                APP_NAME,
                "Delete this script file?\n\n"
                f"{path}\n\n"
                "This file is also linked to cached recording data:\n"
                + "\n".join(f"• {name}" for name in names)
                + "\n\nYes = delete script AND cached recording data\n"
                  "No = delete script file only\n"
                  "Cancel = do nothing",
            )
            if result is None:
                return
            delete_cached = bool(result)
        else:
            result = messagebox.askyesnocancel(
                APP_NAME,
                f"Delete script file?\n\n{path}\n\n"
                "Yes = delete script file\n"
                "No = do nothing\n"
                "Cancel = do nothing",
            )
            if result is None or result is False:
                return

        try:
            path.unlink()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not delete script file:\n{e}")
            return

        if delete_cached and cached_indexes:
            try:
                for i in sorted(cached_indexes, reverse=True):
                    self.recordings["recordings"].pop(i)
                write_json(RECORDINGS_PATH, self.recordings)
            except Exception as e:
                messagebox.showwarning(APP_NAME, f"Script was deleted, but cached recording data could not be removed:\n{e}")

        if self.current_editor_file == path:
            self.current_editor_file = None
            self.current_editor_saved_text = ""
            self.editor_dirty = False
            self.editor.delete("1.0", END)
            self.editor_path.set("No file open")

        self.refresh_recordings()
        self.refresh_files()
        self.status.set(f"Deleted {path.name}")

    def open_script(self):
        if not self.confirm_unsaved_editor():
            return
        path = filedialog.askopenfilename(
            initialdir=str(resolve_app_path(self.export_dir_var.get())),
            filetypes=[("Scripts", "*.py *.ahk *.cmd *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.load_script(Path(path))

    def load_script(self, path):
        path = Path(path)
        if self.current_editor_file and Path(self.current_editor_file) != path and not self.confirm_unsaved_editor():
            return
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        self._loading_editor = True
        self.editor.delete("1.0", END)
        self.editor.insert(END, text)
        self._loading_editor = False
        self.editor_undo_stack.clear()
        self.current_editor_file = path
        self.current_editor_saved_text = text
        self.editor_dirty = False
        self.editor_path.set(str(path))
        self.tabs.select(1)

    def save_script(self, show_message=True):
        if not self.current_editor_file:
            return self.save_script_as(show_message=show_message)

        path = Path(self.current_editor_file)
        text = self.editor_text()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            # Verify the disk file actually matches the editor before saying it saved.
            try:
                saved_text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                saved_text = None
            if saved_text is not None and saved_text != text:
                raise OSError("Save verification failed: file on disk did not match the editor text.")

            self.current_editor_file = path
            self.mark_editor_saved()
            self.refresh_files()
            self.status.set(f"Saved {path.name}")
            if show_message:
                messagebox.showinfo(APP_NAME, f"Saved:\n{path}")
            return True
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save script:\n{path}\n\n{e}")
            return False

    def save_script_as(self, show_message=True):
        while True:
            path = filedialog.asksaveasfilename(
                initialdir=str(resolve_app_path(self.export_dir_var.get())),
                defaultextension=".py",
                filetypes=[("Scripts", "*.py *.ahk *.cmd *.txt"), ("All files", "*.*")])
            if not path:
                return False

            path = Path(path)
            if path.exists():
                result = messagebox.askyesnocancel(
                    APP_NAME,
                    f"This file already exists:\n{path}\n\nYes = overwrite it\nNo = choose a different name\nCancel = stop saving",
                )
                if result is None:
                    return False
                if result is False:
                    continue

            self.current_editor_file = path
            return self.save_script(show_message=show_message)

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
            answers.append(f"Recordings: {RECORDINGS_PATH}    Settings: {SETTINGS_PATH}")
        if any(k in question for k in ("game","roblox","currency","read","ocr","screen")):
            answers.extend(self.knowledge.get("ocr", []))
        if not answers:
            answers = [
                "This helper is local and rule-based. It guides script edits but is not a cloud AI.",
                "Paste code into the Editor tab to edit it directly, or describe a change here.",
            ]
        if self.ai_can_edit.get():
            answers.append("Edit permission is ON  the safe header tool can modify the open script.")
        else:
            answers.append("Edit permission is OFF. Enable it in Settings  Permissions.")
        self.helper_answer.delete("1.0", END)
        self.helper_answer.insert(END, "\n".join(f"   {l}" for l in dict.fromkeys(answers)))

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
            new_text = text.rstrip() + f"\n\n{prefix} CodeHub assistant reviewed  no rewrite rule matched.\n"
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
        self.helper_answer.insert(END, "Proposed:\n" + "\n".join(f"   {i}" for i in notes))

    def apply_ai_review(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        if not self.ai_pending_path or not self.ai_pending_text:
            messagebox.showinfo(APP_NAME, "Generate a preview first.")
            return
        if self.current_editor_file != self.ai_pending_path:
            if not self.confirm_unsaved_editor():
                return
            self.load_script(self.ai_pending_path)
        self.ai_undo_stack.append((self.ai_pending_path, self.editor_text()))
        self.replace_editor_text(self.ai_pending_text, "AI change")
        self.status.set(f"AI change staged; press Save to write {self.ai_pending_path.name}")
        messagebox.showinfo(APP_NAME, "AI changes are staged in the editor.\nReview them, then press Save to write the file.")

    def undo_ai_change(self):
        if not self.ai_undo_stack:
            messagebox.showinfo(APP_NAME, "No AI change to undo.")
            return
        path, old_text = self.ai_undo_stack.pop()
        if self.current_editor_file != path:
            self.load_script(path)
        self.replace_editor_text(old_text, "AI undo")
        self.status.set(f"Undid AI change in editor: {path.name}")

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
        self.converter_output.insert(END, "Changes:\n" + "\n".join(f"   {i}" for i in notes))

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
        self.replace_editor_text(script + "\n", "converter output")
        self.tabs.select(1)
        self.status.set("Converted code staged in editor; press Save to write it")

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
        self.builder_draw_preview()

    def builder_clear(self):
        self.builder_blocks = []
        self.builder_refresh_list()
        self.builder_output.delete("1.0", END)
        self.builder_draw_preview()

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
        self.builder_draw_preview()

    def builder_generate(self):
        if self.builder_export.get() == "Python Tkinter":
            code = self.builder_python_code()
        else:
            code = self.builder_ahk_code()
        self.builder_output.delete("1.0", END)
        self.builder_output.insert(END, code)
        self.builder_draw_preview()

    def builder_send_to_editor(self):
        if not self.ai_can_edit.get():
            messagebox.showwarning(APP_NAME, "Enable edit permission in Settings first.")
            return
        code = self.builder_output.get("1.0", END).strip()
        if not code:
            self.builder_generate()
            code = self.builder_output.get("1.0", END).strip()
        self.replace_editor_text(code + "\n", "builder output")
        self.tabs.select(1)
        self.status.set("Builder code staged in editor; press Save to write it")

    def refresh_builder_targets(self):
        if not hasattr(self, "builder_target_combo"):
            return
        export_dir = resolve_app_path(self.export_dir_var.get()) if hasattr(self, "export_dir_var") else EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        values = [str(p) for p in sorted(export_dir.iterdir()) if p.is_file() and p.suffix.lower() in {".py", ".ahk", ".cmd", ".txt"}]
        self.builder_target_combo.configure(values=values)
        if self.builder_target_var.get() not in values and values:
            self.builder_target_var.set(values[0])

    def builder_open_target(self):
        value = self.builder_target_var.get()
        if value:
            self.load_script(Path(value))

    def builder_canvas_metrics(self):
        canvas = self.builder_canvas
        w = max(520, canvas.winfo_width() or 720)
        h = max(360, canvas.winfo_height() or 460)
        origin_x = 18
        origin_y = 40
        scale_x = (w - 36) / 520
        scale_y = (h - 58) / 360
        return w, h, origin_x, origin_y, scale_x, scale_y

    def builder_block_canvas_rect(self, block):
        _w, _h, ox, oy, sx, sy = self.builder_canvas_metrics()
        x = ox + block["x"] * sx
        y = oy + block["y"] * sy
        bw = max(36, block["w"] * sx)
        bh = max(18, block["h"] * sy)
        return x, y, x + bw, y + bh

    def builder_block_at_canvas(self, cx, cy):
        for index in range(len(self.builder_blocks) - 1, -1, -1):
            x1, y1, x2, y2 = self.builder_block_canvas_rect(self.builder_blocks[index])
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return index, x1, y1
        return None, 0, 0

    def builder_canvas_press(self, event):
        index, x1, y1 = self.builder_block_at_canvas(event.x, event.y)
        self.builder_selected_index = index
        self.builder_drag_offset = (event.x - x1, event.y - y1)
        self.builder_draw_preview()

    def builder_canvas_drag(self, event):
        if self.builder_selected_index is None:
            return
        _w, _h, ox, oy, sx, sy = self.builder_canvas_metrics()
        dx, dy = self.builder_drag_offset
        block = self.builder_blocks[self.builder_selected_index]
        nx = int(max(0, min(520 - block["w"], (event.x - dx - ox) / sx)))
        ny = int(max(0, min(360 - block["h"], (event.y - dy - oy) / sy)))
        block["x"] = nx
        block["y"] = ny
        self.builder_x.set(str(nx))
        self.builder_y.set(str(ny))
        self.builder_refresh_list()

    def builder_canvas_release(self, _event=None):
        if self.builder_selected_index is not None:
            self.builder_generate()
        self.builder_selected_index = None
        self.builder_drag_offset = (0, 0)
        self.builder_draw_preview()

    def builder_choose_background(self):
        path = filedialog.askopenfilename(
            title="Choose sandbox background image",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")],
        )
        if path:
            self.builder_background_image.set(path)
            self.save_permissions()
            self.builder_draw_preview()

    def builder_clear_background(self):
        self.builder_background_image.set("")
        self.builder_background_photo = None
        self.save_permissions()
        self.builder_draw_preview()

    def builder_take_background_screenshot(self):
        try:
            import mss
            from PIL import Image
            bg_dir = DATA_DIR / "builder_backgrounds"
            bg_dir.mkdir(parents=True, exist_ok=True)
            path = bg_dir / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with mss.mss() as grabber:
                monitor = grabber.monitors[1]
                shot = grabber.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                img.save(path)
            self.builder_background_image.set(str(path))
            self.save_permissions()
            self.builder_draw_preview()
            self.status.set("Builder background screenshot loaded")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not take screenshot background. Install mss/Pillow if needed.\n\n{e}")

    def builder_draw_preview(self):
        if not hasattr(self, "builder_canvas"):
            return
        canvas = self.builder_canvas
        canvas.delete("all")
        w, h, ox, oy, scale_x, scale_y = self.builder_canvas_metrics()

        bg_path = self.builder_background_image.get().strip() if hasattr(self, "builder_background_image") else ""
        if bg_path and Image is not None and ImageTk is not None and Path(bg_path).exists():
            try:
                img = Image.open(bg_path).convert("RGB")
                img.thumbnail((w, h))
                self.builder_background_photo = ImageTk.PhotoImage(img)
                canvas.create_rectangle(0, 0, w, h, fill="#050505", outline="")
                canvas.create_image(w // 2, h // 2, image=self.builder_background_photo, anchor="center")
                canvas.create_rectangle(0, 0, w, h, fill="", outline=C["border"], width=1)
            except Exception:
                canvas.create_rectangle(0, 0, w, h, fill="#090909", outline="")
        else:
            canvas.create_rectangle(0, 0, w, h, fill="#090909", outline="")
            canvas.create_rectangle(8, 8, w - 8, h - 8, fill="#0f0f0f", outline="#2a2a2a", width=1)

        canvas.create_text(18, 18, text="Drag blocks here  •  520x360 generated UI sandbox", fill=C["text"], anchor="nw", font=("Segoe UI", 10, "bold"))

        for i, block in enumerate(self.builder_blocks):
            x, y, x2, y2 = self.builder_block_canvas_rect(block)
            bw = x2 - x
            bh = y2 - y
            kind = block["kind"]
            selected = i == self.builder_selected_index
            fill = "#e8e8e8" if kind == "Button" else "#111111"
            fg = "#000000" if kind == "Button" else "#e8f0f8"
            outline = C["accent"] if selected else "#303030"
            width = 3 if selected else 1
            if kind == "Slider":
                canvas.create_rectangle(x, y, x + bw, y + bh, fill="#111111", outline=outline, width=width)
                canvas.create_line(x + 8, y + bh / 2, x + bw - 8, y + bh / 2, fill=C["cyan"], width=3)
                canvas.create_oval(x + bw / 2 - 5, y + bh / 2 - 5, x + bw / 2 + 5, y + bh / 2 + 5, fill="#e8e8e8", outline="")
            else:
                canvas.create_rectangle(x, y, x + bw, y + bh, fill=fill, outline=outline, width=width)
                text = block["text"][:24]
                if kind == "Checkbox":
                    canvas.create_rectangle(x + 6, y + 6, x + 18, y + 18, fill="#090909", outline=C["text2"] if not selected else C["accent"])
                    canvas.create_text(x + 24, y + bh / 2, text=text, fill=fg, anchor="w", font=("Segoe UI", 8))
                else:
                    canvas.create_text(x + bw / 2, y + bh / 2, text=text, fill=fg, font=("Segoe UI", 8, "bold" if kind == "Button" else "normal"))

    def builder_ahk_code(self):
        lines = [
            "#Requires AutoHotkey v2.0",
            "#SingleInstance Force",
            "",
            "; Built with CodeHub Code Builder.",
            "; Edit block positions by changing x/y/w/h values below.",
            "ui := Gui('+AlwaysOnTop', 'CodeHub Built UI')",
            f"; Preview background image: {self.builder_background_image.get() if hasattr(self, 'builder_background_image') else ''}",
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
            f"# Preview background image: {self.builder_background_image.get() if hasattr(self, 'builder_background_image') else ''}",
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
        body = []
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                body.append("")
                continue
            converted = None
            if stripped.startswith("#"):
                converted = "; " + stripped.lstrip("#").strip()
                notes.append("comments converted")
            elif re.match(r"time\.sleep\(([^)]+)\)", stripped):
                val = re.findall(r"time\.sleep\(([^)]+)\)", stripped)[0]
                try:
                    ms = int(float(val) * 1000)
                except Exception:
                    ms = 100
                converted = f"Sleep({ms})"
                notes.append("time.sleep converted to Sleep")
            elif re.search(r"mouse\.position\s*=", stripped):
                nums = re.findall(r"-?\d+", stripped)
                converted = f"MouseMove({nums[0]}, {nums[1]}, 0)" if len(nums) >= 2 else "; TODO: MouseMove(x, y, 0)"
                notes.append("mouse.position converted")
            elif "mouse.click" in stripped:
                nums = re.findall(r"-?\d+", stripped)
                converted = f"Click({nums[0]}, {nums[1]})" if len(nums) >= 2 else "Click()"
                notes.append("mouse.click converted")
            elif "mouse.press" in stripped:
                nums = re.findall(r"-?\d+", stripped)
                converted = f"Click(\"Down\", {nums[0]}, {nums[1]})" if len(nums) >= 2 else "Click(\"Down\")"
                notes.append("mouse.press converted")
            elif "mouse.release" in stripped:
                nums = re.findall(r"-?\d+", stripped)
                converted = f"Click(\"Up\", {nums[0]}, {nums[1]})" if len(nums) >= 2 else "Click(\"Up\")"
                notes.append("mouse.release converted")
            elif "keyboard.type" in stripped or ".type(" in stripped:
                found = re.findall(r"[\"'](.+?)[\"']", stripped)
                converted = f"Send({found[0]!r})".replace("'", '"') if found else "; TODO: Send(\"text\")"
                notes.append("keyboard.type converted")
            elif "keyboard.press" in stripped or ".press(" in stripped:
                found = re.findall(r"[\"'](.+?)[\"']", stripped)
                converted = f"Send(\"{{{found[0]} down}}\")" if found else "; TODO: Send(\"{Key down}\")"
                notes.append("keyboard.press converted")
            elif "keyboard.release" in stripped or ".release(" in stripped:
                found = re.findall(r"[\"'](.+?)[\"']", stripped)
                converted = f"Send(\"{{{found[0]} up}}\")" if found else "; TODO: Send(\"{Key up}\")"
                notes.append("keyboard.release converted")
            elif stripped.startswith(("import ", "from ", "def ", "class ", "if __name__")):
                converted = "; " + stripped
            else:
                converted = "; TODO: " + stripped
            body.append("    " + converted if converted else "")

        lines = [
            "#Requires AutoHotkey v2.0",
            "#SingleInstance Force",
            "; Converted by CodeHub. Review coordinates/timing before use.",
            "global running := false",
            "CreateWatermark()",
            "ShowCodeHubLoader(1300, 'Converted Python -> AutoHotkey v2')",
            "",
            "F1::",
            "{",
            "    global running",
            "    running := true",
            "    PlayMacro()",
            "}",
            "",
            "F2::",
            "{",
            "    global running",
            "    running := false",
            "}",
            "",
            "Numpad5::ExitApp",
            "",
            "PlayMacro()",
            "{",
            "    global running",
        ]
        lines.extend(body or ["    ; TODO: paste Python code to convert"])
        lines.extend([
            "    running := false",
            "}",
            "",
            "ShowCodeHubLoader(durationMs := 900, title := 'Loading macro')",
            "{",
            "    loader := Gui('+AlwaysOnTop -Caption +ToolWindow')",
            "    loader.BackColor := '081019'",
            "    loader.SetFont('s10 cEAF6FF', 'Segoe UI')",
            "    loader.AddText('w320 Center', 'AutoHotkey v2 · ' title)",
            "    loader.SetFont('s8 c8FD9FF', 'Segoe UI')",
            "    status := loader.AddText('w320 Center y+6', 'CodeHub converter loader')",
            "    bar := loader.AddProgress('w320 h10 y+10 Background182434 c33FF66 Range0-100', 0)",
            "    x := (A_ScreenWidth - 356) // 2",
            "    y := (A_ScreenHeight - 118) // 2",
            "    loader.Show('NoActivate x' x ' y' y ' w356 h118')",
            "    steps := 32",
            "    delay := Max(10, Floor(durationMs / steps))",
            "    Loop steps {",
            "        bar.Value := Floor((A_Index / steps) * 100)",
            "        status.Text := 'Loading... ' bar.Value '%'",
            "        Sleep(delay)",
            "    }",
            "    Sleep(200)",
            "    loader.Destroy()",
            "}",
            "",
            "CreateWatermark()",
            "{",
            "    wm := Gui('+AlwaysOnTop -Caption +ToolWindow +E0x20')",
            "    wm.BackColor := '101820'",
            "    wm.SetFont('s8 cD6DEE8', 'Segoe UI')",
            "    wm.AddText('w190 Center', 'Made by Cat · AutoHotkey v2')",
            "    WinSetTransparent(70, wm.Hwnd)",
            "    x := A_ScreenWidth - 210",
            "    wm.Show('NoActivate x' x ' y4 w200 h28')",
            "}",
        ])
        return "\n".join(lines), sorted(set(notes or ["wrapped Python snippet in runnable AHK v2 shell"]))

    def ahk_to_python(self, source):
        notes = []
        body = []
        for raw in source.splitlines():
            stripped = raw.strip()
            if not stripped:
                body.append("")
                continue
            low = stripped.lower()
            converted = None
            if stripped.startswith(";"):
                converted = "# " + stripped.lstrip(";").strip()
                notes.append("comments converted")
            elif low.startswith(("#requires", "#singleinstance", "global ", "return")) or stripped in ("{", "}") or stripped.endswith("::"):
                converted = "# " + stripped
            elif re.match(r"sleep[,\( ]+\s*(\d+)", stripped, re.I):
                ms = int(re.findall(r"\d+", stripped)[0])
                converted = f"time.sleep({ms/1000:.3f})"
                notes.append("Sleep converted")
            elif low.startswith("mousemove"):
                nums = re.findall(r"-?\d+", stripped)
                converted = f"mouse.position = ({nums[0]}, {nums[1]})" if len(nums) >= 2 else "# TODO: mouse.position = (x, y)"
                notes.append("MouseMove converted")
            elif low.startswith("click"):
                nums = re.findall(r"-?\d+", stripped)
                if "down" in low:
                    converted = "mouse.press(Button.left)"
                elif "up" in low:
                    converted = "mouse.release(Button.left)"
                elif len(nums) >= 2:
                    converted = f"mouse.position = ({nums[0]}, {nums[1]})\n    mouse.click(Button.left)"
                else:
                    converted = "mouse.click(Button.left)"
                notes.append("Click converted")
            elif low.startswith("send"):
                braced = re.findall(r"\{(.+?)\}", stripped)
                quoted = re.findall(r"[\"'](.+?)[\"']", stripped)
                val = quoted[0] if quoted else (braced[0] if braced else stripped.split(None, 1)[-1].replace(',', '').strip())
                if val:
                    converted = f"keyboard.type({val!r})"
                else:
                    converted = "# TODO: keyboard.type('text')"
                notes.append("Send converted")
            elif low.startswith("tooltip"):
                converted = "print(" + repr(stripped) + ")"
            else:
                converted = "# TODO: " + stripped
            body.append("    " + converted.replace("\n", "\n    "))

        lines = [
            '"""Converted by CodeHub. Review coordinates/timing before use."""',
            "import json",
            "import math",
            "import os",
            "import threading",
            "import time",
            "import tkinter as tk",
            "from pynput import keyboard as pynput_keyboard",
            "from pynput.keyboard import Controller as KeyboardController, Key",
            "from pynput.mouse import Button, Controller as MouseController",
            "",
            "SCRIPT_NAME = 'Converted_AHK_Macro'",
            "running = False",
            "keyboard = KeyboardController()",
            "mouse = MouseController()",
            "",
            "class CodeHubLoader:",
            "    def __init__(self, title='CodeHub Python Loader', duration_ms=1400):",
            "        self.title = title",
            "        self.duration_ms = max(900, int(duration_ms))",
            "        self.root = tk.Tk()",
            "        self.root.overrideredirect(True)",
            "        self.root.attributes('-topmost', True)",
            "        self.root.configure(bg='#07101F')",
            "        self.root.geometry(self._center_geometry(470, 210))",
            "        self.canvas = tk.Canvas(self.root, width=470, height=210, bg='#07101F', highlightthickness=0)",
            "        self.canvas.pack(fill='both', expand=True)",
            "    def _center_geometry(self, w, h):",
            "        self.root.update_idletasks()",
            "        return f'{w}x{h}+{(self.root.winfo_screenwidth()-w)//2}+{(self.root.winfo_screenheight()-h)//2}'",
            "    def run(self):",
            "        steps = 40",
            "        for i in range(steps + 1):",
            "            pct = i / steps",
            "            self.canvas.delete('all')",
            "            self.canvas.create_rectangle(0, 0, 470, 210, fill='#07101F', outline='')",
            "            self.canvas.create_text(235, 35, text='CodeHub Python Loader', fill='#57A6FF', font=('Segoe UI', 16, 'bold'))",
            "            self.canvas.create_text(235, 65, text=self.title, fill='#DDEBFF', font=('Segoe UI', 10))",
            "            for n in range(14):",
            "                a = i * 0.25 + n * 0.45",
            "                x = 235 + int(math.cos(a) * (25 + n % 4 * 8))",
            "                y = 130 + int(math.sin(a) * (25 + n % 4 * 8))",
            "                self.canvas.create_oval(x-3, y-3, x+3, y+3, fill='#57A6FF', outline='')",
            "            self.canvas.create_rectangle(42, 172, 428, 186, outline='#24496E', width=1)",
            "            self.canvas.create_rectangle(44, 174, 44 + int(382 * pct), 184, fill='#57A6FF', outline='')",
            "            self.canvas.create_text(235, 199, text=f'Python engine initializing... {int(pct*100)}%', fill='#9FCBFF', font=('Consolas', 9))",
            "            self.root.update()",
            "            time.sleep(self.duration_ms / 1000 / steps)",
            "        self.root.destroy()",
            "",
            "class Watermark:",
            "    def __init__(self):",
            "        self.root = tk.Tk()",
            "        self.root.overrideredirect(True)",
            "        self.root.attributes('-topmost', True)",
            "        self.root.attributes('-alpha', 0.46)",
            "        label = tk.Label(self.root, text='Made by Cat · Python', bg='#101820', fg='#57A6FF', font=('Segoe UI', 7, 'bold'), padx=7, pady=3)",
            "        label.pack()",
            "        self.root.update_idletasks()",
            "        x = self.root.winfo_screenwidth() - self.root.winfo_width() - 6",
            "        self.root.geometry(f'+{x}+4')",
            "    def show(self):",
            "        threading.Thread(target=self.root.mainloop, daemon=False).start()",
            "",
            "def play_macro():",
            "    global running",
            "    running = True",
            "    CodeHubLoader('Converted AutoHotkey -> Python', 1300).run()",
        ]
        lines.extend(body or ["    # TODO: paste AHK code to convert"])
        lines.extend([
            "    running = False",
            "",
            "def start_playback():",
            "    threading.Thread(target=play_macro, daemon=True).start()",
            "",
            "def stop_playback():",
            "    global running",
            "    running = False",
            "",
            "def on_press(key):",
            "    if key == Key.f1:",
            "        start_playback()",
            "    elif key == Key.f2:",
            "        stop_playback()",
            "    elif getattr(key, 'vk', None) == 101:",
            "        stop_playback()",
            "        return False",
            "",
            "if __name__ == '__main__':",
            "    CodeHubLoader('Starting converted macro', 1600).run()",
            "    WATERMARK = Watermark()",
            "    WATERMARK.show()",
            "    print('F1 start | F2 stop | Numpad 5 exit')",
            "    with pynput_keyboard.Listener(on_press=on_press) as listener:",
            "        listener.join()",
        ])
        return "\n".join(lines), sorted(set(notes or ["wrapped AHK snippet in runnable Python shell with loader/watermark"]))

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
        self.position_status.set(f" Logging    {len(self.position_log_events)} clicks")
        self.position_listener = mouse.Listener(on_click=self.on_position_log_click)
        self.position_listener.start()

    def stop_position_logging(self):
        self.position_logging = False
        if self.position_listener:
            self.position_listener.stop()
            self.position_listener = None
        self.position_status.set(f" Stopped    {len(self.position_log_events)} clicks")

    def clear_position_log(self):
        self.position_log_events.clear()
        self.position_output.delete("1.0", END)
        self.position_status.set(" Logging    0 clicks" if self.position_logging else " Stopped    0 clicks")

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
        self.position_status.set(f" Logging    {len(self.position_log_events)} clicks")

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

    def choose_ahk_path(self, version):
        version = "2"
        path = filedialog.askopenfilename(
            title=f"Choose AutoHotkey v{version} executable",
            filetypes=[("AutoHotkey executable", "AutoHotkey*.exe"), ("Executable", "*.exe"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        detected = detect_ahk_version(path)
        if detected and detected != str(version):
            ok = messagebox.askyesno(
                APP_NAME,
                f"That executable looks like AutoHotkey v{detected}, not v{version}.\n\nUse it anyway?",
                parent=self.root,
            )
            if not ok:
                return
        self.ahk_path_v2.set(path)
        self.save_permissions()

    def autodetect_ahk_paths(self):
        v2 = find_ahk_exe("2")
        if v2:
            self.ahk_path_v2.set(v2)
        if not v2:
            messagebox.showerror(APP_NAME, "AutoHotkey v2 was not found. Install AutoHotkey v2, then restart CodeHub.", parent=self.root)
            return
        self.ahk_version.set("2")
        self.save_permissions()
        messagebox.showinfo(APP_NAME, "AutoHotkey v2 detection complete.", parent=self.root)


    def missing_ahk_dialog(self, version=None, action="use AutoHotkey scripts"):
        version = "2"
        missing = describe_missing_ahk(version)
        detail = (
            f"{missing}\n\n"
            f"CodeHub can still open and Python scripts still work.\n\n"
            "Missing: AutoHotkey v2\n"
            f"Action blocked: {action}\n\n"
            "Install AutoHotkey v2, restart CodeHub, then try again.\n\n"
            "Open the AutoHotkey download page now?"
        )
        self.missing_runtime_dialog(
            "AutoHotkey v2",
            ahk_install_url(version),
            action,
            detail,
        )

    def missing_runtime_dialog(self, name, url, action, detail=None):
        win = Toplevel(self.root)
        win.title(f"Install {name}")
        win.configure(bg=C["panel"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.geometry("+{}+{}".format(self.root.winfo_rootx() + 140, self.root.winfo_rooty() + 120))

        pad = Frame(win, bg=C["panel"], padx=16, pady=14)
        pad.pack(fill=BOTH, expand=True)
        ttk.Label(pad, text=f"{name} is required", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            pad,
            text=detail or f"CodeHub cannot {action} until {name} is installed on this PC.\n\nDownload link:\n{url}",
            style="Muted.TLabel",
            wraplength=520,
        ).pack(anchor="w", pady=(0, 12))
        row = Frame(pad, bg=C["panel"])
        row.pack(fill=X)

        def copy_link():
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.status.set(f"Copied {name} download link")

        ttk.Button(row, text="Open Browser", style="Accent.TButton", command=lambda: webbrowser.open(url)).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Copy Link", style="Ghost.TButton", command=copy_link).pack(side=LEFT, padx=(0, 8))
        ttk.Button(row, text="Close", style="Ghost.TButton", command=win.destroy).pack(side=RIGHT)

    def ensure_ahk_available_for_action(self, version=None, action="use AutoHotkey"):
        version = "2"
        if self.selected_ahk_exe(version):
            return True
        self.missing_ahk_dialog(version, action)
        return False

    def selected_ahk_exe(self, version=None):
        custom = self.ahk_path_v2.get()
        ahk = find_ahk_exe("2", custom)
        return ahk

    def save_permissions(self):
        self.settings["ai_can_edit"] = self.ai_can_edit.get()
        self.settings["ai_can_delete"] = self.ai_can_delete.get()
        self.settings["ai_can_run"] = self.ai_can_run.get()
        self.ahk_version.set("2")
        self.settings["ahk_version"] = "2"
        self.settings["ahk_path_v2"] = self.ahk_path_v2.get().strip()
        self.settings["record_screenshots"] = self.record_screenshots.get()
        self.settings["record_replay_video"] = self.record_replay_video.get()
        self.settings["record_replay_audio"] = self.record_replay_audio.get()
        self.settings["replay_audio_source"] = self.replay_audio_source.get()
        self.settings["replay_audio_device"] = self.replay_audio_device.get()
        self.settings["replay_speaker_device"] = self.replay_speaker_device.get()
        self.settings["replay_mic_device"] = self.replay_mic_device.get()
        self.settings["allow_headset_mic_audio"] = self.allow_headset_mic_audio.get()
        self.settings["ui_sounds_enabled"] = self.ui_sounds_enabled.get()
        self.settings["click_sounds_enabled"] = self.click_sounds_enabled.get()
        self.settings["tab_sounds_enabled"] = self.tab_sounds_enabled.get()
        self.loading_sound_enabled.set(True)
        self.settings["loading_sound_enabled"] = True
        self.settings["show_data_paths"] = self.show_data_paths.get()
        if hasattr(self, "builder_background_image"):
            self.settings["builder_background_image"] = self.builder_background_image.get().strip()
        self.settings["auto_update"] = self.auto_update.get()
        fps = max(1, min(MAX_REPLAY_FPS, self.builder_number(self.review_fps.get(), 60)))
        self.review_fps.set(str(fps))
        self.settings["review_capture_fps"] = fps
        self.settings["review_capture_interval_ms"] = max(1, int(1000 / fps))
        write_json(SETTINGS_PATH, self.settings)
        self.status.set("Settings saved")

    def latest_github_sha(self):
        payload = github_json_request(GITHUB_API_LATEST, timeout=15)
        sha = str(payload.get("sha", "")).strip()
        if not sha:
            raise RuntimeError("GitHub did not return a commit SHA.")
        return sha

    def latest_github_file_sha(self):
        api_url = GITHUB_API_MAIN_EXE if getattr(sys, "frozen", False) else GITHUB_API_MAIN_SOURCE
        payload = github_json_request(api_url, timeout=15)
        sha = str(payload.get("sha", "")).strip()
        if not sha:
            raise RuntimeError("GitHub did not return a file SHA.")
        return sha

    def latest_github_release(self):
        payload = github_json_request(GITHUB_API_LATEST_RELEASE, timeout=15)
        tag = str(payload.get("tag_name", "")).strip()
        asset_url = GITHUB_EXE_URL
        for asset in payload.get("assets", []) or []:
            if str(asset.get("name", "")).lower() == "codehub.exe":
                asset_url = str(asset.get("browser_download_url") or asset_url)
                break
        if not tag:
            raise RuntimeError("GitHub did not return a release tag.")
        return tag, asset_url

    def check_for_updates(self, auto=False):
        self.status.set("Checking GitHub file for updates...")

        def worker():
            try:
                latest_commit = self.latest_github_sha()
                latest_sha = self.latest_github_file_sha()
                latest_tag = build_version(BUILD_NUMBER)
                asset_url = GITHUB_MAIN_EXE_URL
                local_path = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__).resolve()
                current_sha = git_blob_sha_for_file(local_path)
                has_update = bool(latest_sha and latest_sha != current_sha)
                if not has_update:
                    remember_update_sha(self.settings, latest_commit, latest_tag)
                self.root.after(0, lambda: self.finish_update_check(latest_commit, has_update, auto, asset_url, latest_tag, latest_sha, current_sha))
            except Exception as exc:
                if not auto:
                    self.root.after(0, lambda: messagebox.showerror(APP_NAME, f"Update check failed:\n{exc}"))
                self.root.after(0, lambda: self.status.set("Update check failed" if not auto else "Ready"))

        threading.Thread(target=worker, daemon=True).start()

    def finish_update_check(self, latest_sha, has_update, auto, asset_url=None, latest_tag=None, remote_file_sha=None, local_file_sha=None):
        short_sha = str(latest_sha or "")[:7]
        short_remote_file = str(remote_file_sha or "")[:7]
        short_local_file = str(local_file_sha or "")[:7]
        version_label = str(latest_tag or build_version(BUILD_NUMBER))
        if not has_update:
            self.status.set(f"Already up to date    {version_label}    {short_sha}    file {short_local_file}")
            if not auto:
                messagebox.showinfo(
                    APP_NAME,
                    "CodeHub is already up to date.\n\n"
                    f"Version: {version_label}\n"
                    f"Commit: {short_sha}\n"
                    f"File: {short_local_file}",
                )
            return
        if auto and not getattr(sys, "frozen", False):
            self.status.set(f"Source update available    {version_label}    {short_sha}    file {short_remote_file}")
            return
        if auto:
            self.status.set(f"Update available    {version_label}    {short_sha}    file {short_remote_file}")
            self.root.after(500, lambda: self.download_and_apply_update(latest_sha, asset_url or GITHUB_MAIN_EXE_URL, latest_tag=version_label))
            return
        else:
            should_update = messagebox.askyesno(
                APP_NAME,
                "Update found on GitHub.\n\n"
                f"Version label: {version_label}\n"
                f"Latest commit: {short_sha}\n\n"
                f"Your file: {short_local_file}\n"
                f"GitHub file: {short_remote_file}\n\n"
                "Download the latest CodeHub.exe now?",
            )
        if should_update:
            self.download_and_apply_update(latest_sha, asset_url or GITHUB_MAIN_EXE_URL, latest_tag=version_label)
        else:
            self.status.set(f"Update available    {version_label}    {short_sha}")

    def download_and_apply_update(self, latest_sha, asset_url=None, latest_tag=None):
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                APP_NAME,
                "Source mode detected.\n\n"
                "GitHub has a different source file, but source mode will not replace itself. "
                "Use Github.bat to rebuild/push a compiled app update, or run AppUpdater.bat to rebuild your local exe.",
            )
            return

        self.update_in_progress = True
        self.macro_locked = False
        self.macro_process = None
        self.macro_lock_kind = "process"
        self.update_in_progress = False
        try:
            if self.lock_overlay and self.lock_overlay.winfo_exists():
                self.lock_overlay.destroy()
        except Exception:
            pass
        self.lock_overlay = None
        self.lock_window = None

        exe_path = Path(sys.executable).resolve()
        app_dir = exe_path.parent
        cmd_path = app_dir / "CodeHub_apply_update.cmd"
        current_pid = os.getpid()
        tmp_exe = Path(tempfile.gettempdir()) / f"CodeHub_update_{current_pid}.exe"

        asset_url = asset_url or GITHUB_MAIN_EXE_URL
        latest_sha = str(latest_sha or "").strip()
        latest_tag = str(latest_tag or "")
        marker_path = UPDATE_MARKER_PATH

        script = textwrap.dedent(f"""\
    @echo off
    setlocal EnableExtensions
    color 0A
    title CodeHub Update
    cd /d "{app_dir}"

    set "LOG={app_dir}\\CodeHub_update_log.txt"
    set "URL={asset_url}"
    set "TMP={tmp_exe}"
    set "EXE={exe_path}"
    set "APPDIR={app_dir}"
    set "MARKER={marker_path}"
    set "LATEST_SHA={latest_sha}"
    set "LATEST_TAG={latest_tag}"

    echo ================================================================>>"%LOG%"
    echo CodeHub update started %date% %time%>>"%LOG%"
    echo URL: %URL%>>"%LOG%"
    echo EXE: %EXE%>>"%LOG%"
    echo.
    echo [CodeHub] downloading latest commit build...

    if exist "%TMP%" del /f /q "%TMP%" >nul 2>&1
    curl.exe -L --fail -A "CodeHub-Updater" -o "%TMP%" "%URL%" >>"%LOG%" 2>&1
    if errorlevel 1 (
        echo [CodeHub] curl download failed. Trying Windows download fallback...
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%TMP%' -UseBasicParsing -Headers @{{'User-Agent'='CodeHub-Updater'}}" >>"%LOG%" 2>&1
        if errorlevel 1 (
            echo [CodeHub] download failed. Log: %LOG%
            pause
            exit /b 1
        )
    )

    if not exist "%TMP%" (
        echo [CodeHub] download did not create a file. Log: %LOG%
        pause
        exit /b 1
    )

    for %%A in ("%TMP%") do set "SIZE=%%~zA"
    echo [CodeHub] downloaded %SIZE% bytes
    echo Downloaded bytes: %SIZE%>>"%LOG%"
    if not defined SIZE (
        echo [CodeHub] could not read downloaded file size. Log: %LOG%
        pause
        exit /b 1
    )
    if %SIZE% LSS 1048576 (
        echo [CodeHub] downloaded file is too small, refusing to replace the app. Log: %LOG%
        pause
        exit /b 1
    )

    echo [CodeHub] waiting for old CodeHub process to close...
    :WAIT_CODEHUB_CLOSE
    tasklist /FI "PID eq {current_pid}" | find "{current_pid}" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto WAIT_CODEHUB_CLOSE
    )

    echo [CodeHub] replacing executable...
    set "COPIED=0"
    for /L %%I in (1,1,20) do (
        copy /y "%TMP%" "%EXE%" >>"%LOG%" 2>&1
        if not errorlevel 1 (
            set "COPIED=1"
            goto COPY_DONE
        )
        echo [CodeHub] replace attempt %%I failed, retrying...
        timeout /t 1 /nobreak >nul
    )

    :COPY_DONE
    if not "%COPIED%"=="1" (
        echo [CodeHub] could not replace CodeHub.exe. Log: %LOG%
        pause
        exit /b 1
    )

    echo [CodeHub] saving installed commit marker...
    for %%D in ("%MARKER%") do if not exist "%%~dpD" mkdir "%%~dpD" >nul 2>&1
    >"%MARKER%" echo %LATEST_SHA%

    echo [CodeHub] restarting CodeHub...
    start "" /D "%APPDIR%" "%EXE%"
    timeout /t 2 /nobreak >nul
    del /f /q "%TMP%" >nul 2>&1

    echo [CodeHub] updated successfully. Closing updater...
    echo CodeHub update finished %date% %time%>>"%LOG%"
    timeout /t 1 /nobreak >nul
    exit /b 0
    """)

        cmd_path.write_text(script, encoding="utf-8")
        if os.name == "nt":
            try:
                subprocess.run(
                    ["attrib", "+h", str(cmd_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags(),
                )
            except Exception:
                pass

        if os.name == "nt":
            subprocess.Popen(
                ["cmd.exe", "/c", "call", str(cmd_path)],
                cwd=str(app_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(["sh", str(cmd_path)], cwd=str(app_dir))

        self.status.set("Updater console opened. CodeHub will force-close in a moment...")
        self.root.after(700, self.force_close_for_update)

    def run_local_updater(self):
        candidates = [
            APP_ROOT / "AppUpdater.bat",
            Path(r"F:\Auto Hotkey\Python\CodeHub\AppUpdater.bat"),
        ]

        updater = next((path for path in candidates if path.exists()), None)

        if not updater:
            messagebox.showerror(APP_NAME, "Could not find AppUpdater.bat.")
            return

        app_dir = updater.parent
        current_exe = Path(sys.executable).resolve()
        exe_candidates = []
        if getattr(sys, "frozen", False) and current_exe.exists():
            exe_candidates.append(current_exe)
        exe_candidates.extend([
            Path(r"F:\Auto Hotkey\Python\Apps\CodeHub.exe"),
            app_dir.parent / "Apps" / "CodeHub.exe",
            app_dir / "CodeHub.exe",
        ])
        exe_path = next((path for path in exe_candidates if path.exists()), exe_candidates[0])
        restart_dir = exe_path.parent
        cmd_path = app_dir / "CodeHub_local_update.cmd"
        current_pid = os.getpid()

        script = textwrap.dedent(f"""\
    @echo off
    setlocal EnableExtensions
    color 0A
    title CodeHub Local Updater
    cd /d "{app_dir}"
    set "CODEHUB_UPDATE_LOG={app_dir}\\CodeHub_update_log.txt"
    echo ================================================================>>"%CODEHUB_UPDATE_LOG%"
    echo CodeHub local update started %date% %time%>>"%CODEHUB_UPDATE_LOG%"

    echo [CodeHub] waiting for app to close...
    :WAIT_APP
    tasklist /FI "PID eq {current_pid}" | find "{current_pid}" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto WAIT_APP
    )

    echo [CodeHub] running local updater...
    call "{updater}" >>"%CODEHUB_UPDATE_LOG%" 2>&1
    if errorlevel 1 (
        echo [CodeHub] local update failed.
        echo [CodeHub] log: %CODEHUB_UPDATE_LOG%
        pause
        exit /b 1
    )

    echo [CodeHub] restarting CodeHub...
    if exist "{exe_path}" (
        echo [CodeHub] making sure desktop shortcut exists...
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $lnk=Join-Path $desktop 'CodeHub.lnk'; $shell=New-Object -ComObject WScript.Shell; $s=$shell.CreateShortcut($lnk); $s.TargetPath='{exe_path}'; $s.WorkingDirectory='{restart_dir}'; $s.IconLocation='{exe_path},0'; $s.Save()"
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '{exe_path}' -WorkingDirectory '{restart_dir}' -PassThru; Start-Sleep -Seconds 2; if ($p.HasExited) {{ Write-Host '[CodeHub] relaunched but immediately exited.' -ForegroundColor Red; exit 1 }} else {{ Write-Host '[CodeHub] relaunch verified.' -ForegroundColor Green }}"
        if errorlevel 1 (
            echo [CodeHub] relaunch failed.
            pause
            exit /b 1
        )
    ) else (
        echo [CodeHub] CodeHub.exe not found after update.
        pause
        exit /b 1
    )

    echo [CodeHub] updated and closing...
    timeout /t 1 /nobreak >nul
    exit /b 0
    """)

        cmd_path.write_text(script, encoding="utf-8")
        if os.name == "nt":
            try:
                subprocess.run(
                    ["attrib", "+h", str(cmd_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_process_flags(),
                )
            except Exception:
                pass

        if os.name == "nt":
            subprocess.Popen(
                ["cmd.exe", "/c", "call", str(cmd_path)],
                cwd=str(app_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(["sh", str(cmd_path)], cwd=str(app_dir))

        self.status.set("Local updater console opened. CodeHub will force-close in a moment...")
        self.root.after(700, self.force_close_for_update)

    def start_tutorial(self):
        self.tutorial_steps = [
            (0, "Recorder", "This is where you record macros. Pick a mode, press F1 to start, then F2 to stop and save."),
            (1, "Workspace", "This is your script editor. Open generated scripts, edit them, then press Save before running."),
            (2, "Tools", "These helper tools can build code, convert code, find click positions, and assist with edits."),
            (3, "Replay", "Load a recording here. Use Open Video for the smooth OpenCV replay, or screenshot frames as fallback."),
            (4, "Help", "The Help tab has this tutorial, the HTML guide, and support links."),
            (5, "Settings", "Settings controls themes, replay FPS, permissions, updates, and data paths. You can scroll this page now."),
        ]
        self.tutorial_index = 0
        self.show_tutorial_step()

    def _destroy_tutorial_windows(self):
        for attr in ("tutorial_panel", "tutorial_highlight"):
            win = getattr(self, attr, None)
            if win and win.winfo_exists():
                try:
                    win.destroy()
                except Exception:
                    pass
            setattr(self, attr, None)

    def show_tutorial_step(self):
        self._destroy_tutorial_windows()
        tab_index, title, body = self.tutorial_steps[self.tutorial_index]
        try:
            self.tabs.select(tab_index)
        except Exception:
            pass
        self.root.update_idletasks()

        # Highlight the real app area instead of covering the whole app.
        target = self.tabs
        try:
            x = target.winfo_rootx() + 6
            y = target.winfo_rooty() + 34
            w = max(320, target.winfo_width() - 12)
            h = max(220, target.winfo_height() - 40)
        except Exception:
            x = self.root.winfo_rootx() + 40
            y = self.root.winfo_rooty() + 90
            w = self.root.winfo_width() - 80
            h = self.root.winfo_height() - 140

        highlight = Toplevel(self.root)
        highlight.overrideredirect(True)
        highlight.attributes("-topmost", True)
        try:
            highlight.attributes("-transparentcolor", "#010101")
        except Exception:
            pass
        highlight.configure(bg="#010101")
        highlight.geometry(f"{w}x{h}+{x}+{y}")
        canvas = Canvas(highlight, bg="#010101", highlightthickness=0)
        canvas.pack(fill=BOTH, expand=True)
        canvas.create_rectangle(4, 4, w - 5, h - 5, outline=C["accent"], width=4)
        canvas.create_rectangle(10, 10, w - 11, h - 11, outline=C["yellow"], width=1)
        self.tutorial_highlight = highlight

        panel = Toplevel(self.root)
        panel.overrideredirect(True)
        panel.attributes("-topmost", True)
        panel.configure(bg=C["panel2"])
        if tab_index in (3, 4, 5):
            px = self.root.winfo_rootx() + self.root.winfo_width() - 545
            py = self.root.winfo_rooty() + self.root.winfo_height() - 205
        else:
            px = min(x + 28, self.root.winfo_rootx() + self.root.winfo_width() - 560)
            py = min(y + 28, self.root.winfo_rooty() + self.root.winfo_height() - 210)
        panel.geometry(f"520x178+{max(10, px)}+{max(10, py)}")
        box = Frame(panel, bg=C["panel2"], padx=18, pady=14, highlightbackground=C["accent"], highlightthickness=1)
        box.pack(fill=BOTH, expand=True)
        ttk.Label(box, text=f"Tutorial {self.tutorial_index + 1}/{len(self.tutorial_steps)}: {title}", style="SectionTitle2.TLabel").pack(anchor="w")
        ttk.Label(box, text=body, style="PanelMuted2.TLabel", wraplength=470, justify="left").pack(anchor="w", pady=(8, 12))
        row = Frame(box, bg=C["panel2"])
        row.pack(fill=X)
        ttk.Button(row, text="Skip", style="Ghost.TButton", command=self.cancel_tutorial).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(row, text="Next", style="Accent.TButton", command=self.next_tutorial_step).pack(side=RIGHT)
        self.tutorial_panel = panel
        self.status.set(f"Tutorial: {title}")

    def next_tutorial_step(self):
        self.tutorial_index += 1
        if self.tutorial_index >= len(self.tutorial_steps):
            self.cancel_tutorial()
            self.status.set("Tutorial complete")
            return
        self.show_tutorial_step()

    def cancel_tutorial(self):
        self._destroy_tutorial_windows()

    def open_help_html(self):
        path = DATA_DIR / "Index.html"
        html = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>CodeHub Guide</title>

<style>
body{
    background:#080808;
    color:#e8f0f8;
    font-family:Segoe UI,Arial,sans-serif;
    margin:0;
    line-height:1.7;
}

.wrap{
    max-width:1050px;
    margin:auto;
    padding:34px;
}

h1{
    color:#67ff8a;
    font-size:42px;
    margin-bottom:6px;
}

h2{
    color:#57a6ff;
    margin-bottom:8px;
}

p{
    color:#c9d7e6;
}

code{
    background:#151515;
    padding:2px 6px;
    border-radius:5px;
    color:#67ff8a;
}

.card{
    border:1px solid #2a2a2a;
    border-radius:12px;
    padding:22px;
    margin:18px 0;
    background:#101010;
}

.hero{
    border:1px solid #245c36;
    background:linear-gradient(135deg,#0d1810,#081018);
    padding:28px;
    border-radius:14px;
    margin-bottom:18px;
}

a{
    color:#30c8e8;
    text-decoration:none;
    font-weight:700;
}

a:hover{
    text-decoration:underline;
}

ul{
    margin-top:8px;
}

li{
    margin:8px 0;
    color:#d7e3ef;
}

.badge{
    display:inline-block;
    border:1px solid #2a2a2a;
    background:#151515;
    border-radius:999px;
    padding:5px 10px;
    margin:4px;
    color:#9ecbff;
    font-size:13px;
}

.social-button{
    display:inline-block;
    padding:13px 22px;
    border-radius:8px;
    color:white;
    text-decoration:none;
    margin:10px 10px 0 0;
    font-weight:bold;
    transition:.2s;
}

.social-button:hover{
    transform:translateY(-2px);
    text-decoration:none;
}

.discord{
    background:#5865F2;
}

.youtube{
    background:#FF0000;
}

.footer{
    text-align:center;
    color:#6f8ca8;
    margin-top:30px;
    font-size:14px;
}
</style>

</head>

<body>

<div class="wrap">

<div class="hero">

<h1>CodeHub</h1>

<p>
CodeHub is an all-in-one automation toolkit designed to simplify macro creation, script editing, replay analysis, and workflow automation. Whether you're creating simple keyboard macros or building larger automation projects, CodeHub provides everything in one organized interface.
</p>

<p>
<strong>Official Repository:</strong><br>
<a href="https://github.com/Catchallcat5382/CodeHub" target="_blank" rel="noopener noreferrer">
https://github.com/Catchallcat5382/CodeHub
</a>
</p>

<span class="badge">Macro Recorder</span>
<span class="badge">AutoHotkey v2</span>
<span class="badge">Python</span>
<span class="badge">Replay Viewer</span>
<span class="badge">Workspace</span>
<span class="badge">Automation</span>

</div>

<div class="card">

<h2>Recording Macros</h2>

<p>
The Recorder is the core of CodeHub. It captures your keyboard and mouse activity while preserving timing, allowing you to recreate actions exactly as they were performed.
</p>

<ul>
<li><b>F1</b> starts recording.</li>
<li><b>F2</b> stops recording and opens the save window.</li>
<li>Choose between AutoHotkey v2 or Python exports.</li>
<li>Every recording is automatically stored inside the Recordings Manager for future editing or exporting.</li>
</ul>

<p><b>Recording Modes</b></p>

<ul>
<li><b>Minimal</b> — Records only the essential actions for lightweight scripts.</li>
<li><b>Normal</b> — Captures standard keyboard, mouse clicks, scrolling, and timing.</li>
<li><b>Advanced</b> — Includes additional movement information for more accurate playback.</li>
</ul>

</div>

<div class="card">

<h2>Workspace</h2>

<p>
The Workspace acts as a built-in code editor specifically designed for macro development. Instead of switching between multiple programs, you can manage everything directly inside CodeHub.
</p>

<ul>
<li>Create new scripts.</li>
<li>Edit existing Python and AutoHotkey files.</li>
<li>Rename, delete, and organize projects.</li>
<li>Run scripts directly from the editor.</li>
<li>Use quick insert tools for commonly used code snippets.</li>
<li>Keep all exported files organized in your configured export folder.</li>
</ul>

</div>

<div class="card">

<h2>Tools</h2>

<p>
CodeHub includes several built-in utilities that make building and maintaining scripts much easier.
</p>

<ul>
<li><b>Assistant</b> — Reviews scripts, explains code, and stages edits before applying them.</li>

<li><b>Converter</b> — Converts between Python and AutoHotkey style code where possible.</li>

<li><b>Code Builder</b> — Visually create interface elements and generate matching code automatically.</li>

<li><b>Position Logger</b> — Records exact screen coordinates to make mouse automation much easier.</li>
</ul>

</div>

<div class="card">

<h2>Replay</h2>

<p>
The Replay page allows you to review recordings frame by frame before exporting or modifying them.
</p>

<ul>
<li>Inspect event timing.</li>
<li>Pause and resume playback.</li>
<li>Adjust playback speed.</li>
<li>Verify click locations.</li>
<li>Review captured screenshots (when enabled).</li>
</ul>

<p>
Replay is useful when fine-tuning a macro that almost works but needs small timing or positioning adjustments.
</p>

</div>

<div class="card">

<h2>Updates</h2>

<p>
CodeHub supports built-in update checking through the official GitHub repository. Updates are detected from the latest main-branch commit, while releases remain the public version labels. When a newer commit is available, CodeHub can download the main-branch CodeHub.exe and restart into the updated build without requiring a complete reinstall.
</p>

<p>
Official Repository:<br>
<a href="https://github.com/Catchallcat5382/CodeHub" target="_blank" rel="noopener noreferrer">
https://github.com/Catchallcat5382/CodeHub
</a>
</p>

</div>

<div class="card">

<h2>Support</h2>

<p>
If you encounter a bug, have an idea for a new feature, or need help using CodeHub, the easiest place to get assistance is through the official Discord community.
</p>

<p>
When reporting an issue, try to include:
</p>

<ul>
<li>Which feature or tab you were using.</li>
<li>What you expected to happen.</li>
<li>What actually happened.</li>
<li>Any error messages you received.</li>
<li>If possible, include screenshots or a short recording.</li>
</ul>

</div>

<div class="card">

<h2>Social Networks</h2>

<p>
Stay connected with the latest CodeHub updates, development progress, tutorials, announcements, and community discussions.
</p>

<a class="social-button discord" href="https://discord.gg/ZqC32Bn68P" target="_blank" rel="noopener noreferrer">
💬 Join the Official Discord
</a>

<a class="social-button youtube" href="https://www.youtube.com/@UselessGamz" target="_blank" rel="noopener noreferrer">
▶ Visit the YouTube Channel
</a>

<p style="margin-top:25px;">

<b>Discord Server</b><br>
Join the community to receive support, report bugs, suggest new features, chat with other users, and stay informed about upcoming updates.

</p>

<p>

<b>YouTube</b><br>
Watch tutorials, feature showcases, update videos, setup guides, development previews, and future CodeHub content.

</p>

</div>

<div class="footer">

CodeHub • Built by Catchallcat5382

</div>

</div>

</body>
</html>"""
        path.write_text(html, encoding="utf-8")
        webbrowser.open(path.as_uri())

    def open_discord_support(self):
        webbrowser.open("https://discord.gg/ZqC32Bn68P")

    def audio_device_names(self):
        names = ["Default"]
        self._audio_devices_cache = []
        try:
            import sounddevice as sd
            for idx, dev in enumerate(sd.query_devices()):
                if int(dev.get("max_input_channels", 0)) > 0:
                    label = f"{idx}: {dev.get('name', 'Audio Device')}"
                    names.append(label)
                    self._audio_devices_cache.append((label, idx))
        except Exception:
            pass
        return names

    def speaker_device_names(self):
        names = ["Default Speakers"]
        self._speaker_devices_cache = []
        try:
            import soundcard as sc
            seen = set()

            try:
                default_speaker = sc.default_speaker()
                default_name = str(getattr(default_speaker, "name", "Default Speakers"))
                default_loopback = sc.get_microphone(default_name, include_loopback=True)
                label = f"Default Speakers: {default_name}"
                names.append(label)
                self._speaker_devices_cache.append((label, default_loopback))
                seen.add(label.lower())
                seen.add(default_name.lower())
            except Exception:
                pass

            all_loopbacks = list(sc.all_microphones(include_loopback=True))
            filtered = []
            fallback = []
            for mic in all_loopbacks:
                label = str(getattr(mic, "name", "Loopback Audio"))
                lower = label.lower()
                if lower in seen:
                    continue
                fallback.append((label, mic))
                looks_like_output = any(term in lower for term in (
                    "loopback", "speaker", "speakers", "headphone", "headphones",
                    "output", "wasapi", "what u hear", "stereo mix", "monitor"
                ))
                looks_like_plain_mic = "microphone" in lower and not any(term in lower for term in ("loopback", "stereo mix", "what u hear"))
                if looks_like_output and not looks_like_plain_mic:
                    filtered.append((label, mic))
                    seen.add(lower)

            if not filtered:
                filtered = [(label, mic) for label, mic in fallback if label.lower() not in seen]

            for label, mic in filtered:
                if label.lower() in seen:
                    continue
                names.append(label)
                self._speaker_devices_cache.append((label, mic))
                seen.add(label.lower())
        except Exception:
            pass
        return names

    def mic_device_names(self):
        names = ["Default Mic"]
        self._mic_devices_cache = []
        try:
            import soundcard as sc
            for mic in sc.all_microphones(include_loopback=False):
                label = str(getattr(mic, "name", "Microphone"))
                names.append(label)
                self._mic_devices_cache.append((label, mic))
        except Exception:
            pass
        return names

    def resolve_soundcard_speaker(self, label):
        try:
            import soundcard as sc
            if not label or label == "Default Speakers":
                speaker = sc.default_speaker()
                return sc.get_microphone(str(getattr(speaker, "name", "")), include_loopback=True)
            for name, loopback in self._speaker_devices_cache or []:
                if name == label:
                    return loopback
            raw_label = str(label)
            if raw_label.startswith("Default Speakers:"):
                raw_label = raw_label.split(":", 1)[1].strip()
            try:
                return sc.get_microphone(raw_label, include_loopback=True)
            except Exception:
                pass
            for mic in sc.all_microphones(include_loopback=True):
                if str(getattr(mic, "name", "")) == str(label):
                    return mic
        except Exception:
            return None
        return None

    def resolve_soundcard_mic(self, label):
        try:
            import soundcard as sc
            if not label or label == "Default Mic":
                return sc.default_microphone()
            for name, mic in self._mic_devices_cache or []:
                if name == label:
                    return mic
            for mic in sc.all_microphones(include_loopback=False):
                if str(getattr(mic, "name", "")) == str(label):
                    return mic
        except Exception:
            return None
        return None

    def selected_audio_device_index(self):
        value = self.replay_audio_device.get()
        if value == "Default":
            return None
        for label, idx in self._audio_devices_cache:
            if label == value:
                return idx
        try:
            return int(str(value).split(":", 1)[0])
        except Exception:
            return None

    def selected_audio_device_label(self, device_index=None):
        try:
            import sounddevice as sd
            if device_index is None:
                default_input = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
                if default_input is None or int(default_input) < 0:
                    return "Default input"
                dev = sd.query_devices(int(default_input))
                return f"Default input: {dev.get('name', 'Audio Device')}"
            dev = sd.query_devices(int(device_index))
            return str(dev.get("name", "Audio Device"))
        except Exception:
            value = self.replay_audio_device.get()
            return value or "Default input"

    def is_headset_audio_device(self, label):
        text = str(label or "").lower()
        risky = ("headset", "hands-free", "hands free", "headphones", "bluetooth", "airpods", "earbuds", "microphone", "mic ")
        safe_loopback = ("stereo mix", "loopback", "virtual audio", "voicemeeter", "cable output", "monitor of")
        return any(word in text for word in risky) and not any(word in text for word in safe_loopback)

    def is_game_audio_device(self, label):
        text = str(label or "").lower()
        game_sources = ("stereo mix", "loopback", "virtual audio", "voicemeeter", "cable output", "monitor of", "what u hear")
        mic_sources = ("microphone", "mic ", "headset", "hands-free", "hands free", "airpods", "earbuds")
        return any(word in text for word in game_sources) and not any(word in text for word in mic_sources)

    def refresh_audio_devices(self):
        values = self.audio_device_names()
        if hasattr(self, "audio_device_combo"):
            self.audio_device_combo.configure(values=values)
        if self.replay_audio_device.get() not in values:
            self.replay_audio_device.set("Default")
        speaker_values = self.speaker_device_names()
        if hasattr(self, "speaker_device_combo"):
            self.speaker_device_combo.configure(values=speaker_values)
        if hasattr(self, "replay_speaker_device") and self.replay_speaker_device.get() not in speaker_values:
            self.replay_speaker_device.set("Default Speakers")
        mic_values = self.mic_device_names()
        if hasattr(self, "mic_device_combo"):
            self.mic_device_combo.configure(values=mic_values)
        if hasattr(self, "replay_mic_device") and self.replay_mic_device.get() not in mic_values:
            self.replay_mic_device.set("Default Mic")
        self.save_permissions()

    def toggle_data_paths(self):
        self.show_data_paths.set(not self.show_data_paths.get())
        self.settings["show_data_paths"] = self.show_data_paths.get()
        write_json(SETTINGS_PATH, self.settings)
        self.refresh_data_paths_info()

    def refresh_data_paths_info(self):
        if not hasattr(self, "data_paths_info"):
            return
        self.data_paths_info.configure(state="normal")
        self.data_paths_info.delete("1.0", END)
        if hasattr(self, "data_paths_toggle_btn"):
            self.data_paths_toggle_btn.configure(text="Hide Data Paths" if self.show_data_paths.get() else "Show Data Paths")
        if self.show_data_paths.get():
            self.data_paths_info.insert(END, f"Settings  : {SETTINGS_PATH}\n")
            self.data_paths_info.insert(END, f"Recordings: {RECORDINGS_PATH}\n")
            self.data_paths_info.insert(END, f"Knowledge : {KNOWLEDGE_PATH}\n")
            self.data_paths_info.insert(END, f"Exports   : {self.export_dir_var.get()}\n")
            self.data_paths_info.insert(END, f"Videos    : {DATA_DIR / 'review_videos'}\n")
            self.data_paths_info.insert(END, f"Screens   : {DATA_DIR / 'review_frames'}\n")
            self.data_paths_info.insert(END, f"Audio     : {DATA_DIR / 'review_audio'}\n\n")
        else:
            self.data_paths_info.insert(END, "Data paths are hidden. Click Show Data Paths to reveal them.\n")
            self.data_paths_info.insert(END, "Packaged CodeHub stores JSON/settings/replays in LocalAppData/CodeHub.\n")
            self.data_paths_info.insert(END, "Source mode stores data beside the source folder.\n\n")
        self.data_paths_info.insert(END, "Generated scripts include comments for hotkeys, editing, and watermark removal.\n")
        self.data_paths_info.insert(END, "All recordings persist as JSON; they survive app restarts.\n")
        self.data_paths_info.configure(state="disabled")


    def pick_theme_color(self, var):
        current = clamp_hex_color(var.get())
        color = colorchooser.askcolor(color=current, parent=self.root, title="Choose CodeHub color")
        if color and color[1]:
            var.set(clamp_hex_color(color[1]))
            self.theme_mode.set("custom")
            self.save_ui_settings()

    def refresh_basic_widget_colors(self, widget=None):
        widget = widget or self.root
        try:
            cls = widget.winfo_class()
            if cls in ("Frame", "TFrame", "Tk", "Toplevel"):
                widget.configure(bg=C["bg"])
            elif cls in ("Canvas",):
                widget.configure(bg=C["bg2"], highlightbackground=C["border"])
            elif cls in ("Text",):
                widget.configure(bg=C["bg2"], fg=C["text"], insertbackground=C["text"], highlightbackground=C["border"])
        except Exception:
            pass
        for child in widget.winfo_children():
            self.refresh_basic_widget_colors(child)

    def save_ui_settings(self):
        try:
            size = int(self.ui_font_size.get())
        except ValueError:
            size = 9
        self.settings["ui_font_size"] = max(8, min(12, size))
        self.settings["ui_density"] = self.ui_density.get()
        self.settings["theme_mode"] = self.theme_mode.get()
        self.settings["custom_bg"] = clamp_hex_color(self.custom_bg.get(), "#050505")
        self.settings["custom_panel"] = clamp_hex_color(self.custom_panel.get(), "#0B0B0B")
        self.settings["custom_text"] = clamp_hex_color(self.custom_text.get(), "#E8F0F8")
        self.settings["custom_accent"] = clamp_hex_color(self.custom_accent.get(), "#57A6FF")
        self.custom_bg.set(self.settings["custom_bg"])
        self.custom_panel.set(self.settings["custom_panel"])
        self.custom_text.set(self.settings["custom_text"])
        self.custom_accent.set(self.settings["custom_accent"])
        apply_theme_to_palette(self.settings)
        write_json(SETTINGS_PATH, self.settings)
        self.root.configure(bg=C["bg"])
        self._configure_styles()
        self.refresh_basic_widget_colors()
        self.status_bar.set_color(C["text3"])
        self.status.set("UI/theme settings saved")

    def toggle_fullscreen(self):
        self.fullscreen.set(not self.fullscreen.get())
        self.root.attributes("-fullscreen", self.fullscreen.get())

    def close(self):
        if self.current_editor_file and not Path(self.current_editor_file).exists():
            self.current_editor_file = None
            self.current_editor_saved_text = ""
            self.editor_dirty = False
        if hasattr(self, "editor") and self.editor_dirty and not self.confirm_unsaved_editor():
            return
        if self.is_recording:
            self.recorder.stop()
        self.stop_replay_video_capture()
        self.stop_position_logging()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.root.destroy()

    def force_close_for_update(self):
        try:
            self.editor_dirty = False
            self.is_recording = False
            try:
                self.recorder.stop()
            except Exception:
                pass
            try:
                self.stop_replay_video_capture()
            except Exception:
                pass
            try:
                self.stop_position_logging()
            except Exception:
                pass
            if hasattr(self, "hotkey_listener"):
                try:
                    self.hotkey_listener.stop()
                except Exception:
                    pass
            self.root.destroy()
        except Exception:
            try:
                os._exit(0)
            except Exception:
                pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    startup_console()
    CodeHubApp().run()







