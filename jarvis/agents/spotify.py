"""Dedicated Spotify agent — full control via the Spotify Web API (spotipy).

Requires (one-time):
  1. Spotify Premium account.
  2. Free app at https://developer.spotify.com/dashboard with redirect URI
     http://127.0.0.1:8888/callback
  3. SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in jarvis/.env

First command triggers a one-time browser consent; the token is then cached
in jarvis/.cache-spotify and refreshed automatically.

Every playback method ensures an active device first: if none, the desktop
app is launched and playback transferred to it.
"""
import subprocess
import sys
import time

from config import settings
from core import state as core_state

SCOPES = ("user-modify-playback-state user-read-playback-state "
          "user-read-currently-playing playlist-read-private "
          "playlist-read-collaborative user-library-modify user-library-read")

_sp = None  # cached spotipy client


class SpotifyNotConfigured(Exception):
    pass


def _client():
    global _sp
    if _sp is not None:
        return _sp
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise SpotifyNotConfigured(
            "Spotify isn't set up yet. Add your client ID and secret to the "
            "dot env file — see the README for the two-minute setup.")
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=SCOPES,
        cache_path=str(settings.PROJECT_ROOT / ".cache-spotify"),
        open_browser=True,
    ), requests_timeout=10)
    return _sp


# ── Device handling ──────────────────────────────────────────────

def _launch_desktop_app() -> None:
    subprocess.Popen([settings.SPOTIFY_EXE])


def _active_device(sp) -> dict | None:
    devices = sp.devices().get("devices", [])
    for d in devices:
        if d.get("is_active"):
            return d
    return devices[0] if devices else None


def _ensure_device(sp, wait: float = 15.0) -> str | None:
    """Return a device id, launching the desktop app if nothing is available."""
    dev = _active_device(sp)
    if dev:
        return dev["id"]
    _launch_desktop_app()
    deadline = time.time() + wait
    while time.time() < deadline:
        if core_state.stop_event.is_set():
            return None
        time.sleep(1.5)
        dev = _active_device(sp)
        if dev:
            try:
                sp.transfer_playback(dev["id"], force_play=False)
            except Exception:
                pass
            return dev["id"]
    return None


def _ready():
    """(sp, device_id) or a spoken error string."""
    try:
        sp = _client()
    except SpotifyNotConfigured as e:
        return str(e)
    dev = _ensure_device(sp)
    if dev is None:
        return "I opened Spotify but it never showed up as a playback device"
    return sp, dev


# ── Open / transport ─────────────────────────────────────────────

def open_spotify() -> str:
    """Launch the desktop app; connect it to the API if configured."""
    _launch_desktop_app()
    try:
        sp = _client()
    except SpotifyNotConfigured:
        return "Opening Spotify"  # app still opens without API creds
    deadline = time.time() + 20
    while time.time() < deadline:
        if core_state.stop_event.is_set():
            return ""
        time.sleep(1.5)
        dev = _active_device(sp)
        if dev:
            try:
                sp.transfer_playback(dev["id"], force_play=False)
            except Exception:
                pass
            return "Spotify is open and ready"
    return "Opening Spotify"


def play() -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    try:
        sp.start_playback(device_id=dev)
    except Exception:
        return "Nothing to resume — try asking for a song or playlist"
    return "Playing"


def pause() -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    try:
        sp.pause_playback(device_id=dev)
    except Exception:
        return "Nothing is playing"
    return "Paused"


def toggle() -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, _dev = r
    cur = sp.current_playback()
    return pause() if cur and cur.get("is_playing") else play()


def next_track() -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    sp.next_track(device_id=dev)
    time.sleep(0.5)
    return f"Skipped. {current_track()}"


def previous_track() -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    sp.previous_track(device_id=dev)
    time.sleep(0.5)
    return f"Going back. {current_track()}"


def seek(seconds: int) -> str:
    """Seek relative: positive = forward, negative = backward."""
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        return "Nothing is playing"
    pos = max(0, cur["progress_ms"] + seconds * 1000)
    pos = min(pos, cur["item"]["duration_ms"] - 1000)
    sp.seek_track(pos, device_id=dev)
    direction = "Forward" if seconds >= 0 else "Back"
    return f"{direction} {abs(seconds)} seconds"


# ── Playlists / search ───────────────────────────────────────────

def _all_playlists(sp) -> list[dict]:
    items, offset = [], 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        items.extend(page["items"])
        if page["next"] is None:
            break
        offset += 50
    return items


def _match_playlist(sp, name: str) -> dict | None:
    name = name.lower().strip()
    playlists = _all_playlists(sp)
    for pl in playlists:  # exact
        if pl["name"].lower() == name:
            return pl
    for pl in playlists:  # substring
        if name in pl["name"].lower() or pl["name"].lower() in name:
            return pl
    # loose word overlap
    words = set(name.split())
    best, best_score = None, 0
    for pl in playlists:
        score = len(words & set(pl["name"].lower().split()))
        if score > best_score:
            best, best_score = pl, score
    return best


def play_playlist(name: str) -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    pl = _match_playlist(sp, name)
    if not pl:
        return f"I couldn't find a playlist called {name}"
    sp.start_playback(device_id=dev, context_uri=pl["uri"])
    return f"Playing your playlist {pl['name']}"


def play_nth(n: int, playlist_name: str | None = None) -> str:
    """Play the nth song (1-based) of a playlist. No playlist named →
    current context if it's a playlist, else the user's first playlist."""
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r

    context_uri, pl_label = None, ""
    if playlist_name:
        pl = _match_playlist(sp, playlist_name)
        if not pl:
            return f"I couldn't find a playlist called {playlist_name}"
        context_uri, pl_label = pl["uri"], pl["name"]
    else:
        cur = sp.current_playback()
        ctx = (cur or {}).get("context") or {}
        if ctx.get("type") == "playlist":
            context_uri, pl_label = ctx["uri"], "the current playlist"
        else:
            playlists = _all_playlists(sp)
            if not playlists:
                return "You don't seem to have any playlists"
            context_uri, pl_label = playlists[0]["uri"], playlists[0]["name"]

    try:
        sp.start_playback(device_id=dev, context_uri=context_uri,
                          offset={"position": max(0, n - 1)})
    except Exception:
        return f"{pl_label} doesn't have {n} songs"
    time.sleep(0.5)
    return f"Playing song {n} from {pl_label}. {current_track()}"


def search_play(query: str) -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    res = sp.search(q=query, type="track", limit=1)
    tracks = res.get("tracks", {}).get("items", [])
    if not tracks:
        return f"No results for {query}"
    t = tracks[0]
    sp.start_playback(device_id=dev, uris=[t["uri"]])
    artists = ", ".join(a["name"] for a in t["artists"])
    return f"Playing {t['name']} by {artists}"


# ── Info / misc ──────────────────────────────────────────────────

def current_track() -> str:
    try:
        sp = _client()
    except SpotifyNotConfigured as e:
        return str(e)
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        return "Nothing is playing right now"
    t = cur["item"]
    artists = ", ".join(a["name"] for a in t["artists"])
    return f"Now playing {t['name']} by {artists}"


def set_volume(pct: int) -> str:
    r = _ready()
    if isinstance(r, str):
        return r
    sp, dev = r
    sp.volume(max(0, min(100, pct)), device_id=dev)
    return f"Spotify volume set to {pct} percent"


def like_current() -> str:
    try:
        sp = _client()
    except SpotifyNotConfigured as e:
        return str(e)
    cur = sp.current_playback()
    if not cur or not cur.get("item"):
        return "Nothing is playing to like"
    sp.current_user_saved_tracks_add([cur["item"]["id"]])
    return f"Added {cur['item']['name']} to your liked songs"


def close_spotify() -> str:
    from control.apps import close_app
    return close_app("spotify")


if __name__ == "__main__":
    print(open_spotify())
    print(current_track())
