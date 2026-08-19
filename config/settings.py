"""JARVIS global configuration — paths, model names, thresholds, hotkeys."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ── Project paths ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_LOG = PROJECT_ROOT / "build_log.txt"
SCREENSHOT_DIR = Path.home() / "Desktop"
TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# ── Voice / STT ───────────────────────────────────────────────
WAKE_WORDS = ("hey ultron", "hi ultron", "ultron", "hey jarvis", "hi jarvis", "jarvis")
WHISPER_MODEL = "base"          # faster-whisper model size
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"        # low-CPU quantized inference
STT_CONFIDENCE_THRESHOLD = 0.75
SAMPLE_RATE = 16000
WAKE_CHUNK_SECONDS = 2.0        # rolling window length for wake-word listening
COMMAND_RECORD_SECONDS = 6.0    # max seconds to record a command
SILENCE_THRESHOLD = 0.01        # RMS below this = silence
SILENCE_STOP_SECONDS = 1.2      # stop recording after this much trailing silence

# ── TTS ───────────────────────────────────────────────────────
TTS_RATE = 180                  # words per minute
TTS_VOLUME = 1.0
EDGE_TTS_VOICE = "en-US-GuyNeural"   # online fallback voice

# ── Brain / LLM ───────────────────────────────────────────────
OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TIMEOUT = 20             # seconds before falling back to regex parser
CONTEXT_WINDOW = 5              # remembered commands for pronoun resolution
NLP_TEMPERATURE = 0.1           # LLM temperature for intent extraction
NLP_MAX_TOKENS = 500            # max tokens for NLP extraction response

# ── Screen / OCR ───────────────────────────────────────────────
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_CONFIDENCE_MIN = 40         # tesseract word confidence floor
CLICK_MOVE_DURATION = 0.25      # seconds for mouse glide

# ── Browser ───────────────────────────────────────────────────
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BRAVE_EXE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
CHROME_PROFILE = "Default"      # user's main profile ("Akshat") for "open chrome"
BROWSER_PAGE_LOAD_TIMEOUT = 30

# ── Special launchers ─────────────────────────────────────────
# "open youtube" launches this Desktop PWA shortcut instead of a Selenium tab.
YOUTUBE_SHORTCUT = str(Path.home() / "Desktop" / "Akshat's YouTube.lnk")

# ── Spotify agent ─────────────────────────────────────────────
SPOTIFY_EXE = str(Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI",
                                      "http://127.0.0.1:8888/callback")

# ── Dashboard UI ───────────────────────────────────────────────
UI_WIDTH = 980
UI_HEIGHT = 640
UI_INFO_POLL_SECONDS = 60       # battery/weather/location refresh interval

# ── NLP Confidence Thresholds (Section 2.2 Step 6) ───────────────
LOW_CONFIDENCE_THRESHOLD = 0.6    # below this → ask for clarification
MEDIUM_CONFIDENCE_THRESHOLD = 0.6  # 60–85% → state interpretation before acting
HIGH_CONFIDENCE_THRESHOLD = 0.85   # above this → execute immediately

# ── System ───────────────────────────────────────────────────────
VOLUME_STEP = 10                # default % change for "increase volume"
BRIGHTNESS_STEP = 10

# ── NLP / Research paths ───────────────────────────────────────
RESEARCH_SAVE_DIR = Path.home() / "Documents"

# ── Voice: additional user-defined wake words (Section 7.2) ───────
# Populated at runtime via "From now on also respond to [phrase]".
CUSTOM_WAKE_WORDS = set()

# ── Safety ───────────────────────────────────────────────────────
# Actions that require a spoken confirmation before executing.
CONFIRM_ACTIONS = {"shutdown", "restart", "delete"}
# PyAutoGUI failsafe: slam mouse to top-left corner to abort.
PYAUTOGUI_FAILSAFE = True


os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# This machine has stale system env vars pointing at deleted cert files
# (old PostgreSQL install). They break pip/requests/webdriver-manager TLS.
for _var in ("CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "OPENSSL_CONF"):
    _val = os.environ.get(_var)
    if _val and not os.path.exists(_val):
        os.environ.pop(_var, None)

# Windows consoles default to cp1252 — web pages / OCR emit unicode.
import sys
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass