"""General media control across all applications (not just Spotify).

Uses system-level media session controls (Windows 10/11 MediaSession API)
via keyboard media keys and application-specific shortcuts.
"""
import subprocess
import sys
import time

from core import state as core_state


def _media_key(key: str) -> bool:
    """Send a media key via nircmd or pyautogui media keys."""
    # Try nircmd (install nircmd.exe to PATH or set path below)
    try:
        nircmd = getattr(sys.modules.get("config.settings", None), "NIRCMD_EXE", None)
        if nircmd and __import__("os").path.exists(nircmd):
            key_map = {
                "play": "media-play-pause",
                "pause": "media-play-pause",
                "next": "media-next",
                "previous": "media-prev",
                "mute": "mute",
                "volume_up": "changesysvolume 5000",
                "volume_down": "changesysvolume -5000",
            }
            if key in key_map:
                subprocess.run([nircmd, key_map[key]], capture_output=True)
                return True
    except Exception:
        pass

    # Fallback: pyautogui media keys
    try:
        import pyautogui
        key_map = {
            "play": "playpause",
            "pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
            "mute": "volumemute",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
        }
        if key in key_map:
            pyautogui.press(key_map[key])
            return True
    except Exception:
        pass

    return False


def play() -> str:
    """Play/pause the currently playing media across any app."""
    if _media_key("play"):
        return "Playing"
    return "Couldn't send a play command"


def pause() -> str:
    """Pause the currently playing media across any app."""
    if _media_key("pause"):
        return "Paused"
    return "Couldn't send a pause command"


def toggle_playback() -> str:
    """Toggle play/pause across any app."""
    if _media_key("play"):
        return "Toggled playback"
    return "Couldn't toggle playback"


def next_track() -> str:
    """Skip to the next track across any app."""
    if _media_key("next"):
        return "Skipped to next track"
    return "Couldn't skip track"


def previous_track() -> str:
    """Go back to the previous track across any app."""
    if _media_key("previous"):
        return "Went back to previous track"
    return "Couldn't go back"


def set_volume(level: int) -> str:
    """Set system volume to a percentage (0-100)."""
    from system.os_control import set_volume as os_set_volume
    return os_set_volume(level)


def increase_volume(amount: int = 10) -> str:
    """Increase volume by a percentage."""
    from system.os_control import change_volume, get_volume
    new_vol = get_volume() + amount
    return change_volume(amount)


def decrease_volume(amount: int = 10) -> str:
    """Decrease volume by a percentage."""
    from system.os_control import change_volume
    return change_volume(-amount)


def mute() -> str:
    """Toggle mute on/off."""
    if _media_key("mute"):
        from system.os_control import toggle_mute
        return toggle_mute()
    return "Couldn't toggle mute"


def get_current_media() -> str:
    """Get the currently playing media title (via PowerShell)."""
    try:
        result = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             "(Get-CimInstance -Namespace root\\media\\transient -ClassName"
             " CurrentMediaMetadata 2>$null | Select-Object -First 1"
             " | ForEach-Object { \"$($_.Title) by $($_.Artist)\" }) 2>$null"
             " | Out-String"],
            capture_output=True, text=True, timeout=5,
        )
        text = result.stdout.strip()
        if text:
            return f"Now playing: {text}"
        # Fallback: check if Spotify is active
        result2 = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-Command",
             "powershell -command \"(New-Object -ComObject WScript.Shell).AppActivate('Spotify')\""],
            capture_output=True, timeout=5,
        )
        return "Nothing currently playing"
    except Exception:
        return "Couldn't detect current media"


if __name__ == "__main__":
    print(play())
    print(next_track())
