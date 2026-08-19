"""pywebview dashboard window + JS↔Python bridge."""
import sys
from pathlib import Path

from config import settings
from core import state as core_state

WEB_DIR = Path(__file__).resolve().parent / "web"


class JsApi:
    """Methods callable from the page via pywebview.api.*"""

    def submit_command(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        core_state.push_chat("user", text)
        # Instant-stop fast path: don't queue, interrupt NOW.
        if core_state.is_stop_command(text):
            print("[ui] stop requested")
            core_state.request_stop()
            return
        core_state.command_queue.put(text)


def create_window():
    """Create (but don't start) the dashboard window. Returns the window."""
    import webview
    window = webview.create_window(
        "J.A.R.V.I.S",
        url=str(WEB_DIR / "index.html"),
        js_api=JsApi(),
        width=settings.UI_WIDTH,
        height=settings.UI_HEIGHT,
        background_color="#03060c",
        min_size=(720, 480),
    )
    core_state.attach_ui(window)
    return window


def run(on_ready) -> None:
    """Blocking: opens the window and calls on_ready(window) once loaded.
    Must be called from the main thread on Windows."""
    import webview
    window = create_window()

    def _started():
        try:
            on_ready(window)
        except Exception as e:
            print(f"[ui] on_ready failed: {e}", file=sys.stderr)

    webview.start(_started, debug=False)
