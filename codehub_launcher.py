import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "CodeHub"

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent

RUNTIME_DIR = ROOT / ".codehub_runtime"
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "bootstrap_state.json"

GUI_SCRIPT = ROOT / "code_hub.py"
GUI_EXE = RUNTIME_DIR / "CodeHubApp.exe"
ICON_PATH = ROOT / "assets" / "CodeHub Logo.ico"
REQ_PATH = ROOT / "requirements.txt"


def line(text=""):
    print(text, flush=True)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    if os.name == "nt":
        os.system("color 0A")
    clear()
    print("=" * 72)
    print("              CODEHUB SYSTEM BOOTSTRAP SEQUENCE")
    print("=" * 72)
    print()


def read_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def file_hash(path):
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)
    return h.hexdigest()


def project_hash():
    h = hashlib.sha256()

    important_files = [GUI_SCRIPT, REQ_PATH, ICON_PATH]

    for py_file in ROOT.glob("*.py"):
        important_files.append(py_file)

    for path in sorted(set(important_files)):
        if path.exists() and path.is_file():
            h.update(str(path.relative_to(ROOT)).encode())
            h.update(file_hash(path).encode())

    return h.hexdigest()


def find_python():
    for cmd in (["py", "-3"], ["py"], [sys.executable], ["python"], ["python3"]):
        try:
            result = subprocess.run(
                cmd + ["--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return cmd
        except Exception:
            pass
    return None


def pip_install(python_cmd, args):
    return subprocess.run(
        python_cmd + ["-m", "pip", "install"] + args,
        cwd=str(ROOT)
    ).returncode == 0


def install_requirements_if_needed():
    python_cmd = find_python()
    if not python_cmd:
        line("[FAIL] Python not found, cannot install requirements.")
        return False

    line("[REQ ] upgrading pip...")
    subprocess.run(
        python_cmd + ["-m", "pip", "install", "--upgrade", "pip"],
        cwd=str(ROOT)
    )

    if not REQ_PATH.exists():
        line("[REQ ] requirements.txt not found, creating default one.")
        REQ_PATH.write_text(
            "\n".join([
                "pynput>=1.7.7",
                "mss>=9.0.1",
                "Pillow>=10.0.0",
                "pytesseract>=0.3.10",
                "opencv-python>=4.9.0.80",
                "numpy>=1.26.0",
                "pygame>=2.6.0",
                ""
            ]),
            encoding="utf-8"
        )

    required_text = REQ_PATH.read_text(encoding="utf-8", errors="ignore")
    must_have = {
        "opencv-python": "opencv-python>=4.9.0.80",
        "numpy": "numpy>=1.26.0",
        "mss": "mss>=9.0.1",
        "pillow": "Pillow>=10.0.0",
        "pynput": "pynput>=1.7.7",
        "pytesseract": "pytesseract>=0.3.10",
        "pygame": "pygame>=2.6.0",
    }

    changed = False
    lower = required_text.lower()
    lines_to_add = []

    for key, line_text in must_have.items():
        if key not in lower:
            lines_to_add.append(line_text)
            changed = True

    if changed:
        with open(REQ_PATH, "a", encoding="utf-8") as f:
            if not required_text.endswith("\n"):
                f.write("\n")
            for item in lines_to_add:
                f.write(item + "\n")
        line("[REQ ] requirements.txt updated with missing packages.")

    state = read_state()
    current = file_hash(REQ_PATH)

    line("[REQ ] installing/updating requirements...")
    ok = subprocess.run(
        python_cmd + ["-m", "pip", "install", "-r", str(REQ_PATH)],
        cwd=str(ROOT)
    ).returncode == 0

    if not ok:
        line("[FAIL] requirements install failed.")
        return False

    state["requirements_sha256"] = current
    write_state(state)
    line("[REQ ] requirements installed.")

    line("[REQ ] verifying imports...")

    check = subprocess.run(
        python_cmd + [
            "-c",
            (
                "import pygame;"
                "import cv2;"
                "import numpy;"
                "import mss;"
                "import PIL;"
                "import pynput;"
                "import pytesseract"
            )
        ],
        cwd=str(ROOT)
    )

    if check.returncode != 0:
        line("[FAIL] One or more required modules failed to import.")
        input("Press Enter to close...")
        return False

    line("[REQ ] import verification passed.")

    return True


def ensure_pyinstaller():
    python_cmd = find_python()
    if not python_cmd:
        return None

    check = subprocess.run(
        python_cmd + ["-m", "PyInstaller", "--version"],
        capture_output=True,
        text=True
    )

    if check.returncode == 0:
        return python_cmd

    line("[BUILD] PyInstaller missing. Installing...")
    ok = pip_install(python_cmd, ["pyinstaller"])

    if not ok:
        line("[FAIL] could not install PyInstaller.")
        return None

    return python_cmd


def close_old_gui():
    if os.name != "nt":
        return

    line("[PROC ] closing old CodeHubApp.exe if running...")
    subprocess.run(
        ["taskkill", "/f", "/im", "CodeHubApp.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(0.35)


def rebuild_gui():
    if not GUI_SCRIPT.exists():
        line("[FAIL] Missing code_hub.py in main folder.")
        return False

    python_cmd = ensure_pyinstaller()
    if not python_cmd:
        line("[FAIL] Python or PyInstaller not found.")
        return False

    close_old_gui()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    line("[BUILD] rebuilding CodeHubApp.exe...")

    cmd = [
        *python_cmd,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--clean",
        "--name",
        "CodeHubApp",
        "--distpath",
        str(RUNTIME_DIR),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT),

        "--hidden-import=cv2",
        "--hidden-import=numpy",
        "--hidden-import=mss",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=pynput",
        "--hidden-import=pytesseract",
        "--hidden-import=pygame",
        "--hidden-import=pygame.mixer",
    ]

    if ICON_PATH.exists():
        cmd.append(f"--icon={ICON_PATH}")

    assets_dir = ROOT / "assets"
    if assets_dir.exists():
        sep = ";" if os.name == "nt" else ":"
        cmd.append(f"--add-data={assets_dir}{sep}assets")

    cmd.append(str(GUI_SCRIPT))

    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        line("[FAIL] PyInstaller build failed.")
        return False

    line("[DONE] rebuild complete.")
    return True


def launch_gui():
    if not GUI_EXE.exists():
        line("[FAIL] GUI exe not found.")
        return False

    line("[BOOT] launching CodeHub GUI...")

    flags = 0
    if os.name == "nt":
        flags = (
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NEW_PROCESS_GROUP |
            subprocess.CREATE_NEW_CONSOLE
        )

    subprocess.Popen(
        [str(GUI_EXE)],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True
    )

    return True


def main():
    banner()

    line(f"[ROOT] {ROOT}")
    line(f"[GUI ] {GUI_EXE}")
    line()

    if not install_requirements_if_needed():
        line("[BOOT] requirements failed.")
        time.sleep(2)
        return

    state = read_state()
    current_hash = project_hash()
    old_hash = state.get("project_sha256")

    if not GUI_EXE.exists():
        line("[CHECK] no GUI exe found. Building now.")
        rebuilt = rebuild_gui()
    elif current_hash != old_hash:
        line("[CHECK] source or requirements changed. Updating exe.")
        rebuilt = rebuild_gui()
    else:
        line("[CHECK] no source changes detected.")
        rebuilt = True

    if rebuilt:
        state["project_sha256"] = current_hash
        state["requirements_sha256"] = file_hash(REQ_PATH)
        write_state(state)

        if launch_gui():
            line("[BOOT] closing bootstrap.")
            time.sleep(0.3)
            sys.exit(0)

    line("[BOOT] bootstrap failed or cancelled.")
    time.sleep(1.2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print()
        print("=" * 70)
        print("BOOTSTRAP CRASH")
        print("=" * 70)
        print(repr(e))
        print()
        input("Press Enter to close...")