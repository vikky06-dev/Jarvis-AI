"""Intent parsing: Ollama (qwen2.5:3b) primary, rule-based regex fallback.

Every command resolves to an intent dict:
    {"action": str, "target": str|None, "parameters": dict}

The NLP pipeline (brain/nlp.py) provides enhanced parsing with:
  - Full JSON output per Section 9.3 (intents, confidence, is_chained, etc.)
  - Transcription normalization (filler words, false starts, spoken punctuation)
  - Language detection and translation
  - Confidence scoring and ambiguity resolution
  - Conditional command evaluation
"""
import json
import re
import sys

from config import settings
from .memory import memory

# ── Action registry (Section 2.1 intent categories) ─────────────────

ACTIONS = [
    # apps
    "open_app", "close_app", "switch_window", "minimize_window", "maximize_window",
    # browser
    "browse_url", "web_search", "youtube_search", "browser_back", "browser_forward",
    "new_tab", "close_browser", "read_page", "refresh_page", "reload_page",
    "identify_song", "close_all_windows", "set_wake_word",
    # screen / input
    "click_text", "double_click_text", "right_click_text", "scroll", "type_text", "hotkey",
    # files
    "create_folder", "create_file", "delete_path", "move_file", "copy_file",
    "rename_file", "open_file", "search_file", "read_file", "list_folder", "open_recent",
    # system
    "volume_change", "volume_set", "volume_mute", "brightness_change", "brightness_set",
    "screenshot", "shutdown", "restart", "sleep", "lock_screen", "wifi_on", "wifi_off",
    "battery_status", "tell_time", "tell_date", "cancel_shutdown",
    # spotify
    "spotify_open", "spotify_play", "spotify_pause", "spotify_toggle",
    "spotify_next", "spotify_previous", "spotify_seek", "spotify_play_playlist",
    "spotify_play_nth", "spotify_search_play", "spotify_current",
    "spotify_volume", "spotify_like",
    # general media control (across all apps, not just Spotify)
    "media_play", "media_pause", "media_toggle", "media_next", "media_previous",
    # communication (Section 2.1: COMMUNICATION)
    "send_whatsapp", "send_sms", "make_call",
    # research (Section 2.1: RESEARCH)
    "research", "find_info", "save_research",
    # content creation (Section 2.1: CONTENT_CREATION)
    "dictate_notepad", "write_email",
    # task management (Section 2.1: TASK_MANAGEMENT)
    "task_add", "task_complete", "task_list", "task_remove",
    # preference learning (Section 4.3)
    "set_preference", "get_preference",
    # meta
    "stop", "quit", "undo", "unknown",
]

SYSTEM_PROMPT = """You convert voice commands for a Windows PC assistant into JSON.
Reply with ONLY a JSON object, no prose:
{"action": "<one of the allowed actions>", "target": "<main object or null>", "parameters": {}}

Allowed actions: %s

parameters keys by action:
- volume_change/brightness_change: {"amount": int}  (negative = decrease)
- volume_set/brightness_set: {"level": int 0-100}
- scroll: {"direction": "up"|"down", "amount": int clicks (default 5)}
- type_text/dictate_notepad: target = the text to type
- move_file/copy_file: {"source_dir": str, "dest_dir": str} target = filename
- rename_file: {"new_name": str}
- create_folder/create_file: {"location": str e.g. "Desktop"}
- web_search/youtube_search: target = the query
- browse_url: target = url or site name
- hotkey: target = e.g. "ctrl+s"
- spotify_seek: {"seconds": int}  (negative = backward)
- spotify_play_nth: {"n": int, "playlist": str or null}  e.g. "play the 3rd song from my chill playlist"
- spotify_play_playlist: target = playlist name
- spotify_search_play: target = song/artist query  (e.g. "play blinding lights on spotify")
- spotify_volume: {"level": int 0-100}
- send_whatsapp: target = contact name; parameters = {"message": str}
- send_sms: target = contact name; parameters = {"message": str}
- make_call: target = contact name
- research: target = topic to research; parameters = {"filename": str}
- find_info: target = the question
- save_research: target = topic; parameters = {"filename": str}
- dictate_notepad: target = text content; parameters = {"filename": str, "save_path": str}
- write_email: target = recipient; parameters = {"subject": str, "body": str}
- task_add: target = task title; parameters = {"description": str, "priority": str, "due_date": str}
- task_complete: target = task identifier (text or number)
- task_list: parameters = {"filter": "pending"|"all"}
- task_remove: target = task identifier
- set_preference: target = preference key; parameters = {"value": str}
- get_preference: target = preference key

Music/Spotify commands (play, pause, skip, next/previous song, playlists) always
use spotify_* actions. "stop" means interrupt what you're doing (action stop);
"goodbye"/"exit"/"quit" means shut the assistant down (action quit).
Resolve pronouns ("it", "that", "this") using the recent-command context if given.
If the command is not an action request, use action "unknown".
Understand casual/slangy phrasing like "blast some music", "kill the volume",
"pull up YouTube", "crank it up", "dim this thing down".
""" % ", ".join(ACTIONS)

# ── Rule-based fallback parser ───────────────────────────────────

_NUM = r"(\d{1,3})"


def _rule_parse(cmd: str) -> dict:
    c = cmd.lower().strip()
    p = lambda a, t=None, **kw: {"action": a, "target": t, "parameters": kw}

    # ── Slangy / casual commands (Section 3.2) ──
    # NOTE: slang detection runs BEFORE pronoun resolution so idioms like
    # "crank it up" / "turn it down" are not mangled by pronoun substitution.
    # "kill the volume" / "mute the volume" / "shut up"
    if re.search(r"\b(kill|shut up|be quiet|mute) (?:the )?volume\b", c):
        return p("volume_mute")
    # "crank it up" / "make it louder" / "turn it up" / Hinglish "volume badha"
    if re.search(r"\b(crank|turn|make|amp) (?:it |the |things? )?up\b", c) or \
       re.search(r"\bmake it (?:louder|quieter|softer)\b", c) or \
       re.search(r"\b(louder|raise|increase) (?:the )?volume\b", c) or \
       re.search(r"\bvolume (?:thoda|thodi|thora|zara)? ?(?:up|badha|badhao|barha|barhao)\b", c):
        return p("volume_change", amount=settings.VOLUME_STEP)
    # "dim this thing down" / "lower the brightness" / Hinglish "brightness kam"
    if re.search(r"\b(dim|turn down|reduce) (?:this |the )?thing(?: down| off)?\b", c) or \
       re.search(r"\bdim\b.*?\bbrightness\b", c) or \
       re.search(r"\bbrightness (?:thodi|zara)? ?(?:kam|com|niche|ghata)\b", c) or \
       re.search(r"\bvolume (?:thoda|thodi|thora|zara)? ?(?:kam|ghata|ghatao|low|down)\b", c):
        if re.search(r"\bvolume\b", c) and not re.search(r"\bbrightness\b", c):
            return p("volume_change", amount=-settings.VOLUME_STEP)
        return p("brightness_change", amount=-settings.BRIGHTNESS_STEP)
    # "blast some music" / "put on music" / "play some music"
    if re.search(r"\b(blast|put on) (?:some )?music\b", c):
        return p("media_play")
    # "fire up X" / "pull up X" / "get X going"
    if re.search(r"\b(fire up|pull up|get going|put on)\b", c):
        m = re.search(r"\b(?:fire up|pull up|get going|put on)\b\s+(.+?)(?: and .*)?$", c)
        if m:
            return p("open_app", m.group(1).strip())
    # "Get Spotify going" (Section 3.1 phrasing variation)
    m = re.search(r"\bget ([a-z0-9 .]+?) going\b", c)
    if m:
        return p("open_app", m.group(1).strip())
    # "I want to listen to Spotify" / "I want to hear X" → open the app (Section 3.1)
    m = re.search(r"\bi want to (?:listen|hear|watch|play) (?:to )?(.+)", c)
    if m:
        return p("open_app", m.group(1).strip())
    # Bare pause variants (Section 3.1): "Pause", "Hold on", "Freeze", "Shh"
    if re.search(r"^(?:pause|hold on|hold it|wait a sec|shh+|shush+|freeze)\b", c):
        return p("media_pause")
    if re.search(r"\bpause\b", c) or \
       re.search(r"\bstop (?:that|it|playing|the music|the song|the video)\b", c):
        return p("media_pause")
    # "I'm done for the night" → context-dependent shutdown
    if re.search(r"\bi'?m done for the night\b", c):
        return p("shutdown")
    # "I can't hear the video" → increase volume
    if re.search(r"\bi can'?t hear\b", c):
        return p("volume_change", amount=settings.VOLUME_STEP)
    # "I need to write something down" → open Notepad for dictation
    if re.search(r"\bi need to write\b", c):
        return p("dictate_notepad")
    # "Chuck that file in my Downloads" (Section 3.2)
    m = re.search(r"\b(?:chuck|drop|throw) (?:that|this|the)? ?(?:file |document |photo |picture )?(?:in|into|to) (.+)", c)
    if m:
        return p("move_file", m.group(1).strip(), dest_dir=m.group(1).strip())
    # "Flip the Wi-Fi off" / "turn the wifi on" / Hinglish "wifi band kar"
    if re.search(r"\b(flip|turn|switch) (?:the )?wi-?fi off\b", c) or \
       re.search(r"\bwi-?fi (?:band|off) (?:kar|karo)\b", c):
        return p("wifi_off")
    if re.search(r"\b(flip|turn|switch) (?:the )?wi-?fi on\b", c) or \
       re.search(r"\bwi-?fi (?:on|chalu) (?:kar|karo)\b", c):
        return p("wifi_on")
    # "Close everything" / "close all windows"
    if re.search(r"\bclose (?:everything|all (?:apps?|windows?))\b", c):
        return p("close_all_windows")
    # "Who made this song?" → identify current song
    if re.search(r"\bwho (?:made|sang|performed) (?:this )?song\b", c):
        return p("identify_song")
    # "This page won't load" → refresh
    if re.search(r"\bwon'?t load\b", c):
        return p("refresh_page")
    # "From now on also respond to X" → set wake word
    m = re.search(r"\b(?:from now on|also)?\s*(?:respond|answer|react) to (?:the wake word )?(?:'([a-z0-9]+)'|\"([a-z0-9]+)\"|([a-z0-9]+))\b", c)
    if m:
        word = next((g for g in m.groups() if g), None)
        if word and word.lower() not in ("me", "that", "this", "voice", "commands"):
            return p("set_wake_word", word.strip().lower())
    # pronoun resolution (Section 3.6) — runs AFTER slang detection
    for pron in (" it", " that", " this one", " that one", " him", " her", " them"):
        if c.endswith(pron) or f"{pron} " in c + " ":
            last = memory.last_target()
            if last:
                c = c.replace(pron.strip(), last)
    # "play it again" / "again" → repeat the last played item (Section 3.6)
    if re.search(r"\bagain\b", c):
        last = memory.last_intent()
        if last and last.get("action") in ("spotify_search_play", "spotify_play", "media_play", "youtube_search"):
            return p(last["action"], last.get("target"))
        return p("media_play")
    # "Keep the volume at 50 unless I say otherwise" → hold preference
    # "Keep the volume at 50 unless I say otherwise" → hold preference
    m = re.search(r"\bkeep (?:the )?([a-z ]+?) at (\d+)(?:%| percent)? (?:unless|until|till) i say otherwise\b", c)
    if m:
        key = m.group(1).strip().lower()
        key_map = {"volume": "default_volume", "brightness": "default_brightness",
                   "spotify volume": "spotify_default_volume"}
        pref_key = key_map.get(key, f"hold_{key}".replace(" ", "_"))
        return p("set_preference", pref_key, value=m.group(2))
    # "Send the message only after I confirm" → confirmation gate
    if re.search(r"\b(?:only after (?:i|we|my) confirm|wait for (?:my|the) confirm|don'?t (?:send|do|execute|run|close|shut) until|hold (?:it|that) until|until (?:i|we) (?:say|give|confirm|approve))\b", c):
        # Strip the gate phrase and parse the underlying action
        stripped = re.sub(r"\b(?:only after (?:i|we|my) confirm|wait for (?:my|the) confirm|don'?t (?:send|do|execute|run|close|shut) until|hold (?:it|that) until|until (?:i|we) (?:say|give|confirm|approve))\b", "", c).strip()
        if stripped:
            return _rule_parse(stripped)

    # ── Volume / brightness ──
    m = re.search(rf"volume (?:to|at|up) {_NUM}", c) or re.search(rf"set volume {_NUM}", c)
    if m:
        return p("volume_set", level=int(m.group(1)))
    m = re.search(rf"(increase|raise|decrease|lower|reduce) (?:the )?volume(?: by {_NUM}| ${_NUM})?", c)
    if m:
        amt = int(m.group(2)) if m.group(2) else settings.VOLUME_STEP
        return p("volume_change", amount=amt if m.group(1) in ("increase", "raise") else -amt)
    if "mute" in c:
        return p("volume_mute")

    m = re.search(rf"brightness (?:to|at) {_NUM}", c)
    if m:
        return p("brightness_set", level=int(m.group(1)))
    m = re.search(rf"(increase|raise|decrease|lower|reduce) (?:the )?brightness(?: by ${_NUM})?", c)
    if m:
        amt = int(m.group(2)) if m.group(2) else settings.BRIGHTNESS_STEP
        return p("brightness_change", amount=amt if m.group(1) in ("increase", "raise") else -amt)

    # ── System ──
    if re.search(r"\b(screenshot|screen shot)\b", c):
        return p("screenshot")
    if "lock" in c and "screen" in c:
        return p("lock_screen")
    if re.search(r"\bshut ?down\b", c):
        return p("shutdown")
    if re.search(r"\bcancel (?:the )?shutdown\b|\bdon'?t shut ?down\b", c):
        return p("cancel_shutdown")
    if "restart" in c or "reboot" in c:
        return p("restart")
    if re.search(r"\b(sleep|go to sleep)\b", c):
        return p("sleep")
    if "battery" in c:
        return p("battery_status")
    if re.search(r"\bwhat time\b|\btime is it\b", c):
        return p("tell_time")
    if re.search(r"\bwhat(?:'s| is) the date\b|\btoday'?s date\b", c):
        return p("tell_date")
    if re.search(r"\bwifi (on|connect)\b", c):
        return p("wifi_on")
    if re.search(r"\bwifi (off|disconnect)\b", c):
        return p("wifi_off")

    # ── General media control (Section 2.1: MEDIA_CONTROL, non-Spotify) ──
    if re.search(r"\b(play|resume) (?:the )?(?:music|song|video|media)\b", c) and "spotify" not in c:
        return p("media_play")
    if re.search(r"\b(pause|stop) (?:the )?(?:music|song|video|media)\b", c) and "spotify" not in c:
        return p("media_pause")
    if re.search(r"\b(next|skip) (?:the )?(?:song|track|video)\b|\bskip this\b", c) and "spotify" not in c:
        return p("media_next")
    if re.search(r"\b(previous|last) (?:song|track|video)\b|go back a song", c) and "spotify" not in c:
        return p("media_previous")
    m = re.search(r"\b(currently playing|what's playing|what is playing|now playing)\b", c)
    if m:
        return p("spotify_current")  # reuse spotify_current which checks any media

    # ── Spotify (must precede browser rules and the greedy open/close) ──
    if re.search(r"\bopen spotify\b|\bstart spotify\b|\blaunch spotify\b", c):
        return p("spotify_open")
    m = re.search(rf"(?:play )?(?:the )?{_NUM}(?:st|nd|rd|th)? song (?:from|of|in) (?:my )?(.+?)(?: playlist)?$", c)
    if m and ("song" in c):
        return p("spotify_play_nth", n=int(m.group(1)), playlist=m.group(2).strip())
    m = re.search(rf"play (?:the )?{_NUM}(?:st|nd|rd|th)? song", c)
    if m:
        return p("spotify_play_nth", n=int(m.group(1)), playlist=None)
    m = re.search(r"play (?:my )?(?:the )?playlist (.+)", c) or \
        re.search(r"play (?:my )?(.+?) playlist", c)
    if m:
        return p("spotify_play_playlist", m.group(1).strip())
    m = re.search(rf"(?:go |skip |seek )?(forward|ahead) (?:by )?{_NUM} seconds?", c)
    if m:
        return p("spotify_seek", seconds=int(m.group(2)))
    m = re.search(rf"(?:go |skip |seek )?(backward|back) (?:by )?{_NUM} seconds?", c)
    if m:
        return p("spotify_seek", seconds=-int(m.group(2)))
    if re.search(r"\b(next|skip) (?:the )?(song|track)\b|\bskip this\b", c) and "spotify" in c:
        return p("spotify_next")
    if re.search(r"\b(previous|last) (?:song|track)\b|go back a song", c) and "spotify" in c:
        return p("spotify_previous")
    if re.search(r"\bpause\b", c) and "spotify" in c:
        return p("spotify_pause")
    if re.search(r"\bresume\b|\bunpause\b|^play (?:the )?(?:music|song)$|^play$", c):
        return p("spotify_play")
    m = re.search(rf"spotify volume (?:to |at )?{_NUM}", c)
    if m:
        return p("spotify_volume", level=int(m.group(1)))
    if re.search(r"\bwhat(?:'s| is) (?:playing|this song)\b|\bcurrent song\b|\bwhich song\b", c):
        return p("spotify_current")
    if re.search(r"\b(like|save) (?:this|the) (?:song|track)\b", c):
        return p("spotify_like")
    m = re.search(r"play (.+?) (?:on|in) spotify", c)
    if m:
        return p("spotify_search_play", m.group(1).strip())

    # ── Communication: WhatsApp / SMS / calls (Section 2.1) ──
    m = re.search(r"\b(?:send|text|message|whatsapp|ping|drop) (.+?) a message saying (.+)", c)
    if m:
        return p("send_whatsapp", m.group(1).strip(), message=m.group(2).strip())
    m = re.search(r"\b(?:text|message|whatsapp|tell) (.+?)\s*[:,]\s*(.+)", c)
    if m:
        return p("send_whatsapp", m.group(1).strip(), message=m.group(2).strip())
    m = re.search(r"\b(?:call|ring) (.+?)\b", c)
    if m and "spotify" not in c:
        return p("make_call", m.group(1).strip())
    m = re.search(r"\b(?:sms|text) (.+?)\s*[:,]\s*(.+)", c)
    if m:
        return p("send_sms", m.group(1).strip(), message=m.group(2).strip())

    # ── Research (Section 2.1: RESEARCH) ──
    m = re.search(r"\b(?:research|look up|find out about|tell me about) (.+?)(?: and |$)", c)
    if m:
        return p("research", m.group(1).strip())
    if re.search(r"\b(what is|who is|how does|why does|when was|where is) (.+?)\??$", c):
        m2 = re.search(r"\b(what is|who is|how does|why does|when was|where is) (.+?)\b(?:\?|$)?", c)
        if m2:
            return p("find_info", m2.group(2).strip())

    # ── Task management (Section 2.1: TASK_MANAGEMENT) ──
    m = re.search(r"\b(?:add|create) (?:a )?task(?: called| named)? (.+)", c)
    if m:
        return p("task_add", m.group(1).strip())
    m = re.search(r"\b(?:mark|check off|complete) (?:task )?(?:number )?(.+)", c)
    if m:
        return p("task_complete", m.group(1).strip())
    if re.search(r"\b(what('s| is) on my list|show (?:me )?my tasks|list my tasks|what are my tasks|my to-?do)\b", c):
        return p("task_list", "", filter="pending")
    m = re.search(r"\b(?:remove|delete) task (?:number )?(.+)", c)
    if m:
        return p("task_remove", m.group(1).strip())

    # ── Content creation (Section 2.1: CONTENT_CREATION) ──
    m = re.search(r"\b(?:write|dictate|type) (?:in|into|to) notepad (.+)", c)
    if m:
        return p("dictate_notepad", m.group(1).strip())
    m = re.search(r"\b(?:write|draft|create) an? email to (.+?)(?: saying| with| about)\s*[:,]?\s*(.+)", c)
    if m:
        return p("write_email", m.group(1).strip(), subject="", body=m.group(2).strip())
    if re.search(r"\b(?:write|type) this down\b", c):
        return p("dictate_notepad")

    # ── Preference learning (Section 4.3) ──
    m = re.search(r"\bfrom now on(?: always)? save (?:screenshots?|screenshots) to (.+)", c)
    if m:
        return p("set_preference", "screenshot_save_dir", value=m.group(1).strip())
    m = re.search(r"\b(?:i prefer|from now on) (?:shorter|longer|brief|detailed) responses?\b", c)
    if m:
        pref = "brief" if "short" in c or "brief" in c else "detailed"
        return p("set_preference", "response_verbosity", value=pref)
    m = re.search(r"\b(?:always|from now on) open spotify at (\d+)% volume\b", c)
    if m:
        return p("set_preference", "spotify_default_volume", value=m.group(1))
    if re.search(r"\bwhat (?:are|is) my (?:preference|preferences)\b", c):
        return p("get_preference", "")

    # ── Browser ──
    m = re.search(r"search (?:for )?(.+?) on youtube", c)
    if m:
        return p("youtube_search", m.group(1).strip())
    m = re.search(r"search (?:for )?(.+?)(?: on google)?$", c)
    if m and ("search" in c):
        return p("web_search", m.group(1).strip())
    m = re.search(r"(?:go to|navigate to|open) ([\w.-]+\.(?:com|org|net|io|in)\S*)", c)
    if m:
        return p("browse_url", m.group(1))
    m = re.search(r"(?:go to|navigate to) (?:the )?([\w .-]+?)(?: website| site)?$", c)
    if m:
        return p("browse_url", m.group(1).strip())
    if re.search(r"go back", c):
        return p("browser_back")
    if re.search(r"go forward", c):
        return p("browser_forward")
    if "new tab" in c:
        return p("new_tab")
    if re.search(r"read (?:the )?page", c):
        return p("read_page")

    # ── Screen / input ──
    m = re.search(r"scroll (up|down)(?: .*?(\d+))?", c)
    if m:
        return p("scroll", direction=m.group(1), amount=int(m.group(2)) if m.group(2) else 5)

    m = re.search(r"type (.+?)(?: in.*)?$", cmd, re.IGNORECASE)
    if m:
        return p("type_text", m.group(1))

    m = re.search(r"double.?click (?:on )?(?:the )?(.+)", c)
    if m:
        return p("double_click_text", m.group(1).replace(" button", ""))
    m = re.search(r"right.?click (?:on )?(?:the )?(.+)", c)
    if m:
        return p("right_click_text", m.group(1).replace(" button", ""))
    m = re.search(r"click (?:on )?(?:the )?(.+)", c)
    if m:
        return p("click_text", m.group(1).replace(" button", ""))

    # ── Files ──
    m = re.search(r"create (?:a )?folder (?:called |named )?([\w .-]+?)(?: on (?:my )?(\w+))?$", c)
    if m:
        return p("create_folder", m.group(1).strip(), location=m.group(2) or "Desktop")
    m = re.search(r"create (?:a )?file (?:called |named )?([\w .-]+?)(?: on (?:my )?(\w+))?$", c)
    if m:
        return p("create_file", m.group(1).strip(), location=m.group(2) or "Desktop")
    m = re.search(r"delete (?:the )?(?:file |folder )?([\w .-]+)", c)
    if m:
        return p("delete_path", m.group(1).strip())
    m = re.search(r"move (?:the )?file ([\w .-]+) from (\w+) to (\w+)", c)
    if m:
        return p("move_file", m.group(1).strip(), source_dir=m.group(2), dest_dir=m.group(3))
    m = re.search(r"copy (?:the )?file ([\w .-]+) from (\w+) to (\w+)", c)
    if m:
        return p("copy_file", m.group(1).strip(), source_dir=m.group(2), dest_dir=m.group(3))
    m = re.search(r"rename ([\w .-]+) to ([\w .-]+)", c)
    if m:
        return p("rename_file", m.group(1).strip(), new_name=m.group(2).strip())
    m = re.search(r"(?:search for|find) (?:the )?file ([\w .-]+)", c)
    if m:
        return p("search_file", m.group(1).strip())
    m = re.search(r"read (?:the )?file ([\w .-]+)", c)
    if m:
        return p("read_file", m.group(1).strip())
    m = re.search(r"(?:list|show) (?:the )?(?:contents of |files in )?(?:my )?([\w .-]+) folder", c)
    if m:
        return p("list_folder", m.group(1).strip())
    if re.search(r"open (?:the )?last file", c):
        return p("open_recent")
    m = re.search(r"open (?:the )?file ([\w .-]+)", c)
    if m:
        return p("open_file", m.group(1).strip())

    # ── Windows ──
    if re.search(r"switch (?:to (?:the )?)?(?:next )?window|alt tab", c):
        return p("switch_window")
    m = re.search(r"minimi[sz]e (?:the )?(?:window|(.+))", c)
    if m:
        return p("minimize_window", m.group(1))
    m = re.search(r"maximi[sz]e (?:the )?(?:window|(.+))", c)
    if m:
        return p("maximize_window", m.group(1))

    m = re.search(r"close (?:the )?(.+)", c)
    if m:
        t = m.group(1).strip()
        return p("close_browser") if t in ("chrome", "the browser", "browser") else p("close_app", t)
    m = re.search(r"open (.+?)(?: and .*)?$", c)
    if m:
        return p("open_app", m.group(1).strip())

    # bare "play <something>" with no other match → treat as a Spotify request
    m = re.search(r"^play (.+?)(?: on youtube)?$", c)
    if m:
        if c.endswith("on youtube"):
            return p("youtube_search", m.group(1).strip())
        return p("spotify_search_play", m.group(1).strip())

    if re.search(r"\b(undo|reverse|take that back|go back on that)\b", c):
        return p("undo")
    if re.search(r"\b(exit|quit|goodbye|good bye|shut yourself down)\b", c):
        return p("quit")
    if re.search(r"\b(stop|wait|cancel|shut up|be quiet)\b", c):
        return p("stop")
    return p("unknown", cmd)


# ── LLM parser ───────────────────────────────────────────────────

def _llm_parse(cmd: str) -> dict | None:
    try:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)
        ctx = memory.context_lines()
        user = cmd if not ctx else "Recent commands:\n" + "\n".join(ctx) + f"\n\nCommand: {cmd}"
        resp = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.0, "num_predict": 200},
            format="json",
        )
        data = json.loads(resp["message"]["content"])
        if not isinstance(data, dict) or data.get("action") not in ACTIONS:
            return None
        data.setdefault("target", None)
        params = data.get("parameters")
        data["parameters"] = params if isinstance(params, dict) else {}
        return data
    except Exception as e:
        print(f"[interpreter] LLM unavailable ({e}); using rule parser", file=sys.stderr)
        return None


TARGET_REQUIRED = {
    "open_app", "close_app", "browse_url", "web_search", "youtube_search",
    "click_text", "double_click_text", "right_click_text", "type_text", "hotkey",
    "create_folder", "create_file", "delete_path", "move_file", "copy_file",
    "rename_file", "open_file", "search_file", "read_file", "list_folder",
    "spotify_play_playlist", "spotify_search_play",
    "send_whatsapp", "send_sms", "make_call",
    "research", "find_info", "save_research",
    "dictate_notepad", "write_email",
    "task_add", "task_complete", "task_remove",
    "set_preference", "get_preference",
}

_PARAM_TARGET_KEYS = ("query", "name", "text", "url", "app", "app_name", "file", "folder",
                      "message", "topic", "subject", "body", "contact")


def _repair(intent: dict, cmd: str) -> dict:
    """Small local models get the action right but mangle fields — fix the
    common failures deterministically instead of re-prompting."""
    action = intent["action"]
    params = intent["parameters"]

    # type_text: the words to type belong in target; "in this box" is noise
    if action == "type_text" and params.get("text"):
        intent["target"] = str(params.pop("text"))

    # Dictation: text may be in params under "text" key
    if action == "dictate_notepad" and params.get("text"):
        intent["target"] = str(params.pop("text"))

    # Communication: message may be in target or in params under "message"/"text"
    if action in ("send_whatsapp", "send_sms"):
        if not intent.get("target") and params.get("message"):
            # "message Rohan saying hello" — target is contact, message is in params
            intent["target"] = str(params.pop("message")) if not intent.get("target") else intent["target"]
        if not params.get("message") and intent.get("target"):
            # If message is in target but not params, move it
            pass  # The rule parser already handles this correctly

    # target dropped but hiding in parameters under another key
    if not intent.get("target"):
        for key in _PARAM_TARGET_KEYS:
            if params.get(key):
                intent["target"] = str(params.pop(key))
                break

    # still no target — trust the regex parser if it agrees on the action
    if not intent.get("target") and action in TARGET_REQUIRED and action not in ("task_list", "get_preference"):
        ruled = _rule_parse(cmd)
        if ruled["action"] == action and ruled.get("target"):
            intent["target"] = ruled["target"]
            for k, v in ruled["parameters"].items():
                params.setdefault(k, v)

    # "go to X" is navigation, never a search — LLM confuses these
    if action in ("web_search", "youtube_search") and re.search(
            r"^\s*(?:go|navigate) to\b", cmd.lower()):
        intent["action"] = "browse_url"
        m = re.search(r"(?:go|navigate) to (?:the )?(.+?)(?: website| site)?$", cmd.lower())
        if m:
            intent["target"] = m.group(1).strip()

    # sign of volume/brightness deltas must come from the words, not the model
    if action in ("volume_change", "brightness_change") and "amount" in params:
        try:
            amt = abs(int(params["amount"]))
        except (TypeError, ValueError):
            amt = settings.VOLUME_STEP
        negative = re.search(r"\b(decrease|lower|reduce|down|quieter|dimmer)\b", cmd.lower())
        params["amount"] = -amt if negative else amt

    return intent


def parse(cmd: str) -> dict:
    """Parse a single voice command into an intent dict. Never raises."""
    cmd = cmd.strip()
    if not cmd:
        return {"action": "unknown", "target": None, "parameters": {}}
    intent = _llm_parse(cmd)
    intent = _repair(intent, cmd) if intent else _rule_parse(cmd)
    # If the repaired LLM intent still lacks a required target, the rule
    # parser's answer is safer than dispatching a blank.
    if intent["action"] in TARGET_REQUIRED and not intent.get("target"):
        intent = _rule_parse(cmd)
    memory.add(cmd, intent)
    return intent


# ── NLP-integrated parsing (Section 9.2 pipeline) ─────────────────

def parse_nlp(cmd: str, context: dict | None = None) -> dict:
    """Full NLP pipeline extraction — returns the Section 9.3 JSON structure.

    Uses brain/nlp.py for:
      - Transcription normalization (filler words, false starts, spoken punctuation)
      - Language detection + translation
      - Intent classification with confidence scoring
      - Context injection (conversation history + long-term memory)
      - Ambiguity resolution & clarification questions
      - Compound/chained command parsing
      - Conditional command detection
      - Self-correction detection

    Falls back to the rule-based parser if the LLM is unavailable.
    """
    from . import nlp as nlp_module
    result = nlp_module.extract_intent(cmd, context)

    # Convert the rich NLP result back to the simple intent dict for dispatch.
    # If chained, dispatch step-by-step (main.py handles chain_steps).
    if result.get("is_chained") and result.get("chain_steps"):
        # Return the first intent for immediate dispatch, rest in chain_steps
        first = result["chain_steps"][0]
        intent = {
            "action": first["action"],
            "target": first.get("target", "") or None,
            "parameters": first.get("parameters", {}),
            # Extended fields for main.py to consume
            "_nlp_result": result,
            "_is_chained": True,
            "_chain_steps": result["chain_steps"][1:],
            "_requires_clarification": result.get("requires_clarification", False),
            "_clarification_question": result.get("clarification_question"),
            "_confidence": result.get("confidence", 0.0),
            "_detected_language": result.get("detected_language", "English"),
            "_is_conditional": result.get("is_conditional", False),
            "_condition": result.get("condition"),
            "_is_correction": result.get("is_correction", False),
            "_corrects_previous": result.get("corrects_previous"),
            "_requires_confirmation": result.get("requires_confirmation", False),
            "_hold_preference": result.get("hold_preference"),
        }
        memory.add(cmd, intent)
        return intent

    # Single command
    actions = result.get("actions", ["unknown"])
    targets = result.get("targets", [])
    params = result.get("parameters", {})

    intent = {
        "action": actions[0] if actions else "unknown",
        "target": targets[0] if targets else None,
        "parameters": params,
        "_nlp_result": result,
        "_is_chained": False,
        "_chain_steps": [],
        "_requires_clarification": result.get("requires_clarification", False),
        "_clarification_question": result.get("clarification_question"),
        "_confidence": result.get("confidence", 0.0),
        "_detected_language": result.get("detected_language", "English"),
        "_is_conditional": result.get("is_conditional", False),
        "_condition": result.get("condition"),
        "_is_correction": result.get("is_correction", False),
        "_corrects_previous": result.get("corrects_previous"),
        "_requires_confirmation": result.get("requires_confirmation", False),
        "_hold_preference": result.get("hold_preference"),
    }
    memory.add(cmd, intent)
    return intent


# Compound commands: enhanced version using NLP module's splitter (Section 3.4)
def parse_compound(cmd: str) -> list[dict]:
    """Split a compound/chained command and parse each step.

    Uses the NLP module's split_compound which handles more conjunctions
    and ordinal markers (first/next/finally). Each step is parsed with the
    full NLP pipeline so conditional/correction fields are populated.
    """
    from . import nlp as nlp_module

    parts = nlp_module.split_compound(cmd)
    parts = [s.strip() for s in parts if s.strip()]

    if len(parts) <= 1:
        return [parse_nlp(cmd)]
    return [parse_nlp(s) for s in parts]


if __name__ == "__main__":
    print(json.dumps(parse("open Chrome"), indent=2))
