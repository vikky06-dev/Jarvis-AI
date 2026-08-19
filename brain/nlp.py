"""ULTRON AI — NLP & Natural Language Understanding Pipeline.

Implements the full 7-step extraction process from the NLP module specification:
  1. Transcription normalization (filler words, false starts, spoken punctuation)
  2. Language detection
  3. Intent classification
  4. Entity extraction
  5. Context injection
  6. Confidence scoring
  7. Execution dispatch metadata

Returns the structured JSON described in Section 9.3 for every user input.
"""
import json
import re
import sys

from config import settings
from .memory import memory

# ── Intent Categories (Section 2.1) ─────────────────────────────────

INTENT_CATEGORIES = [
    "SYSTEM_CONTROL", "APPLICATION_CONTROL", "FILE_OPERATION", "MEDIA_CONTROL",
    "COMMUNICATION", "WEB_ACTION", "RESEARCH", "CONTENT_CREATION",
    "SCREEN_ACTION", "TASK_MANAGEMENT", "CONVERSATIONAL", "AMBIGUOUS",
]

# ── Stop-word / filler lexicons (Section 7.1) ──────────────────────

FILLER_WORDS = {
    "um", "uh", "like", "you know", "kind of", "sort of", "basically",
    "so", "right", "well", "hmm", "ah", "oh",
    "i mean", "literally", "seriously", "please", "pls", "plz",
}

# Spoken punctuation tokens (Section 7.1)
_SPOKEN_PUNCT = {
    "comma": ",", "period": ".", "full stop": ".", "dot": ".",
    "question mark": "?", "exclamation mark": "!", "exclamation point": "!",
    "colon": ":", "semicolon": ";", "dash": "-",
    "open paren": "(", "close paren": ")",
    "open bracket": "[", "close bracket": "]",
    "quote": '"', "quotation mark": '"',
}

# Casual / slang intent patterns (Section 3.2)
SLANG_PATTERNS = [
    (r"\b(blast|put) (?:on |some )?(.+)", "media_play"),
    (r"\b(kill|cancel) (?:the )?volume\b", "volume_mute"),
    (r"\b(crank|turn|make) (?:it|the )?up\b", "volume_up"),
    (r"\b(dim|turn down) (?:this|the )?thing\b", "brightness_down"),
    (r"\b(pull up|open|get going)\b", "open_app"),
    (r"\b(fire up)\b", "open_app"),
    (r"\b(screenshot|takes? ?a? ?screen)\b", "screenshot"),
    (r"\b(smash) (.+)", "web_click"),
    (r"\b(flip|turn|switch) (?:the )?wifi off\b", "wifi_off"),
    (r"\b(flip|turn|switch) (?:the )?wifi on\b", "wifi_on"),
    (r"\b(chuck|drop|throw) (?:that|this|the)? ?file (?:in|into|to) (.+)", "move_file"),
    (r"\bclose (?:everything|all (?:apps?|windows?))\b", "close_all_windows"),
    (r"\b(lock|freeze) (?:the )?screen\b", "lock_screen"),
]

# ── Implicit commands (Section 3.3) ─────────────────────────────────

IMPLICIT_PATTERNS = [
    (r"\bi(?: ?'?m| am) cold\b", None, "I'm cold — not directly actionable for the system."),
    (r"\btoo bright\b", "brightness_down", "Brightness may be too high; offering to reduce it."),
    (r"\bi need to write\b", "content_create_notepad", "Opening Notepad for dictation."),
    (r"\bi can'?t hear\b", "volume_up", "Raising the volume."),
    (r"\bi want to remember\b", "screenshot_or_note", "Capturing what's on screen or adding to notes."),
    (r"\bwho (?:made|is) (?:this )?song\b", "identify_song", "Looking up the current song."),
    (r"\bwhere was i\b", "resume_task", "Resuming your last task."),
    (r"\bwon'?t load\b", "refresh_page", "Refreshing the page and checking the connection."),
    (r"\b(?:page|site|website).{0,25}won'?t load\b", "refresh_page", "Refreshing the page and checking the connection."),
    (r"\bwho (?:made|sang|performed) this song\b", "identify_song", "Looking up the current song."),
]

# ── Self-correction indicators (Section 5.3) ────────────────────────

CORRECTION_INDICATORS = [
    "actually", "no wait", "no,", "i meant", "change the last",
    "i meant to say", "sorry", "oops", "never mind", "instead",
    "correct that", "redo", "try again", "make that",
]

# ── Conditional trigger words (Section 3.5) ─────────────────────────

CONDITIONAL_TRIGGERS = [
    r"\bif\b", r"\bunless\b", r"\bwhen\b", r"\bafter\b", r"\bbefore\b",
    r"\bonly\b", r"\bwhenever\b", r"\bas soon as\b",
]

# ── Confirmation gating (Section 3.5) ───────────────────────────────
# "Send the message only after I confirm" → hold the action for confirmation.
CONFIRM_GATE_PATTERNS = [
    r"\bonly after (?:i|we|my) confirm",
    r"\bwait for (?:my|the) confirm",
    r"\bdon'?t (?:send|do|execute|run|close|shut) until",
    r"\bhold (?:it|that) until",
    r"\buntil (?:i|we) (?:say|give|confirm|approve)",
    r"\bonly with (?:my|your) (?:confirm|approval)\b",
]


def detect_confirmation_gate(command: str) -> bool:
    """Detect if the command requires user confirmation before executing."""
    cmd_lower = command.lower()
    return any(re.search(p, cmd_lower) for p in CONFIRM_GATE_PATTERNS)


# ── "Unless I say otherwise" preference (Section 3.5) ───────────────
_HOLD_PREFERENCE_RE = re.compile(
    r"\bkeep (?:the )?([a-z ]+?) at (\d+)(?:%| percent)? (?:unless|until|till) i say otherwise\b",
    re.IGNORECASE,
)


def detect_hold_preference(command: str) -> dict | None:
    """Detect 'keep the volume at 50 unless I say otherwise' → preference."""
    m = _HOLD_PREFERENCE_RE.search(command)
    if m:
        key = m.group(1).strip().lower()
        # Map common hold targets to preference keys
        key_map = {
            "volume": "default_volume",
            "brightness": "default_brightness",
            "spotify volume": "spotify_default_volume",
        }
        pref_key = key_map.get(key, f"hold_{key}".replace(" ", "_"))
        return {"key": pref_key, "value": m.group(2)}
    return None


# ── Custom wake word instruction (Section 7.2) ──────────────────────
_WAKE_WORD_RE = re.compile(
    r"\b(?:from now on )?(?:also )?(?:respond|answer|react) to (?:the wake word )?"
    r"(?:'([a-z0-9]+)'|\"([a-z0-9]+)\"|([a-z0-9]+))\b",
    re.IGNORECASE,
)


def detect_wake_word_instruction(command: str) -> str | None:
    """Detect 'from now on also respond to [custom wake word]'."""
    m = _WAKE_WORD_RE.search(command)
    if m:
        word = next((g for g in m.groups() if g), None)
        if word and word.lower() not in ("me", "that", "this", "voice", "commands"):
            return word.strip().lower()
    return None


# ── Dictation mode (Section 7.1) ────────────────────────────────────
DICTATION_START_RE = re.compile(
    r"\b(write this down|start dictation|dictate|write down)\b", re.IGNORECASE)
DICTATION_STOP_RE = re.compile(
    r"\b(okay? stop|stop (?:dictating|writing)|that'?s it|now save(?: the file)?|save the file)\b",
    re.IGNORECASE)

# ── Language detection ──────────────────────────────────────────────

def detect_language(text: str) -> str:
    """Detect the language of the input text.

    Uses langdetect if available; falls back to a lightweight heuristic.
    Returns a language name string (e.g., "Hindi", "English", "Hinglish").
    """
    text = text.strip()
    if not text:
        return "English"

    has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
    hinglish_words = {
        "kya", "hai", "kyun", "kaise", "kaunsa", "kitna",
        "thoda", "bahut", "achha", "theek", "mast", "cool", "bas",
        "karo", "karein", "karenge", "hoon",
        "mera", "tera", "uska", "unka", "yeh", "voh",
        "band kar", "volume kam", "brightness badha",
        "yaar", "bhai", "kar", "daal", "rok", "bhej", "likh",
        "band", "khol", "chalu", "aur", "pe", "mein", "ko", "ka",
        "karke", "de", "do", "ho", "nahi", "haan", "baat", "waqt",
    }
    latin_lower = text.lower()
    if has_devanagari:
        return "Hinglish"
    hinglish_count = sum(1 for w in hinglish_words if re.search(r'\b' + re.escape(w), latin_lower))
    if hinglish_count >= 1:
        return "Hinglish"

    # Short English text is often misclassified by langdetect (e.g. "Open Spotify" → 'no').
    # If the text is short and uses only Latin characters with common English words,
    # default to English rather than trusting langdetect on tiny inputs.
    _ENGLISH_HINTS = {
        "the", "and", "open", "play", "pause", "stop", "close", "send", "search",
        "volume", "brightness", "screenshot", "spotify", "youtube", "chrome",
        "what", "who", "how", "where", "when", "please", "can", "you", "me",
        "music", "song", "video", "file", "folder", "task", "wifi", "screen",
    }
    latin_words = re.findall(r"[a-zA-Z']+", text.lower())
    if latin_words and len(latin_words) <= 8:
        english_hits = sum(1 for w in latin_words if w in _ENGLISH_HINTS)
        if english_hits >= 1 or len(latin_words) <= 3:
            return "English"

    try:
        from langdetect import detect
        code = detect(text)
        _MAP = {"en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
                "de": "German", "zh-cn": "Chinese", "ja": "Japanese",
                "ru": "Russian", "ar": "Arabic", "pt": "Portuguese"}
        return _MAP.get(code, code)
    except Exception:
        pass

    if has_devanagari:
        return "Hindi"
    return "English"


# ── Text normalization (Section 7.1, Section 2.2 Step 1) ──────────

def normalize_transcription(text: str) -> str:
    """Normalize voice-to-text output:

    - Remove filler words
    - Resolve false starts
    - Convert spoken punctuation to actual punctuation
    - Standardize spacing
    """
    if not text:
        return ""

    # Convert spoken punctuation first (before filler removal)
    for spoken, punct in sorted(_SPOKEN_PUNCT.items(), key=lambda x: -len(x[0])):
        text = re.sub(r'\b' + re.escape(spoken) + r'\b', punct, text, flags=re.IGNORECASE)

    # Remove filler words — only standalone words, not substrings
    words = text.split()
    cleaned = []
    for word in words:
        w = word.lower().strip(".,!?;:'\"()[]{}")
        if w in FILLER_WORDS:
            continue
        cleaned.append(word)

    text = " ".join(cleaned)
    text = re.sub(r'\s+', ' ', text).strip()

    # False-start resolution: split on fillers that start a correction
    for sep in ["no wait", "actually", "i mean", "never mind", "oops", "sorry"]:
        pattern = re.split(re.escape(sep), text, maxsplit=1, flags=re.IGNORECASE)
        if len(pattern) > 1 and pattern[1].strip():
            text = pattern[1].strip()

    return text


# ── Translation (Section 8) ─────────────────────────────────────────

def translate_text(text: str, target: str = "en") -> str:
    """Translate text to English (or the target language).

    Uses deep-translator if available; otherwise returns the text unchanged.
    """
    if not text:
        return text
    detected = detect_language(text)
    if detected == "English" and target == "en":
        return text
    if detected == target and target != "Hinglish":
        return text
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target=target)
        return translator.translate(text)
    except Exception:
        return text


# ── Compound & chained command splitting (Section 3.4) ─────────────

_COMPOUND_SPLIT_RE = re.compile(
    r'(?:\s+(?:and then|then|after that|next|;| and )\s+|\s*,\s*|\s*;\s*)',
    re.IGNORECASE
)


def split_compound(command: str) -> list[str]:
    """Split a compound/chained command into sequential steps.

    Handles: "A and then B", "A, then B", "A; B", "First X, then Y",
    "A and B" (when both are action phrases).
    """
    parts = _COMPOUND_SPLIT_RE.split(command.strip())
    parts = [re.sub(r'^(?:first|step 1|step one)\s+', '', p, flags=re.IGNORECASE).strip() for p in parts]
    parts = [re.sub(r'^next\s+', '', p, flags=re.IGNORECASE).strip() for p in parts]
    parts = [re.sub(r'^(?:finally|lastly)\s+', '', p, flags=re.IGNORECASE).strip() for p in parts]
    return [p for p in parts if p]


# ── Conditional command detection (Section 3.5) ────────────────────

def detect_conditional(command: str) -> dict | None:
    """Detect conditional logic embedded in natural language."""
    cmd_lower = command.lower()

    delay_match = re.search(r'\b(?:in|after) (\d+)\s*(?:minute|min|second|sec|hour|hr)\b', cmd_lower)
    if delay_match:
        return {
            "condition": f"delayed by {delay_match.group(1)} {delay_match.group(0)}",
            "action": command,
            "fallback": None,
        }

    if re.search(r'\bif\b.*?\b(?:then|,|;)\b.*?\b(?:otherwise|else|or)\b', cmd_lower):
        if_match = re.search(r'if\s+(.+?),\s*then\s+(.+?)(?:,?\s*(?:otherwise|else|or)\s+(.+))?', cmd_lower)
        if if_match:
            return {
                "condition": if_match.group(1).strip(),
                "action": if_match.group(2).strip(),
                "fallback": if_match.group(3).strip() if if_match.group(3) else None,
            }

    if re.search(r'\bonly (?:if|when)\b', cmd_lower):
        m = re.search(r'(.+?)\s+(?:only if|unless)\s+(.+)', cmd_lower)
        if m:
            return {"condition": m.group(2).strip(), "action": m.group(1).strip(), "fallback": None}

    # "Only message Rohan if it's past 6 PM" — action first, condition after "if"
    if re.search(r'\bif\b', cmd_lower):
        m = re.search(r'(.+?)\s+if\s+(.+)', cmd_lower)
        if m:
            return {"condition": m.group(2).strip(), "action": m.group(1).strip(), "fallback": None}

    return None


# ── Self-correction detection (Section 5.3) ─────────────────────────

def detect_self_correction(command: str) -> dict | None:
    """Detect if this command is correcting a previous output."""
    cmd_lower = command.lower()
    for indicator in CORRECTION_INDICATORS:
        if indicator in cmd_lower:
            last = memory.last_intent()
            if last:
                return {
                    "corrects_previous": f"{last.get('action', '')} {last.get('target', '')}".strip(),
                    "field": None,
                }
            # Even without memory, the indicator itself signals a correction
            return {
                "corrects_previous": "previous action",
                "field": None,
            }
    return None


# ── Implicit command inference (Section 3.3) ────────────────────────

def detect_implicit(text: str) -> dict | None:
    """Detect implicit intent where no direct action verb is used."""
    for pattern, action, _note in IMPLICIT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if action is None:
                return None
            params = {}
            target = None
            if action == "volume_up":
                params = {"amount": settings.VOLUME_STEP}
            elif action == "brightness_down":
                params = {"amount": -settings.BRIGHTNESS_STEP}
            return {"action": action, "target": target, "parameters": params}
    return None


# ── Intent classification & entity extraction (Section 2.2 Steps 3-4, 9.3) ──

NLP_SYSTEM_PROMPT = """You are the NLP core of ULTRON AI, a Windows 11 laptop management assistant.
Your job is to analyze user input and return a structured JSON object representing the user's intent.

The user may speak casually, informally, in Hinglish, or with slang. You must always interpret
their intent charitably and accurately. Translate non-English input to English internally for
processing.

Given the user input and conversation context provided, return ONLY a valid JSON object
with this structure (no explanation, no markdown):

{
  "intents": ["INTENT_CATEGORY_1", "INTENT_CATEGORY_2"],
  "actions": ["action1", "action2"],
  "targets": ["target1", "target2"],
  "parameters": {"key1": "value1"},
  "confidence": 0.0 to 1.0,
  "detected_language": "language name",
  "requires_clarification": true or false,
  "clarification_question": "question to ask user if needed or null",
  "is_chained": true or false,
  "chain_steps": [
    {"action": "action1", "target": "target1", "parameters": {}}
  ],
  "is_conditional": true or false,
  "condition": "condition description or null",
  "is_correction": true or false,
  "corrects_previous": "description of what is being corrected or null"
}

INTENT CATEGORIES:
SYSTEM_CONTROL, APPLICATION_CONTROL, FILE_OPERATION, MEDIA_CONTROL,
COMMUNICATION, WEB_ACTION, RESEARCH, CONTENT_CREATION, SCREEN_ACTION,
TASK_MANAGEMENT, CONVERSATIONAL, AMBIGUOUS

For each action, extract these entities:
- ACTION: what the user wants done (play, open, send, search, save)
- TARGET: what the action applies to (Spotify, a contact, a file, a URL)
- PARAMETERS: additional specs (song name, timestamp, folder path, message text)
- MODIFIER: how the action should be done (quickly, quietly, in background)
- CONDITION: any conditional logic (if X is open, if Y is available)

For compound commands (multiple actions in one input), set is_chained=true and
list each step in chain_steps. Each step has action, target, parameters.

Confidence: 0.0 (no idea) to 1.0 (certain). Below 0.6 = ask for clarification.
"""

# Template for the user prompt (with placeholders for context injection)
_NLP_USER_PROMPT_TEMPLATE = """Conversation history: {history}
Current system state: {system_state}
Long-term memory context: {memory_context}
User input: {user_input}"""


def _ollama_extract(text: str, context: dict) -> dict | None:
    """Send text + context to the LLM and parse the structured result."""
    try:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)
        user_prompt = _NLP_USER_PROMPT_TEMPLATE.format(
            history=context.get("history", ""),
            system_state=context.get("system_state", ""),
            memory_context=context.get("memory_context", ""),
            user_input=text,
        )
        resp = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": NLP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": settings.NLP_TEMPERATURE, "num_predict": settings.NLP_MAX_TOKENS},
            format="json",
        )
        raw = resp["message"]["content"]
        data = json.loads(raw)
        if isinstance(data, dict) and "intents" in data:
            return data
        # LLM returned a simpler structure — wrap it
        if isinstance(data, dict) and "action" in data:
            return {
                "intents": [_action_to_intent(data.get("action"))],
                "actions": [data.get("action")],
                "targets": [data.get("target")] if data.get("target") else [],
                "parameters": data.get("parameters", {}),
                "confidence": 0.7,
                "detected_language": "English",
                "requires_clarification": False,
                "clarification_question": None,
                "is_chained": False,
                "chain_steps": [],
                "is_conditional": False,
                "condition": None,
                "is_correction": False,
                "corrects_previous": None,
            }
        return None
    except Exception as e:
        print(f"[nlp] LLM extraction failed ({e}); using rule parser", file=sys.stderr)
        return None


def _action_to_intent(action: str) -> str:
    """Map an internal action name to an intent category."""
    a = action.lower()
    if a in ("open_app", "close_app", "switch_window", "minimize_window",
             "maximize_window", "spotify_open"):
        return "APPLICATION_CONTROL"
    if a in ("volume_set", "volume_change", "volume_mute", "brightness_set",
             "brightness_change", "screenshot", "shutdown", "restart", "sleep",
             "lock_screen", "wifi_on", "wifi_off", "battery_status", "tell_time",
             "tell_date", "spotify_volume"):
        return "SYSTEM_CONTROL"
    if a in ("create_folder", "create_file", "delete_path", "move_file",
             "copy_file", "rename_file", "open_file", "search_file",
             "read_file", "list_folder", "open_recent"):
        return "FILE_OPERATION"
    if a.startswith("spotify_") or a == "spotify_play" or a == "spotify_pause" or \
       a == "spotify_toggle" or a == "spotify_next" or a == "spotify_previous" or \
       a == "spotify_seek" or a == "spotify_play_playlist" or a == "spotify_play_nth" or \
       a == "spotify_search_play" or a == "spotify_current" or a == "spotify_like":
        return "MEDIA_CONTROL"
    if a in ("media_play", "media_pause", "media_toggle", "media_next", "media_previous"):
        return "MEDIA_CONTROL"
    if a in ("browse_url", "web_search", "youtube_search", "browser_back",
             "browser_forward", "new_tab", "close_browser", "read_page",
             "click_text", "double_click_text", "right_click_text",
             "scroll", "type_text", "hotkey"):
        return "WEB_ACTION"
    if a in ("send_whatsapp", "send_sms", "make_call", "send_message"):
        return "COMMUNICATION"
    if a == "identify_song":
        return "MEDIA_CONTROL"
    if a in ("refresh_page", "reload_page"):
        return "WEB_ACTION"
    if a == "close_all_windows":
        return "APPLICATION_CONTROL"
    if a == "set_wake_word":
        return "SYSTEM_CONTROL"
    if a in ("research", "find_info", "save_research"):
        return "RESEARCH"
    if a in ("dictate_notepad", "write_email"):
        return "CONTENT_CREATION"
    if a == "screenshot":
        return "SCREEN_ACTION"
    if a in ("task_add", "task_complete", "task_list", "task_remove"):
        return "TASK_MANAGEMENT"
    if a in ("set_wake_word", "add_wake_word"):
        return "SYSTEM_CONTROL"
    if a == "unknown":
        return "CONVERSATIONAL"
    return "AMBIGUOUS"


# ── Rule-based intent extraction (fallback when LLM is unavailable) ──

def _rule_extract(text: str) -> dict:
    """Rule-based intent extraction returning the full JSON structure from 9.3."""
    from .interpreter import parse, TARGET_REQUIRED

    parts = split_compound(text)
    is_chained = len(parts) > 1

    if is_chained:
        chain_steps = []
        actions, targets, intents = [], [], []
        for part in parts:
            intent = parse(part)
            act = intent.get("action", "unknown")
            tgt = intent.get("target") or ""
            actions.append(act)
            if tgt:
                targets.append(tgt)
            intents.append(_action_to_intent(act))
            chain_steps.append({
                "action": act,
                "target": tgt,
                "parameters": intent.get("parameters", {}),
            })
        conf = max(0.7, 0.85 - 0.05 * len(parts))
        return {
            "intents": intents,
            "actions": actions,
            "targets": targets,
            "parameters": {},
            "confidence": round(conf, 2),
            "detected_language": detect_language(text),
            "requires_clarification": False,
            "clarification_question": None,
            "is_chained": True,
            "chain_steps": chain_steps,
            "is_conditional": False,
            "condition": None,
            "is_correction": False,
            "corrects_previous": None,
        }

    # Single command path
    intent = parse(text)
    action = intent.get("action", "unknown")
    target = intent.get("target") or ""
    params = intent.get("parameters", {})

    if action == "unknown":
        conf = 0.3
        requires_clarification = True
        implicit = detect_implicit(text)
        if implicit:
            action = implicit["action"]
            target = implicit.get("target", "")
            params = implicit.get("parameters", {})
            conf = 0.75
            requires_clarification = False
        if action == "unknown":
            return {
                "intents": ["AMBIGUOUS"],
                "actions": ["unknown"],
                "targets": [],
                "parameters": {},
                "confidence": conf,
                "detected_language": detect_language(text),
                "requires_clarification": True,
                "clarification_question": "What would you like me to do?",
                "is_chained": False,
                "chain_steps": [],
                "is_conditional": False,
                "condition": None,
                "is_correction": False,
                "corrects_previous": None,
            }

    high_conf_actions = {
        "volume_set", "volume_mute", "brightness_set", "screenshot", "shutdown",
        "restart", "sleep", "lock_screen", "wifi_on", "wifi_off", "battery_status",
        "tell_time", "tell_date", "spotify_pause", "spotify_play", "spotify_next",
        "spotify_previous", "open_app", "browser_back", "browser_forward", "new_tab",
    }
    conf = 0.9 if action in high_conf_actions else 0.75
    requires_clarification = False

    if action in TARGET_REQUIRED and not target:
        conf = 0.4
        requires_clarification = True

    intent_cat = _action_to_intent(action)

    return {
        "intents": [intent_cat],
        "actions": [action],
        "targets": [target] if target else [],
        "parameters": params,
        "confidence": round(conf, 2),
        "detected_language": detect_language(text),
        "requires_clarification": requires_clarification,
        "clarification_question": "What did you want me to do?" if requires_clarification else None,
        "is_chained": False,
        "chain_steps": [],
        "is_conditional": False,
        "condition": None,
        "is_correction": detect_self_correction(text) is not None,
        "corrects_previous": (detect_self_correction(text) or {}).get("corrects_previous"),
    }


# ── LLM action name normalization ────────────────────────────────
# The LLM often returns generic action names ("open", "play", "pause")
# instead of the registry actions. Map them deterministically.

_ACTION_ALIASES = {
    "open": "open_app", "launch": "open_app", "start": "open_app",
    "pull up": "open_app", "fire up": "open_app", "get going": "open_app",
    "run": "open_app", "activate": "open_app",
    "close": "close_app", "quit app": "close_app", "exit app": "close_app",
    "kill app": "close_app",
    "play": "spotify_search_play", "play music": "media_play",
    "play media": "media_play", "resume": "media_play",
    "pause": "media_pause", "stop music": "media_pause",
    "stop playback": "media_pause", "hold_on": "media_pause",
    "hold": "media_pause", "freeze": "media_pause", "shh": "media_pause",
    "shush": "media_pause", "quiet": "media_pause",
    "wait": "stop", "stop": "stop",
    "next": "media_next", "skip": "media_next", "next track": "media_next",
    "previous": "media_previous", "back": "media_previous", "previous track": "media_previous",
    "shuffle": "media_toggle",
    "mute": "volume_mute", "silence": "volume_mute", "kill volume": "volume_mute",
    "volume up": "volume_change", "louder": "volume_change",
    "increase volume": "volume_change", "volume down": "volume_change",
    "lower volume": "volume_change", "reduce volume": "volume_change",
    "adjust volume": "volume_change", "increase_volume": "volume_change",
    "volume": "volume_change", "decrease_volume": "volume_change",
    "set volume": "volume_set", "volume set": "volume_set",
    "brightness": "brightness_change", "dim": "brightness_change",
    "set brightness": "brightness_set", "brightness set": "brightness_set",
    "screenshot": "screenshot", "screen shot": "screenshot",
    "capture screen": "screenshot", "capture": "screenshot",
    "shutdown": "shutdown", "shut down": "shutdown",
    "restart": "restart", "reboot": "restart",
    "sleep": "sleep", "lock": "lock_screen", "lock screen": "lock_screen",
    "wifi on": "wifi_on", "wifi off": "wifi_off",
    "turn on wifi": "wifi_on", "turn off wifi": "wifi_off",
    "turn wifi on": "wifi_on", "turn wifi off": "wifi_off",
    "enable wifi": "wifi_on", "disable wifi": "wifi_off",
    "reload": "refresh_page", "reload page": "refresh_page",
    "refresh": "refresh_page", "refresh page": "refresh_page",
    "close all": "close_all_windows", "close all windows": "close_all_windows",
    "close everything": "close_all_windows",
     "identify song": "identify_song", "what song": "identify_song",
     "who made this": "identify_song", "who sang this": "identify_song",
     "current song": "identify_song", "now playing": "identify_song",
     "ask for information": "identify_song", "ask_for_information": "identify_song",
     "get information": "find_info", "answer question": "find_info",
    "respond to": "set_wake_word", "wake word": "set_wake_word",
    "send": "send_message", "send message": "send_message",
    "message": "send_message", "text": "send_message",
    "whatsapp": "send_whatsapp", "call": "make_call",
    "search": "web_search", "google": "web_search",
    "youtube search": "youtube_search", "browse": "browse_url",
    "navigate": "browse_url", "go to": "browse_url",
    "scroll": "scroll", "click": "click_text", "type": "type_text",
    "write": "dictate_notepad", "record": "dictate_notepad",
    "dictate": "dictate_notepad", "remember": "save",
    "save": "save_research", "research": "research",
    "find info": "find_info", "look up": "research",
    "create folder": "create_folder", "create file": "create_file",
    "delete": "delete_path", "move": "move_file", "copy": "copy_file",
    "rename": "rename_file", "open file": "open_file",
    "task": "task_add", "task add": "task_add", "add task": "task_add",
    "task complete": "task_complete", "complete task": "task_complete",
    "task done": "task_complete", "task list": "task_list",
    "show tasks": "task_list", "task delete": "task_remove",
    "undo": "undo", "reverse": "undo", "take back": "undo",
    "email": "write_email", "notepad": "dictate_notepad",
    "cancel": "stop", "cancel shutdown": "cancel_shutdown",
    "preference": "set_preference", "set preference": "set_preference",
    "get preference": "get_preference",
}


def _normalize_action(action: str) -> str:
    """Map a generic LLM action name to the registry action."""
    if not action:
        return "unknown"
    a = str(action).lower().strip().replace("_", " ")
    # Direct registry match
    if a.replace(" ", "_") in {
        "open_app", "close_app", "switch_window", "minimize_window", "maximize_window",
        "browse_url", "web_search", "youtube_search", "browser_back", "browser_forward",
        "new_tab", "close_browser", "read_page",
        "click_text", "double_click_text", "right_click_text", "scroll", "type_text", "hotkey",
        "create_folder", "create_file", "delete_path", "move_file", "copy_file",
        "rename_file", "open_file", "search_file", "read_file", "list_folder", "open_recent",
        "volume_change", "volume_set", "volume_mute", "brightness_change", "brightness_set",
        "screenshot", "shutdown", "restart", "sleep", "lock_screen", "wifi_on", "wifi_off",
        "battery_status", "tell_time", "tell_date", "cancel_shutdown",
        "spotify_open", "spotify_play", "spotify_pause", "spotify_toggle",
        "spotify_next", "spotify_previous", "spotify_seek", "spotify_play_playlist",
        "spotify_play_nth", "spotify_search_play", "spotify_current",
        "spotify_volume", "spotify_like", "media_play", "media_pause", "media_toggle",
        "media_next", "media_previous", "send_whatsapp", "send_sms", "make_call",
        "research", "find_info", "save_research", "dictate_notepad", "write_email",
        "task_add", "task_complete", "task_list", "task_remove",
        "set_preference", "get_preference", "stop", "quit", "undo", "unknown",
        "identify_song", "refresh_page", "reload_page", "close_all_windows",
        "set_wake_word", "add_wake_word",
    }:
        return a.replace(" ", "_")
    # Alias lookup (longest match first)
    sorted_keys = sorted(_ACTION_ALIASES.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if a == key or a.startswith(key + " ") or a.endswith(" " + key):
            return _ACTION_ALIASES[key]
    return a.replace(" ", "_")


def _merge_llm_result(llm_result: dict, text: str) -> dict:
    """Post-process the LLM result: inject detected_language, confidence, etc."""
    result = dict(llm_result)

    # Normalize action names from generic LLM output to registry actions
    if result.get("actions"):
        result["actions"] = [_normalize_action(a) for a in result["actions"]]
    if result.get("is_chained") and result.get("chain_steps"):
        for step in result["chain_steps"]:
            if step.get("action"):
                step["action"] = _normalize_action(step["action"])

    # Context-aware disambiguation: "play/start/put on Spotify" means OPEN the app
    targets = result.get("targets", [])
    actions = result.get("actions", [])
    text_lower = text.lower()
    for i, act in enumerate(actions):
        tgt = targets[i].lower() if i < len(targets) and targets[i] else ""
        if act == "spotify_search_play" and tgt in ("spotify", "the spotify", "spotify app"):
            actions[i] = "open_app"
        # "crank it up" / "make it louder" → volume_change
        _volume_slang = r"\b(crank|louder|volume up|turn up|make it louder|amp (?:it )?up)\b"
        if act in ("spotify_search_play", "media_play") and re.search(_volume_slang, text_lower):
            actions[i] = "volume_change"
            targets[i] = "" if not re.search(r"\bvolume", tgt) else tgt
        # "Shh" / "shush" → media_pause
        if act in ("send_whatsapp", "send_sms", "send_message", "media_play") and re.search(r"\b(shh|shush)\b", text_lower):
            actions[i] = "media_pause"
        # "I want to remember this" → screenshot_or_note
        if act in ("save_research", "save", "media_play") and re.search(r"\bremember\b", text_lower):
            actions[i] = "screenshot_or_note"
        # "blast some music" / "put on music" → media_play
        if act == "spotify_search_play" and re.search(r"\b(blast|put on|play some)\b.*\bmusic\b", text_lower):
            actions[i] = "media_play"
        # "I can't hear" / "can't hear the video" → volume_change
        if act in ("spotify_search_play", "media_play") and re.search(r"\bcan'?t hear\b", text_lower):
            actions[i] = "volume_change"
        # "Close everything" → close_all_windows (LLM often says close_app)
        if act == "close_app" and re.search(r"\b(close|kill) (?:everything|all (?:apps?|windows?))\b", text_lower):
            actions[i] = "close_all_windows"
        # "Who made/sang this song?" → identify_song (LLM often says web_search)
        if act in ("web_search", "find_info") and re.search(r"\bwho (?:made|sang|performed|is) (?:this )?song\b", text_lower):
            actions[i] = "identify_song"
        # "This page won't load" → refresh_page (LLM often says open_app/reload)
        if act in ("open_app", "reload_page") and re.search(r"\bwon'?t load\b", text_lower):
            actions[i] = "refresh_page"
    result["actions"] = actions

    if not result.get("detected_language"):
        result["detected_language"] = detect_language(text)
    if result.get("confidence") is None:
        result["confidence"] = 0.75
    if result.get("is_chained") and not result.get("chain_steps"):
        steps = []
        for i, act in enumerate(result.get("actions", [])):
            tgt = result.get("targets", [None])[i] if i < len(result.get("targets", [])) else None
            steps.append({"action": act, "target": tgt or "", "parameters": {}})
        result["chain_steps"] = steps
    return result


# ── Public API ────────────────────────────────────────────────────

def extract_intent(text: str, context: dict | None = None) -> dict:
    """Full NLP pipeline (Section 2.2 Steps 1-7).

    Returns the structured JSON from Section 9.3.
    """
    # Step 1: Transcription normalization
    text = normalize_transcription(text)
    if not text:
        return _empty_result()

    # Step 2: Language detection
    lang = detect_language(text)

    # Step 2b: Translate to English if needed
    if lang not in ("English", "Hinglish"):
        text_for_processing = translate_text(text, "en")
    else:
        text_for_processing = text

    # Step 5: Context injection
    ctx = context or {}
    memory_context = ctx.get("memory_context", "")
    if not memory_context:
        memory_context = memory.recall_relevant(text_for_processing)

    full_context = {
        "history": ctx.get("history", ""),
        "system_state": ctx.get("system_state", ""),
        "memory_context": memory_context,
    }

    # Step 3-4 & 6: Intent classification + entity extraction via LLM
    result = _ollama_extract(text_for_processing, full_context)

    if result is not None:
        result = _merge_llm_result(result, text)
    else:
        result = _rule_extract(text_for_processing)

    # Self-correction detection (Section 5.3)
    correction = detect_self_correction(text)
    if correction and not result.get("is_correction"):
        result["is_correction"] = True
        result["corrects_previous"] = correction["corrects_previous"]

    # Conditional detection (Section 3.5)
    cond = detect_conditional(text)
    if cond:
        result["is_conditional"] = True
        result["condition"] = cond["condition"]

    # Confirmation gating (Section 3.5): "only after I confirm"
    if detect_confirmation_gate(text):
        result["requires_confirmation"] = True

    # Hold preference (Section 3.5): "keep the volume at 50 unless I say otherwise"
    hold_pref = detect_hold_preference(text)
    if hold_pref:
        result["hold_preference"] = hold_pref

    # Custom wake word instruction (Section 7.2)
    wake_word = detect_wake_word_instruction(text)
    if wake_word:
        result["wake_word"] = wake_word
        result["actions"] = ["set_wake_word"]
        result["targets"] = [wake_word]
        result["intents"] = ["SYSTEM_CONTROL"]
        result["confidence"] = 0.9
        result["requires_clarification"] = False

    # Step 6: Confidence scoring adjustment for ambiguity
    if result.get("confidence", 0) < 0.6 and not result.get("requires_clarification"):
        result["requires_clarification"] = True
        if not result.get("clarification_question"):
            result["clarification_question"] = _suggest_clarification(text, result)

    return result


def _empty_result() -> dict:
    return {
        "intents": ["CONVERSATIONAL"],
        "actions": [],
        "targets": [],
        "parameters": {},
        "confidence": 0.0,
        "detected_language": "English",
        "requires_clarification": False,
        "clarification_question": None,
        "is_chained": False,
        "chain_steps": [],
        "is_conditional": False,
        "condition": None,
        "is_correction": False,
        "corrects_previous": None,
        "requires_confirmation": False,
        "hold_preference": None,
        "wake_word": None,
    }


def _suggest_clarification(text: str, result: dict) -> str:
    """Generate a natural clarifying question based on what's missing."""
    targets = result.get("targets", [])
    if not targets:
        return "What did you want me to do with that?"
    if "who" in text.lower() or "send" in text.lower():
        return "Who should I send that to?"
    if "open" in text.lower() or "play" in text.lower():
        return "Which one did you want to open?"
    return "Could you be a bit more specific about what you want?"


def get_conversation_history() -> str:
    """Retrieve the conversation history as a formatted string for context."""
    lines = memory.context_lines()
    return "\n".join(lines) if lines else ""


def get_system_state() -> str:
    """Describe the current system state for context injection."""
    from core import state as core_state
    state_val = core_state.get_state().value
    last_target = memory.last_target() or "nothing yet"
    parts = [f"State: {state_val}", f"Last target mentioned: {last_target}"]
    return "; ".join(parts)


if __name__ == "__main__":
    test_commands = [
        "Open Spotify",
        "Yo ULTRON, blast some music",
        "Play Blinding Lights by The Weeknd",
        "Can you pause for a second?",
        "Take a screenshot of this page",
        "Send Rohan a message saying I'll call him in 5 minutes",
        "Open YouTube, search for lo-fi music, and play the first result",
        "If Spotify is open, just add this song to the queue",
        "कृपया स्पॉटिफ़ी खोलें",
        "Yaar, Spotify open kar",
        "Actually, make that 1080p not 720p",
    ]
    for cmd in test_commands:
        result = extract_intent(cmd)
        print(f"  Input: {cmd}")
        print(f"  → {json.dumps(result, indent=2, ensure_ascii=False)}")
        print()