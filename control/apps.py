"""App control: open/close/switch apps by (partial) name.

Discovery order for "open X":
  1. Known-alias table (fast path for common apps)
  2. Start-menu .lnk scan (covers most installed GUI apps)
  3. Windows Registry App Paths
  4. `start` shell fallback (URI handlers, PATH executables)
"""
import os
import subprocess
import sys
from pathlib import Path

import psutil

ALIASES = {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "edge": "msedge.exe",
    "spotify": "spotify.exe",
    "settings": "ms-settings:",
}

START_MENU_DIRS = [
    Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
    Path.home() / "Desktop",
    Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
]


def _find_start_menu_shortcut(name: str) -> Path | None:
    name = name.lower()
    best = None
    for root in START_MENU_DIRS:
        if not root.exists():
            continue
        for lnk in root.rglob("*.lnk"):
            stem = lnk.stem.lower()
            if stem == name:
                return lnk
            if name in stem and (best is None or len(stem) < len(best.stem)):
                best = lnk
    return best


def _find_registry_app(name: str) -> str | None:
    import winreg
    exe = name if name.endswith(".exe") else name + ".exe"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}")
            path, _ = winreg.QueryValueEx(key, None)
            winreg.CloseKey(key)
            if path and Path(path.strip('"')).exists():
                return path.strip('"')
        except OSError:
            continue
    return None


def open_app(name: str) -> str:
    """Open an app by (partial) name. Returns a spoken-status string."""
    name = name.lower().strip()
    target = ALIASES.get(name, name)

    if target.endswith(":"):  # URI like ms-settings:
        os.startfile(target)
        return f"Opening {name}"

    # Registry App Paths (works for chrome.exe, winword.exe, etc.)
    reg = _find_registry_app(target)
    if reg:
        subprocess.Popen([reg])
        return f"Opening {name}"

    # Direct executable on PATH
    try:
        subprocess.Popen(target if target.endswith(".exe") else target,
                         shell=not target.endswith(".exe"))
        return f"Opening {name}"
    except (OSError, subprocess.SubprocessError):
        pass

    # Start-menu shortcut fuzzy match
    lnk = _find_start_menu_shortcut(name)
    if lnk:
        os.startfile(str(lnk))
        return f"Opening {lnk.stem}"

    # Last resort: shell `start`
    try:
        subprocess.run(f'start "" "{name}"', shell=True, check=True, timeout=10)
        return f"Opening {name}"
    except Exception:
        return f"I couldn't find an app called {name}"


def close_app(name: str) -> str:
    """Kill all processes whose name matches (partial, case-insensitive)."""
    name = name.lower().strip().removesuffix(".exe")
    alias = ALIASES.get(name, "")
    needles = {name.replace(" ", ""), alias.removesuffix(".exe")}
    needles.discard("")
    killed = set()
    for proc in psutil.process_iter(["name"]):
        pname = (proc.info["name"] or "").lower().removesuffix(".exe")
        if any(n in pname for n in needles):
            try:
                proc.terminate()
                killed.add(pname)
            except psutil.Error:
                pass
    if killed:
        psutil.wait_procs([p for p in psutil.process_iter() if False], timeout=0)
        return f"Closed {name}"
    return f"{name} doesn't seem to be running"


def close_all_windows() -> str:
    """Close all open application windows (Section 3.2: 'close everything')."""
    import pygetwindow as gw
    closed = 0
    for win in gw.getAllWindows():
        try:
            if win.title and win.isVisible:
                win.close()
                closed += 1
        except Exception:
            continue
    if closed:
        return f"Closed {closed} windows"
    return "No open windows to close"


def switch_window() -> str:
    import pyautogui
    pyautogui.hotkey("alt", "tab")
    return "Switched window"


def _find_window(title: str | None):
    import pygetwindow as gw
    if not title:
        win = gw.getActiveWindow()
        return win
    matches = [w for w in gw.getAllWindows() if title.lower() in w.title.lower() and w.title]
    return matches[0] if matches else None


def minimize_window(title: str | None = None) -> str:
    win = _find_window(title)
    if win:
        win.minimize()
        return "Minimized"
    return "No matching window found"


def maximize_window(title: str | None = None) -> str:
    win = _find_window(title)
    if win:
        win.maximize()
        return "Maximized"
    return "No matching window found"


if __name__ == "__main__":
    import time
    print(open_app("notepad"))
    time.sleep(2)
    print(close_app("notepad"))
