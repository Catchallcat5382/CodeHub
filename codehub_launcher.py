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
    os.system("cls")


def banner():
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

    important_files = [
        GUI_SCRIPT,
        REQ_PATH,
        ICON_PATH,
    ]

    for py_file in ROOT.glob("*.py"):
        important_files.append(py_file)

    for path in sorted(set(important_files)):
        if path.exists() and path.is_file():
            h.update(str(path.relative_to(ROOT)).encode())
            h.update(file_hash(path).encode())

    return h.hexdigest()


def find_python():
    for cmd in (["py", "-3"], ["py"], ["python"], ["python3"]):
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


def install_requirements_if_needed():
    if not REQ_PATH.exists():
        line("[REQ ] requirements.txt not found, skipping.")
        return

    python_cmd = find_python()
    if not python_cmd:
        line("[WARN] Python not found, cannot install requirements.")
        return

    state = read_state()
    current = file_hash(REQ_PATH)

    if state.get("requirements_sha256") == current:
        line("[REQ ] requirements unchanged.")
        return

    line("[REQ ] installing/updating requirements...")
    subprocess.run(
        python_cmd + ["-m", "pip", "install", "-r", str(REQ_PATH)],
        cwd=str(ROOT)
    )

    state["requirements_sha256"] = current
    write_state(state)


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
    subprocess.run(
        python_cmd + ["-m", "pip", "install", "pyinstaller"],
        cwd=str(ROOT)
    )

    return python_cmd


def close_old_gui():
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
        line("[FAIL] Python not found.")
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
        "--name",
        "CodeHubApp",
        "--distpath",
        str(RUNTIME_DIR),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT),
    ]

    if ICON_PATH.exists():
        cmd.append(f"--icon={ICON_PATH}")

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

    install_requirements_if_needed()

    state = read_state()
    current_hash = project_hash()
    old_hash = state.get("project_sha256")

    if not GUI_EXE.exists():
        line("[CHECK] no GUI exe found. Building now.")
        rebuilt = rebuild_gui()
    elif current_hash != old_hash:
        line("[CHECK] source changed. Updating exe.")
        rebuilt = rebuild_gui()
    else:
        line("[CHECK] no source changes detected.")
        rebuilt = True

    if rebuilt:
        state["project_sha256"] = current_hash
        write_state(state)

        if launch_gui():
            line("[BOOT] closing bootstrap.")
            time.sleep(0.3)
            os._exit(0)

    line("[BOOT] bootstrap failed or cancelled.")
    time.sleep(1.2)


if __name__ == "__main__":
    main()