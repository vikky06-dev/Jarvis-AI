"""Task and reminder management (Section 5.4)."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import settings
from core.state import State
from voice.speaker import speak


_DONE_MARKER = "������✓"
_DATA_DIR = Path.home() / "Documents" / "JARVIS"
_TASKS_FILE = _DATA_DIR / "tasks.json"
_REMINDERS_FILE = _DATA_DIR / "reminders.json"
_DATA_DIR.mkdir(exist_ok=True)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return [] if path.suffix == ".json" else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if path.suffix == ".json" else {}


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Tasks (plain to-do list) ─────────────────────────────────

def add_task(description: str) -> str:
    """Append a task to the to-do list."""
    tasks = _load_json(_TASKS_FILE)
    tasks.append({"text": description, "done": False})
    _save_json(_TASKS_FILE, tasks)
    return f"Added task: {description}"


def list_tasks() -> str:
    """Read all pending tasks."""
    tasks = _load_json(_TASKS_FILE)
    if not tasks:
        return "Your to-do list is empty"
    lines = []
    for i, t in enumerate(tasks, 1):
        mark = _DONE_MARKER if t.get("done") else " "
        lines.append(f"{i}. [{mark}] {t['text']}")
    return "\n".join(lines)


def complete_task(description: str) -> str:
    """Mark a task as done by matching its text."""
    tasks = _load_json(_TASKS_FILE)
    for t in tasks:
        if t["text"].lower() == description.lower() and not t.get("done"):
            t["done"] = True
            _save_json(_TASKS_FILE, tasks)
            return f"Completed task: {description}"
    for t in tasks:
        if description.lower() in t["text"].lower() and not t.get("done"):
            t["done"] = True
            _save_json(_TASKS_FILE, tasks)
            return f"Completed task: {t['text']}"
    return f"Couldn't find task: {description}"


def remove_task(description: str) -> str:
    """Remove a task by matching its text."""
    tasks = _load_json(_TASKS_FILE)
    for i, t in enumerate(tasks):
        if t["text"].lower() == description.lower():
            removed = tasks.pop(i)
            _save_json(_TASKS_FILE, tasks)
            return f"Removed task: {removed['text']}"
    return f"Couldn't find task to remove: {description}"


def clear_tasks() -> str:
    """Delete all tasks."""
    _save_json(_TASKS_FILE, [])
    return "Cleared all tasks"


# ── Reminders (time-based) ───────────────────────────────────

def add_reminder(when: str, description: str) -> str:
    """Parse a natural-language time and store a reminder."""
    when_lower = when.lower().strip()
    from datetime import datetime, timedelta
    now = datetime.now()

    # Relative: "in 10 minutes", "after 1 hour"
    m = re.search(r"(?:in|after) (\d+)\s*(minute|min|second|sec|hour|hr)s?", when_lower)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)
        unit_map = {"minute": 60, "min": 60, "second": 1, "sec": 1, "hour": 3600, "hr": 3600}
        delta = timedelta(seconds=qty * unit_map.get(unit, 60))
        remind_time = now + delta
    # Absolute times: "at 3:30 PM", "at 15:00"
    else:
        try:
            # Try parsing with strptime first
            for fmt in ("%I:%M %p", "%H:%M"):
                try:
                    remind_time = datetime.strptime(when, fmt)
                    break
                except ValueError:
                    continue
            else:
                # Try parsing just the hour
                hour = int(when_lower.replace("am", "").replace("pm", "").strip())
                if "pm" in when_lower and hour < 12:
                    hour += 12
                remind_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        except Exception:
            return f"Sorry, I didn't understand the time: {when}"

    # If the time has already passed today, schedule for tomorrow
    if remind_time <= now:
        remind_time += timedelta(days=1)

    reminders = _load_json(_REMINDERS_FILE)
    reminders.append({"when": remind_time.isoformat(), "text": description})
    _save_json(_REMINDERS_FILE, reminders)

    # Format the time nicely for the response
    time_str = remind_time.strftime("%I:%M %p").lstrip("0")
    return f"Okay, I'll remind you to {description} at {time_str}"


def list_reminders() -> str:
    """Show all pending reminders."""
    reminders = _load_json(_REMINDERS_FILE)
    if not reminders:
        return "You have no reminders set"
    from datetime import datetime
    now = datetime.now()
    lines = []
    for r in reminders:
        r_time = datetime.fromisoformat(r["when"])
        if r_time > now:
            time_str = r_time.strftime("%I:%M %p").lstrip("0")
            lines.append(f"• {time_str} — {r['text']}")
    if not lines:
        return "You have no reminders set"
    return "\n".join(lines)


def remove_reminder(description: str) -> str:
    """Remove a reminder by matching its text."""
    reminders = _load_json(_REMINDERS_FILE)
    for i, r in enumerate(reminders):
        if r["text"].lower() == description.lower():
            removed = reminders.pop(i)
            _save_json(_REMINDERS_FILE, reminders)
            return f"Removed reminder: {removed['text']}"
    return f"Couldn't find reminder to remove: {description}"


def clear_reminders() -> str:
    """Delete all reminders."""
    _save_json(_REMINDERS_FILE, [])
    return "Cleared all reminders"


# ── Background checker (called from main worker loop) ──────────

def _check_reminders() -> Optional[str]:
    """Return a reminder message if one is due, else None."""
    reminders = _load_json(_REMINDERS_FILE)
    if not reminders:
        return None
    from datetime import datetime, timedelta
    now = datetime.now()
    due = []
    remaining = []
    for r in reminders:
        r_time = datetime.fromisoformat(r["when"])
        if r_time <= now + timedelta(seconds=30):  # within 30 seconds
            due.append(r)
        else:
            remaining.append(r)
    if due:
        _save_json(_REMINDERS_FILE, remaining)
        messages = [f"Reminder: {r['text']}" for r in due]
        return "\n".join(messages)
    return None


def _run_reminder_checker() -> None:
    """Background thread: polls for reminders and speaks them due."""
    while True:
        try:
            msg = _check_reminders()
            if msg:
                speak(msg)
        except Exception:
            pass
        # Check every 30 seconds
        import time
        time.sleep(30)


def start_reminder_checker() -> None:
    """Launch the background reminder checker thread."""
    threading.Thread(target=_run_reminder_checker, daemon=True).start()


# ── Notepad access (Section 5.4) ─────────────────────────────

_NOTEPAD_PATH = Path.home() / "Desktop" / "JARVIS Notepad.txt"
_NOTEPAD_PATH.touch(exist_ok=True)


def open_notepad() -> str:
    """Open the notepad file in the default editor."""
    os.startfile(_NOTEPAD_PATH)
    return "Opening notepad"


def save_notepad(content: str) -> str:
    """Overwrite the notepad file with given content."""
    _NOTEPAD_PATH.write_text(content, encoding="utf-8")
    return "Saved notepad"


def append_notepad(content: str) -> str:
    """Append content to the notepad file."""
    with _NOTEPAD_PATH.open("a", encoding="utf-8") as f:
        f.write(content)
        if not content.endswith("\n"):
            f.write("\n")
    return "Appended to notepad"


def read_notepad() -> str:
    """Read the current notepad content."""
    try:
        return _NOTEPAD_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def clear_notepad() -> str:
    """Clear the notepad file."""
    _NOTEPAD_PATH.write_text("", encoding="utf-8")
    return "Cleared notepad"


def take_dictation() -> str:
    """Listen for speech and append it to notepad with basic formatting."""
    from voice.listener = listen_for_command
    speak("Listening for dictation. Say 'stop dictation' to finish.")
    lines = []
    while True:
        try:
            command, conf = listen_for_command()
            if not command:
                continue
            if command.lower() in ("stop dictation", "stop taking notes"):
                break
            if conf < settings.STT_CONFIDENCE_THRESHOLD:
                continue
            # Basic formatting: capitalize first letter, add period if missing
            sentence = command.strip()
            if sentence:
                sentence = sentence[0].upper() + sentence[1:]
                if sentence and sentence[-1] not in ".!?":
                    sentence += "."
            lines.append(sentence)
        except Exception:
            break
    if lines:
        content = " ".join(lines)
        return append_notepad(content)
    return "No dictation captured"


# Export for dispatcher
__all__ = [
    "add_task", "list_tasks", "complete_task", "remove_task", "clear_tasks",
    "add_reminder", "list_reminders", "remove_reminder", "clear_reminders",
    "open_notepad", "save_notepad", "append_notepad", "read_notepad",
    "clear_notepad", "take_dictation",
    "_run_reminder_checker", "start_reminder_checker",
]