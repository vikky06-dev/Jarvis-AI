"""NLP module verification tests (Section 10 checklist)."""
import sys
sys.path.insert(0, ".")

from brain.nlp import (extract_intent, detect_language, normalize_transcription,
                       split_compound, detect_conditional, detect_self_correction,
                       detect_confirmation_gate, detect_hold_preference,
                       detect_wake_word_instruction)
from brain.memory import memory

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")

print("=== INTENT RECOGNITION ===")
# 10 phrasings of "open Spotify"
open_spotify_variants = [
    "Open Spotify", "Launch Spotify", "Start Spotify", "Pull up Spotify",
    "Get Spotify going", "Can you open Spotify for me?", "I want to listen to Spotify",
    "Put on Spotify", "Fire up Spotify", "Yo, open Spotify",
]
for v in open_spotify_variants:
    r = extract_intent(v)
    check(f"open Spotify: {v!r}", "spotify_open" in r.get("actions", []) or "open_app" in r.get("actions", []), f"got {r.get('actions')}")

# 10 phrasings of "pause music"
pause_variants = [
    "Pause", "Stop the music", "Hold on", "Wait", "Pause that",
    "Can you pause for a second?", "Stop playing", "Freeze", "Pause the music", "Shh",
]
for v in pause_variants:
    r = extract_intent(v)
    check(f"pause: {v!r}", "media_pause" in r.get("actions", []) or "spotify_pause" in r.get("actions", []) or "stop" in r.get("actions", []), f"got {r.get('actions')}")

# Slangy commands
slang_tests = [
    ("Yo ULTRON, blast some music", "media_play"),
    ("Kill the volume", "volume_mute"),
    ("Crank it up", "volume_change"),
    ("Dim this thing down", "brightness_change"),
    ("Pull up YouTube real quick", "open_app"),
    ("Make it louder", "volume_change"),
]
for cmd, expected in slang_tests:
    r = extract_intent(cmd)
    check(f"slang: {cmd!r}", expected in r.get("actions", []), f"got {r.get('actions')}")

# Implicit commands
implicit_tests = [
    ("I can't hear the video", "volume_change"),
    ("I need to write something down", "dictate_notepad"),
    ("I want to remember this", "screenshot_or_note"),
]
for cmd, expected in implicit_tests:
    r = extract_intent(cmd)
    check(f"implicit: {cmd!r}", expected in r.get("actions", []), f"got {r.get('actions')}")

# Compound commands
compound = "Open YouTube, search for lo-fi music, and play the first result"
parts = split_compound(compound)
check("compound split", len(parts) >= 3, f"got {len(parts)} parts: {parts}")

# Conditional
cond = detect_conditional("Only message Rohan if it's past 6 PM")
check("conditional detection", cond is not None, f"got {cond}")

# Self-correction
corr = detect_self_correction("Actually, make that 1080p")
check("self-correction detection", corr is not None, f"got {corr}")

print("\n=== LANGUAGE DETECTION ===")
check("English", detect_language("Open Spotify") == "English")
check("Hinglish", detect_language("Yaar, Spotify open kar") == "Hinglish")
check("Hindi", detect_language("कृपया स्पॉटिफ़ी खोलें") in ("Hindi", "Hinglish"))

print("\n=== TEXT NORMALIZATION ===")
norm = normalize_transcription("Um, like, open Spotify please")
check("filler removal", "open spotify" in norm.lower(), f"got {norm!r}")
norm2 = normalize_transcription("Write: Dear Rohan comma how are you question mark")
check("spoken punctuation", "," in norm2 and "?" in norm2, f"got {norm2!r}")

print("\n=== HINGLISH ===")
hinglish_tests = [
    "Yaar, Spotify open kar",
    "Volume thoda kam kar",
    "Screenshot le aur Rohan ko bhej",
    "YouTube pe koi lo-fi daal",
    "Wifi band kar",
    "Bhai ek second, music rok",
    "Notepad mein likh: test",
    "Brightness thodi badha",
    "Ye file Desktop pe save kar",
    "Rohan ko WhatsApp kar, bol raha hoon 10 minute mein call karunga",
]
for h in hinglish_tests:
    r = extract_intent(h)
    check(f"Hinglish: {h!r}", r.get("actions", []) != ["unknown"], f"got {r.get('actions')}")

print("\n=== SLANG / CASUAL (Section 3.2) ===")
slang_extra = [
    ("Flip the Wi-Fi off", "wifi_off"),
    ("Chuck that file in my Downloads", "move_file"),
    ("Close everything", "close_all_windows"),
    ("Lock the screen", "lock_screen"),
]
for cmd, expected in slang_extra:
    r = extract_intent(cmd)
    check(f"slang extra: {cmd!r}", expected in r.get("actions", []), f"got {r.get('actions')}")

print("\n=== IMPLICIT (Section 3.3) ===")
implicit_extra = [
    ("This page won't load", "refresh_page"),
    ("Who made this song?", "identify_song"),
]
for cmd, expected in implicit_extra:
    r = extract_intent(cmd)
    check(f"implicit extra: {cmd!r}", expected in r.get("actions", []), f"got {r.get('actions')}")

print("\n=== CONFIRMATION GATE (Section 3.5) ===")
check("confirmation gate: 'only after I confirm'",
      detect_confirmation_gate("Send the message only after I confirm"))
check("confirmation gate: 'don't send until'",
      detect_confirmation_gate("Don't send the message until I say go"))
check("no gate: normal command",
      not detect_confirmation_gate("Open Spotify"))

print("\n=== HOLD PREFERENCE (Section 3.5) ===")
hp = detect_hold_preference("Keep the volume at 50 unless I say otherwise")
check("hold preference detected", hp is not None and hp["key"] == "default_volume", f"got {hp}")

print("\n=== WAKE WORD INSTRUCTION (Section 7.2) ===")
ww = detect_wake_word_instruction("From now on also respond to Jarvis")
check("wake word instruction", ww == "jarvis", f"got {ww}")
r = extract_intent("From now on also respond to Nova")
check("wake word intent", "set_wake_word" in r.get("actions", []), f"got {r.get('actions')}")

print("\n=== DICTATION MODE (Section 7.1) ===")
from brain.nlp import DICTATION_START_RE, DICTATION_STOP_RE
check("dictation start", bool(DICTATION_START_RE.search("Write this down: hello")))
check("dictation stop", bool(DICTATION_STOP_RE.search("okay stop, now save the file")))

print("\n=== RULE-PARSER FALLBACK (no LLM) ===")
# These must work even when Ollama is unavailable (Section 9.2 fallback)
from brain.interpreter import _rule_parse
memory.clear()
fallback_cases = [
    ("Get Spotify going", "open_app"),
    ("I want to listen to Spotify", "open_app"),
    ("Pause", "media_pause"),
    ("Hold on", "media_pause"),
    ("Freeze", "media_pause"),
    ("Shh", "media_pause"),
    ("Crank it up", "volume_change"),
    ("Dim this thing down", "brightness_change"),
    ("Make it louder", "volume_change"),
    ("Volume thoda kam kar", "volume_change"),
    ("Wifi band kar", "wifi_off"),
    ("Flip the Wi-Fi off", "wifi_off"),
    ("Chuck that file in my Downloads", "move_file"),
    ("Kill the volume", "volume_mute"),
    ("Close everything", "close_all_windows"),
    ("Who made this song?", "identify_song"),
    ("This page won't load", "refresh_page"),
    ("I can't hear the video", "volume_change"),
    ("I need to write something down", "dictate_notepad"),
]
for cmd, expected in fallback_cases:
    r = _rule_parse(cmd)
    check(f"fallback: {cmd!r}", r.get("action") == expected, f"got {r.get('action')}")

# Pronoun resolution must not mangle idioms (Section 3.6)
memory.add("open Chrome", {"action": "open_app", "target": "Chrome", "parameters": {}})
r = _rule_parse("Crank it up")
check("fallback: idiom not mangled by pronoun", r.get("action") == "volume_change", f"got {r.get('action')}")
r = _rule_parse("Make it louder")
check("fallback: 'make it louder' not mangled", r.get("action") == "volume_change", f"got {r.get('action')}")

print(f"\n=== RESULTS: {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)