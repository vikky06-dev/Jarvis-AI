"""Background info poller: battery, IP-based location, open-meteo weather.

Pushes {battery, charging, temp, condition, location} to the dashboard every
settings.UI_INFO_POLL_SECONDS. All lookups degrade gracefully offline.
"""
import threading
import time

from config import settings
from core import state as core_state

# WMO weather codes → icon keys used by app.js
_WMO = {
    0: "clear", 1: "mostly_clear", 2: "mostly_clear", 3: "cloudy",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    61: "rain", 63: "rain", 65: "rain", 80: "rain", 81: "rain", 82: "rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow", 85: "snow", 86: "snow",
    95: "thunder", 96: "thunder", 99: "thunder",
}

_geo_cache = None  # (lat, lon, "City, Region") — IP geo rarely changes


def _battery() -> dict:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return {}
        return {"battery": round(b.percent), "charging": b.power_plugged}
    except Exception:
        return {}


def _location() -> tuple | None:
    global _geo_cache
    if _geo_cache:
        return _geo_cache
    try:
        import requests
        r = requests.get("http://ip-api.com/json/?fields=status,city,regionName,lat,lon",
                         timeout=5).json()
        if r.get("status") == "success":
            _geo_cache = (r["lat"], r["lon"], f"{r['city']}, {r['regionName']}")
            return _geo_cache
    except Exception:
        pass
    return None


def _weather(lat: float, lon: float) -> dict:
    try:
        import requests
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,weather_code"},
            timeout=6).json()
        cur = r.get("current", {})
        return {"temp": cur.get("temperature_2m"),
                "condition": _WMO.get(cur.get("weather_code"), "unknown")}
    except Exception:
        return {}


def _poll_loop() -> None:
    while True:
        info = _battery()
        geo = _location()
        if geo:
            lat, lon, label = geo
            info["location"] = label
            info.update(_weather(lat, lon))
        if info:
            core_state.push_info(info)
        time.sleep(settings.UI_INFO_POLL_SECONDS)


def start() -> None:
    threading.Thread(target=_poll_loop, daemon=True, name="info-poller").start()
