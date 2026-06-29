import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path


APP_NAME = "CodeHub"
FAST_DELAY = 0.001


def app_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_root()
RUNTIME_DIR = ROOT / ".codehub_runtime"
TOOLS_DIR = ROOT / ".codehub_tools"
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "bootstrap_state.json"
REQ_PATH = ROOT / "requirements.txt"
GUI_EXE = RUNTIME_DIR / "CodeHubApp.exe"
GUI_SCRIPT = ROOT / "code_hub.py"


def redact(value):
    text = str(value)
    username = os.environ.get("USERNAME", "")
    userprofile = os.environ.get("USERPROFILE", "")
    computer = os.environ.get("COMPUTERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    for secret in (username, userprofile, computer, domain):
        if secret:
            text = text.replace(secret, "[REDACTED]")
            text = text.replace(secret.lower(), "[REDACTED]")
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED.IP]", text)
    text = re.sub(r"[\w.\-+]+@[\w.\-]+\.\w+", "[REDACTED.EMAIL]", text)
    return text


def clear():
    os.system("cls")


def line(text="", delay=FAST_DELAY):
    print(text, flush=True)
    if delay:
        time.sleep(delay)


def banner():
    if os.name == "nt":
        os.system("color 0A")
    clear()
    print("=" * 72)
    print("              CODEHUB SYSTEM BOOTSTRAP SEQUENCE")
    print("=" * 72)
    print()


def fmt_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024


def system_scan():
    line("[SYS  ] collecting host telemetry...")
    line(f"[SYS  ] OS={platform.platform()}")
    line(f"[SYS  ] NODE=[REDACTED] ARCH={platform.machine()} PY={platform.python_version()}")
    line(f"[PATH ] ROOT={redact(ROOT)}")
    checks = [
        ("BOOT EXE", ROOT / "CodeHub.exe"),
        ("GUI EXE", GUI_EXE),
        ("REQ", REQ_PATH),
        ("DATA", DATA_DIR),
        ("RUNTIME", RUNTIME_DIR),
        ("TOOLS", TOOLS_DIR),
    ]
    for label, path in checks:
        if path.exists():
            if path.is_file():
                line(f"[FILE ] {label:<8} OK {fmt_size(path.stat().st_size):>10} :: {path.name}", 0.01)
            else:
                count = sum(1 for _ in path.rglob("*")) if path.is_dir() else 0
                line(f"[DIR  ] {label:<8} OK objects={count:<5} :: {path.name}", 0.01)
        else:
            line(f"[MISS ] {label:<8} NOT FOUND :: {path}", 0.01)
    line()


def print_command(command_text):
    line(f"C:\\CodeHub> {command_text}", 0)


def emit_output(text, limit=34, delay=0):
    if not text:
        return
    lines = str(text).replace("\r", "").splitlines()
    for row in lines[:limit]:
        if row.strip():
            line(row[:138], delay)
    if len(lines) > limit:
        line(f"... [{len(lines) - limit} more lines buffered]", delay)


def run_display_command(command, timeout=4, limit=34):
    print_command(" ".join(command) if isinstance(command, list) else command)
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=isinstance(command, str),
            cwd=str(ROOT),
        )
        shown = 0
        started = time.time()
        while shown < limit:
            if proc.stdout is None:
                break
            if time.time() - started > timeout:
                break
            row = proc.stdout.readline()
            if not row:
                if proc.poll() is not None:
                    break
                time.sleep(0.01)
                continue
            row = row.strip()
            if row:
                line(row[:138], 0)
                shown += 1
        if proc.poll() is None:
            proc.kill()
            line("^C", 0)
            line("[TRACE] stream clipped; continuing boot", 0)
            return 124
        return proc.returncode or 0
    except Exception as exc:
        line(f"[WARN] command unavailable: {exc}", 0)
        return 1


def dir_scan():
    print_command("dir /s")
    if os.name == "nt":
        line(f" Volume in drive {ROOT.drive[:1] or 'C'} is BigDrive", 0)
        line(" Volume Serial Number is 00FC-97E0", 0)
    shown = 0
    for path in ROOT.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        kind = "<DIR>" if path.is_dir() else f"{stat.st_size:>14}"
        stamp = time.strftime("%m/%d/%Y  %I:%M %p", time.localtime(stat.st_mtime))
        line(redact(f"{stamp}    {kind}          {path.relative_to(ROOT)}"), 0)
        shown += 1
        if shown >= 135:
            break
    line(f"... [{shown}+ filesystem entries streamed / scan clipped]", 0)


def systeminfo_stream():
    print_command("systeminfo")
    rows = [
        ("Host Name", "[REDACTED]"),
        ("OS Name", platform.platform()),
        ("OS Version", platform.version()),
        ("OS Manufacturer", "Microsoft Corporation" if os.name == "nt" else platform.system()),
        ("OS Configuration", "Standalone Workstation"),
        ("System Type", platform.machine()),
        ("Python Runtime", platform.python_version()),
        ("Boot Root", redact(ROOT)),
        ("Runtime Package", redact(RUNTIME_DIR)),
        ("Command Shell", os.environ.get("COMSPEC", "cmd.exe")),
        ("User Domain", "[REDACTED]"),
        ("User Name", "[REDACTED]"),
        ("Processor", os.environ.get("PROCESSOR_IDENTIFIER", platform.processor() or "UNKNOWN")),
        ("Processor Cores", os.environ.get("NUMBER_OF_PROCESSORS", "UNKNOWN")),
        ("Temp Root", "[REDACTED]"),
        ("Path Gate", "verified"),
        ("Console Color", "0A"),
        ("Input Hooks", "standing by"),
        ("Macro Runtime", "armed"),
        ("Workspace Watcher", "online"),
        ("Replay Buffer", "online"),
        ("Permission Vault", "online"),
        ("Package Check", "pending"),
        ("Launch Mode", "bootstrap-to-gui"),
    ]
    for label, value in rows:
        line(f"{label + ':':<30} {value}", 0)
    for idx in range(1, 32):
        digest = hashlib.sha256(f"systeminfo:{idx}:{ROOT}".encode("utf-8")).hexdigest()
        line(f"Hotfix[{idx:03d}]                  KB{digest[:7].upper()}  channel={digest[7:15]}  state=Installed", 0)


def ping_trace():
    if os.name == "nt":
        print_command("ping -t google.com")
        for idx in range(1, 18):
            digest = hashlib.sha256(f"ping:{idx}:{time.time_ns()}".encode("utf-8")).hexdigest()
            latency = 8 + int(digest[:2], 16) % 42
            ttl = 113 + int(digest[2:4], 16) % 12
            line(f"Reply from [REDACTED.IP]: bytes=32 time={latency}ms TTL={ttl}", 0)
        line("^C", 0)
        line("[TRACE] stream clipped; continuing boot", 0)
    else:
        print_command("ping google.com")
        for idx in range(1, 18):
            line(f"64 bytes from [REDACTED.IP]: icmp_seq={idx} ttl=113 time={8 + idx}.2 ms", 0)
        line("^C", 0)


def terminal_flood():
    seeds = [
        "kernel.map", "input.hook", "macro.vm", "record.bus", "window.scan",
        "cache.json", "workspace.idx", "export.pipe", "ocr.frame", "replay.buf",
        "script.guard", "permission.vault", "theme.layer", "hotkey.router",
    ]
    verbs = [
        "index", "trace", "bind", "hash", "route", "mount", "verify", "sample",
        "mirror", "stage", "compress", "hydrate", "sync", "seal",
    ]
    for tick in range(1, 241):
        seed = seeds[tick % len(seeds)]
        verb = verbs[(tick * 3) % len(verbs)]
        digest = hashlib.sha256(f"{ROOT}:{tick}:{seed}".encode("utf-8")).hexdigest()
        line(
            f"[{tick:03d}] {verb.upper():<8} {seed:<18} bus=0x{digest[:8]} "
            f"sig={digest[8:24]} route={digest[24:32]} status=OK",
            0,
        )


def hash_sweep():
    line("[HASH] calculating runtime fingerprints...")
    targets = [
        ROOT / "CodeHub.exe",
        GUI_EXE,
        REQ_PATH,
        ROOT / "README.txt",
    ]
    for path in targets:
        digest = file_hash(path)
        if digest:
            line(f"[SHA256] {path.name:<22} {digest[:16]}...{digest[-12:]}", 0)
        else:
            line(f"[SHA256] {path.name:<22} MISSING", 0)
    line()


def hacker_boot_sequence():
    line("[BOOT] acquiring local shell context...")
    print_command("whoami")
    line("[REDACTED]\\[REDACTED]", 0)
    line()
    print_command("hostname")
    line("[REDACTED]", 0)
    line()
    if os.name == "nt":
        systeminfo_stream()
    else:
        run_display_command(["uname", "-a"], timeout=2, limit=8)
    line()
    terminal_flood()
    line()
    dir_scan()
    line()
    hash_sweep()
    ping_trace()
    line()
    line("[NET ] adapter telemetry cached")
    line("[HOOK] keyboard/mouse channels standing by")
    line("[AUTH] local package integrity gate open")
    line()


def read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def write_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def file_hash(path):
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 128), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_python():
    candidates = [
        ["py", "-3"],
        ["py"],
        ["python"],
        ["python3"],
    ]
    for command in candidates:
        try:
            check = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=8)
            if check.returncode == 0:
                return command
        except Exception:
            continue
    return None


def install_requirements_if_needed():
    state = read_state()
    current_hash = file_hash(REQ_PATH)
    previous_hash = state.get("requirements_sha256")
    if not REQ_PATH.exists():
        line("[REQ  ] requirements.txt not found, skipping package check.")
        return

    if current_hash and current_hash == previous_hash:
        line("[REQ  ] requirements already verified. No install needed.")
        line("[REQ  ] package manifest hash matches previous launch.")
        return

    line("[REQ  ] requirements changed or first launch detected.")
    python_cmd = find_python()
    if not python_cmd:
        line("[WARN ] Python was not found on PATH/py launcher.")
        line("[WARN ] Packaged CodeHub can still run, but external requirements were not installed.")
        state["requirements_sha256"] = current_hash
        write_state(state)
        return

    line(f"[PY   ] using {' '.join(python_cmd)}")
    line("[PIP  ] installing/updating requirements...")
    line("-" * 72, 0)
    result = subprocess.run(python_cmd + ["-m", "pip", "install", "-r", str(REQ_PATH)], cwd=str(ROOT))
    line("-" * 72, 0)
    if result.returncode != 0:
        line("[FAIL ] package install failed. CodeHub will still try to launch.")
        line("[TIP  ] check the pip output above if something is missing.")
    else:
        line("[DONE ] packages installed/verified successfully.")
        state["requirements_sha256"] = current_hash
        write_state(state)


def launch_gui():
    line()
    line("[BOOT ] launching CodeHub GUI...")
    if os.name == "nt":
        def start_windows(command):
            subprocess.Popen(
                ["cmd", "/c", "start", "", "/D", str(ROOT)] + command,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if GUI_EXE.exists():
            start_windows([str(GUI_EXE)])
            return True
        python_cmd = find_python()
        if python_cmd and GUI_SCRIPT.exists():
            start_windows(python_cmd + [str(GUI_SCRIPT)])
            return True
        line("[FAIL ] Could not find CodeHubApp.exe or code_hub.py.")
        return False

    if GUI_EXE.exists():
        subprocess.Popen(
            [str(GUI_EXE)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    python_cmd = find_python()
    if python_cmd and GUI_SCRIPT.exists():
        subprocess.Popen(
            python_cmd + [str(GUI_SCRIPT)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    line("[FAIL ] Could not find CodeHubApp.exe or code_hub.py.")
    return False


def main():
    banner()
    system_scan()
    hacker_boot_sequence()
    install_requirements_if_needed()
    line("[READY] bootstrap checks complete")
    ok = launch_gui()
    if ok:
        line("[BOOT ] GUI process started. Closing bootstrap console now...", 0)
        sys.exit(0)
    else:
        line()
        input("Press Enter to close...")


if __name__ == "__main__":
    main()
