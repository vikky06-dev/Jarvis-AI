"""Shared runtime state for all JARVIS threads.

- stop_event: set the instant the user says/types "stop" — every long-running
  operation (TTS chunks, compound steps, Spotify waits) checks it and bails.
- command_queue: commands flow in from BOTH the voice thread and the UI box;
  one worker thread drains it so execution stays serialized.
- ui: late-bound handle to the dashboard window; push helpers are safe no-ops
  when running headless (--text / --once).
"""
import queue
import threading
from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


stop_event = threading.Event()
command_queue: "queue.Queue[str]" = queue.Queue()

_ui_window = None          # pywebview window, set by dashboard.ui
_state = State.IDLE

# Words that trigger the instant-stop fast path (checked before queueing).
STOP_WORDS = {"stop", "stop it", "cancel", "wait", "shut up", "be quiet", "quiet"}


def is_stop_command(text: str) -> bool:
    return text.lower().strip(" ,.!?") in STOP_WORDS


def attach_ui(window) -> None:
    global _ui_window
    _ui_window = window


def _js(code: str) -> None:
    """Run JS in the dashboard; silently skip when headless or window closed."""
    if _ui_window is None:
        return
    try:
        _ui_window.evaluate_js(code)
    except Exception:
        pass


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("'", "\\'")
                .replace("\n", "\\n").replace("\r", ""))


def set_state(state: State) -> None:
    global _state
    _state = state
    _js(f"setOrbState('{state.value}')")


def get_state() -> State:
    return _state


def push_level(rms: float) -> None:
    """Feed a mic RMS sample to the orb (0..~0.3 typical)."""
    _js(f"setOrbLevel({min(1.0, rms * 8):.3f})")


def push_chat(role: str, text: str) -> None:
    """Append a line to the dashboard transcript. role: 'user' | 'jarvis'."""
    _js(f"addChat('{role}', '{_esc(text)}')")


def push_info(info: dict) -> None:
    """Update the top info bar (battery/weather/location)."""
    import json
    _js(f"setInfo({json.dumps(info)})")


def request_stop() -> None:
    """Interrupt whatever JARVIS is doing right now."""
    stop_event.set()
    set_state(State.IDLE)
