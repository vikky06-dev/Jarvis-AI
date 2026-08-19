"""Intent parsing: Ollama (qwen2.5:3b) primary, rule-based regex fallback.

Every command resolves to an intent dict:
    {"action": str, "target": str|None, "parameters": dict}
"""
import json
import re
import sys

from config import settings
from .memory import memory

ACTIONS = [
    # apps
    "open_app", "close_app", "switch_window", "minimize_window", "maximize_window",
    # browser
    "browse_url", "web_search", "youtube_search", "browser_back", "browser_forward",
    "new_tab", "close_browser", "read_page",
    # screen / input
    "click_text", "double_click_text", "right_click_text", "scroll", "type_text", "hotkey",
    # files
    "create_folder", "create_file", "delete_path", "move_file", "copy_file",
    "rename_file", "open_file", "search_file", "read_file", "list_folder", "open_recent",
    # system
    "volume_change", "volume_set", "volume_mute", "brightness_change", "brightness_set",
    "screenshot", "shutdown", "restart", "sleep", "lock_screen", "wifi_on", "wifi_off",
    "battery_status", "tell_time", "tell_date",
    # spotify
    "spotify_open", "spotify_play", "spotify_pause", "spotify_toggle",
    "spotify_next", "spotify_previous", "spotify_seek", "spotify_play_playlist",
    "spotify_play_nth", "spotify_search_play", "spotify_current",
    "spotify_volume", "spotify_like",
    # meta
    "stop", "quit", "unknown",
]

SYSTEM_PROMPT = """You convert voice commands for a Windows PC assistant into JSON.
Reply with ONLY a JSON object, no prose:
{"action": "<one of the allowed actions>", "target": "<main object or null>", "parameters": {}}

Allowed actions: %s

parameters keys by action:
- volume_change/brightness_change: {"amount": int}  (negative = decrease)
- volume_set/brightness_set: {"level": int 0-100}
- scroll: {"direction": "up"|"down", "amount": int clicks (default 5)}
- type_text: target = the text to type
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

Music/Spotify commands (play, pause, skip, next/previous song, playlists) always
use spotify_* actions. "stop" means interrupt what you're doing (action stop);
"goodbye"/"exit"/"quit" means shut the assistant down (action quit).
Resolve pronouns ("it", "that", "this") using the recent-command context if given.
If the command is not an action request, use action "unknown".
""" % ", ".join(ACTIONS)

# ── Rule-based fallback parser ───────────────────────────────────

_NUM = r"(\d{1,3})"

def _rule_parse(cmd: str) -> dict:
    c = cmd.lower().strip()
    p = lambda a, t=None, **kw: {"action": a, "target": t, "parameters": kw}

    # pronoun resolution
    for pron in (" it", " that", " this one", " that one"):
        if c.endswith(pron) or f"{pron} " in c + " ":
            last = memory.last_target()
            if last:
                c = c.replace(pron.strip(), last)

    m = re.search(rf"volume (?:to|at) {_NUM}", c) or re.search(rf"set volume {_NUM}", c)
    if m: return p("volume_set", level=int(m.group(1)))
    m = re.search(rf"(increase|raise|decrease|lower|reduce) (?:the )?volume(?: by {_NUM}| {_NUM})?", c)
    if m:
        amt = int(m.group(2)) if m.group(2) else settings.VOLUME_STEP
        return p("volume_change", amount=amt if m.group(1) in ("increase", "raise") else -amt)
    if "mute" in c: return p("volume_mute")

    m = re.search(rf"brightness (?:to|at) {_NUM}", c)
    if m: return p("brightness_set", level=int(m.group(1)))
    m = re.search(rf"(increase|raise|decrease|lower|reduce) (?:the )?brightness(?: by {_NUM})?", c)
    if m:
        amt = int(m.group(2)) if m.group(2) else settings.BRIGHTNESS_STEP
        return p("brightness_change", amount=amt if m.group(1) in ("increase", "raise") else -amt)

    if re.search(r"\b(screenshot|screen shot)\b", c): return p("screenshot")
    if "lock" in c and "screen" in c: return p("lock_screen")
    if re.search(r"\bshut ?down\b", c): return p("shutdown")
    if "restart" in c or "reboot" in c: return p("restart")
    if re.search(r"\b(sleep|go to sleep)\b", c): return p("sleep")
    if "battery" in c: return p("battery_status")
    if re.search(r"\bwhat time\b|\btime is it\b", c): return p("tell_time")
    if re.search(r"\bwhat(?:'s| is) the date\b|\btoday'?s date\b", c): return p("tell_date")
    if re.search(r"\bwifi (on|connect)\b", c): return p("wifi_on")
    if re.search(r"\bwifi (off|disconnect)\b", c): return p("wifi_off")

    # ── Spotify (must precede browser rules and the greedy open/close) ──
    if re.search(r"\bopen spotify\b|\bstart spotify\b|\blaunch spotify\b", c):
        return p("spotify_open")
    m = re.search(rf"(?:play )?(?:the )?{_NUM}(?:st|nd|rd|th)? song (?:from|of|in) (?:my )?(.+?)(?: playlist)?$", c)
    if m and ("song" in c): return p("spotify_play_nth", n=int(m.group(1)), playlist=m.group(2).strip())
    m = re.search(rf"play (?:the )?{_NUM}(?:st|nd|rd|th)? song", c)
    if m: return p("spotify_play_nth", n=int(m.group(1)), playlist=None)
    m = re.search(r"play (?:my )?(?:the )?playlist (.+)", c) or \
        re.search(r"play (?:my )?(.+?) playlist", c)
    if m: return p("spotify_play_playlist", m.group(1).strip())
    m = re.search(rf"(?:go |skip |seek )?(forward|ahead) (?:by )?{_NUM} seconds?", c)
    if m: return p("spotify_seek", seconds=int(m.group(2)))
    m = re.search(rf"(?:go |skip |seek )?(backward|back) (?:by )?{_NUM} seconds?", c)
    if m: return p("spotify_seek", seconds=-int(m.group(2)))
    if re.search(r"\b(next|skip) (?:the )?(song|track)\b|\bskip this\b", c):
        return p("spotify_next")
    if re.search(r"\b(previous|last) (?:song|track)\b|go back a song", c):
        return p("spotify_previous")
    if re.search(r"\bpause\b", c): return p("spotify_pause")
    if re.search(r"\bresume\b|\bunpause\b|^play (?:the )?(?:music|song)$|^play$", c):
        return p("spotify_play")
    m = re.search(rf"spotify volume (?:to |at )?{_NUM}", c)
    if m: return p("spotify_volume", level=int(m.group(1)))
    if re.search(r"\bwhat(?:'s| is) (?:playing|this song)\b|\bcurrent song\b|\bwhich song\b", c):
        return p("spotify_current")
    if re.search(r"\b(like|save) (?:this|the) (?:song|track)\b", c):
        return p("spotify_like")
    m = re.search(r"play (.+?) (?:on|in) spotify", c)
    if m: return p("spotify_search_play", m.group(1).strip())

    m = re.search(r"search (?:for )?(.+?) on youtube", c)
    if m: return p("youtube_search", m.group(1))
    m = re.search(r"search (?:for )?(.+?)(?: on google)?$", c)
    if m and ("search" in c): return p("web_search", m.group(1))
    m = re.search(r"(?:go to|navigate to|open) ([\w.-]+\.(?:com|org|net|io|in)\S*)", c)
    if m: return p("browse_url", m.group(1))
    m = re.search(r"(?:go to|navigate to) (?:the )?([\w .-]+?)(?: website| site)?$", c)
    if m: return p("browse_url", m.group(1).strip())
    if re.search(r"go back", c): return p("browser_back")
    if re.search(r"go forward", c): return p("browser_forward")
    if "new tab" in c: return p("new_tab")
    if re.search(r"read (?:the )?page", c): return p("read_page")

    m = re.search(r"scroll (up|down)(?: .*?(\d+))?", c)
    if m: return p("scroll", direction=m.group(1), amount=int(m.group(2)) if m.group(2) else 5)

    m = re.search(r"type (.+?)(?: in.*)?$", cmd, re.IGNORECASE)
    if m: return p("type_text", m.group(1))

    m = re.search(r"double.?click (?:on )?(?:the )?(.+)", c)
    if m: return p("double_click_text", m.group(1).replace(" button", ""))
    m = re.search(r"right.?click (?:on )?(?:the )?(.+)", c)
    if m: return p("right_click_text", m.group(1).replace(" button", ""))
    m = re.search(r"click (?:on )?(?:the )?(.+)", c)
    if m: return p("click_text", m.group(1).replace(" button", ""))

    m = re.search(r"create (?:a )?folder (?:called |named )?([\w .-]+?)(?: on (?:my )?(\w+))?$", c)
    if m: return p("create_folder", m.group(1).strip(), location=m.group(2) or "Desktop")
    m = re.search(r"create (?:a )?file (?:called |named )?([\w .-]+?)(?: on (?:my )?(\w+))?$", c)
    if m: return p("create_file", m.group(1).strip(), location=m.group(2) or "Desktop")
    m = re.search(r"delete (?:the )?(?:file |folder )?([\w .-]+)", c)
    if m: return p("delete_path", m.group(1).strip())
    m = re.search(r"move (?:the )?file ([\w .-]+) from (\w+) to (\w+)", c)
    if m: return p("move_file", m.group(1).strip(), source_dir=m.group(2), dest_dir=m.group(3))
    m = re.search(r"copy (?:the )?file ([\w .-]+) from (\w+) to (\w+)", c)
    if m: return p("copy_file", m.group(1).strip(), source_dir=m.group(2), dest_dir=m.group(3))
    m = re.search(r"rename ([\w .-]+) to ([\w .-]+)", c)
    if m: return p("rename_file", m.group(1).strip(), new_name=m.group(2).strip())
    m = re.search(r"(?:search for|find) (?:the )?file ([\w .-]+)", c)
    if m: return p("search_file", m.group(1).strip())
    m = re.search(r"read (?:the )?file ([\w .-]+)", c)
    if m: return p("read_file", m.group(1).strip())
    m = re.search(r"(?:list|show) (?:the )?(?:contents of |files in )?(?:my )?([\w .-]+) folder", c)
    if m: return p("list_folder", m.group(1).strip())
    if re.search(r"open (?:the )?last file", c): return p("open_recent")
    m = re.search(r"open (?:the )?file ([\w .-]+)", c)
    if m: return p("open_file", m.group(1).strip())

    if re.search(r"switch (?:to (?:the )?)?(?:next )?window|alt tab", c): return p("switch_window")
    m = re.search(r"minimi[sz]e (?:the )?(?:window|(.+))", c)
    if m: return p("minimize_window", m.group(1))
    m = re.search(r"maximi[sz]e (?:the )?(?:window|(.+))", c)
    if m: return p("maximize_window", m.group(1))

    m = re.search(r"close (?:the )?(.+)", c)
    if m:
        t = m.group(1).strip()
        return p("close_browser") if t in ("chrome", "the browser", "browser") else p("close_app", t)
    m = re.search(r"open (.+?)(?: and .*)?$", c)
    if m: return p("open_app", m.group(1).strip())

    # bare "play <something>" with no other match → treat as a Spotify request
    m = re.search(r"^play (.+?)(?: on youtube)?$", c)
    if m:
        if c.endswith("on youtube"):
            return p("youtube_search", m.group(1).strip())
        return p("spotify_search_play", m.group(1).strip())

    if re.search(r"\b(exit|quit|goodbye|good bye|shut yourself down)\b", c): return p("quit")
    if re.search(r"\b(stop|wait|cancel|shut up|be quiet)\b", c): return p("stop")
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
}

_PARAM_TARGET_KEYS = ("query", "name", "text", "url", "app", "app_name", "file", "folder")


def _repair(intent: dict, cmd: str) -> dict:
    """Small local models get the action right but mangle fields — fix the
    common failures deterministically instead of re-prompting."""
    action = intent["action"]
    params = intent["parameters"]

    # type_text: the words to type belong in target; "in this box" is noise
    if action == "type_text" and params.get("text"):
        intent["target"] = str(params.pop("text"))

    # target dropped but hiding in parameters under another key
    if not intent.get("target"):
        for key in _PARAM_TARGET_KEYS:
            if params.get(key):
                intent["target"] = str(params.pop(key))
                break

    # still no target — trust the regex parser if it agrees on the action
    if not intent.get("target") and action in TARGET_REQUIRED:
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
    """Parse a voice command into an intent dict. Never raises."""
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


# Compound commands: "open chrome and go to youtube"
def parse_compound(cmd: str) -> list[dict]:
    parts = re.split(r"\b(?:and then|then|and)\b", cmd, flags=re.IGNORECASE)
    parts = [s.strip() for s in parts if s.strip()]
    if len(parts) <= 1:
        return [parse(cmd)]
    return [parse(s) for s in parts]


if __name__ == "__main__":
    print(json.dumps(parse("open Chrome"), indent=2))
