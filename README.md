# JARVIS — Voice-Controlled PC Assistant for Windows 11

A fully local, voice-controlled AI assistant with a modern dashboard that controls
your entire PC — browser, files, apps, Spotify, and on-screen UI — through
natural-language commands (spoken or typed).

- **Dashboard:** dark glassmorphism window (pywebview) — clock, date, weather,
  location, battery %, a living orb that reacts to your voice and JARVIS's replies,
  a scrolling transcript, and a command box at the bottom
- **Instant stop:** say or type **"stop"** (or press `Esc` / the ■ button) to cut
  JARVIS off mid-sentence — it goes silent immediately and waits for the next command
- **Spotify agent:** full playback control via the Spotify Web API
- **Wake word:** "Hey JARVIS" (always listening, low CPU — silent chunks never touch the STT model)
- **STT:** faster-whisper `base` (offline, int8)
- **Brain:** Ollama `qwen2.5:3b` (offline) with a deterministic regex fallback + repair layer
- **TTS:** pyttsx3 (offline), edge-tts fallback (online) — both interruptible
- **Screen control:** PyAutoGUI + Tesseract OCR (click anything visible by its label)
- **Browser control:** Chrome via Selenium

## Setup

1. **Python 3.10+** — the project venv already lives at `jarvis/.venv` (Python 3.10.10).
   To recreate elsewhere:
   ```
   py -3.10 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
2. **Ollama** — install from https://ollama.com, then:
   ```
   ollama pull qwen2.5:3b
   ```
   (JARVIS still works without Ollama — it falls back to the built-in rule parser.)
3. **Tesseract OCR** — installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
   (edit `config/settings.py` if yours is elsewhere).
4. **Google Chrome** — ChromeDriver is auto-matched by webdriver-manager / Selenium Manager.
5. **Microphone** — any default Windows input device.
6. **Spotify (optional, for the Spotify agent)** — needs Spotify **Premium** and a
   free developer app (2 minutes, one time):
   1. Go to https://developer.spotify.com/dashboard → **Create app**
   2. Name: anything · Redirect URI: `http://127.0.0.1:8888/callback` · API: Web API
   3. Copy the **Client ID** and **Client Secret** into `jarvis/.env`
   4. The first Spotify command opens a browser consent page once; the token is
      then cached in `.cache-spotify` and refreshed automatically.

## Usage

| Mode | Command |
|---|---|
| Dashboard + voice (default) | double-click `run_jarvis.bat` or `python main.py` |
| Headless voice | `run_jarvis.bat --voice` |
| Text/debug REPL | `run_jarvis.bat --text` |
| One-shot | `python main.py --once "open notepad"` |

Say **"Hey JARVIS"**, wait for the wake acknowledgment, then speak your command —
or say it in one breath: *"Hey JARVIS, open Chrome and go to YouTube."*
You can also just type into the command box at the bottom of the dashboard.

**Stopping:** "stop" / "wait" / "cancel" (spoken or typed, or `Esc`, or the ■ button)
interrupts JARVIS instantly — it stays running and waits for your next command.
Say **"goodbye"** / **"exit"** to shut JARVIS down. Low-confidence transcripts (< 0.75) are re-prompted.

## Special launchers

- **"open YouTube"** → opens the *Akshat's YouTube* desktop app (the PWA shortcut
  on your Desktop), not a browser tab. Falls back to a tab if the shortcut is gone.
- **"open Chrome" / "open browser"** → launches real Chrome with your **Default
  profile** (Akshat), with all your logins — not an automation profile.
- **"open Spotify"** → launches the desktop app and connects it to the Spotify agent.
  (Paths/profile configurable in `config/settings.py`.)

## Spotify commands

"open Spotify" · "play" / "pause" / "resume" · "next song" / "previous song" ·
"forward 30 seconds" / "back 15 seconds" · "play my *chill* playlist" ·
"play the **3rd** song from my *workout* playlist" · "play *Blinding Lights* on Spotify" ·
"play *believer*" (bare `play X` goes to Spotify) · "what's playing" ·
"like this song" · "spotify volume 40"

## Voice commands

**Browser** — "open Chrome and go to YouTube" · "search Python tutorials on Google" ·
"search lo-fi music on YouTube" · "go back" / "go forward" · "new tab" ·
"scroll down" · "read the page" · "close Chrome"

**Apps** — "open VS Code" · "open Notepad" · "close Spotify" · "switch window" ·
"minimize the window" · "maximize the window"

**Screen** — "click the Submit button" · "double click OK" · "right click the file" ·
"type Hello World" · "scroll down 10"

**Files** — "create a folder called Projects on my Desktop" ·
"move file report.pdf from Downloads to Documents" · "rename notes.txt to old-notes.txt" ·
"search for the file budget.xlsx" · "read file todo.txt" · "list contents of my Downloads folder" ·
"open the last file I worked on" · "delete file draft.txt" *(goes to `temp/trash`, not permanent)*

**System** — "increase volume by 20 percent" · "set volume to 50" · "mute" ·
"increase brightness" · "take a screenshot" · "lock the screen" · "shut down" *(10-s delay + abort)* ·
"restart" · "sleep" · "what time is it" · "what's the date" · "check battery" ·
"wifi on" / "wifi off" *(may need admin)*

## Architecture

```
jarvis/
├── main.py               threads: UI (main) · voice · worker (queue) · barge-in stop
├── core/     state.py (stop_event, State enum, command queue, UI push helpers)
├── dashboard/ ui.py (pywebview bridge) · info.py (battery/weather/location poller)
│             └── web/ index.html · style.css · app.js (canvas orb)
├── agents/   spotify.py (Spotify Web API agent — spotipy)
├── voice/    listener.py (wake word + STT + mic levels + barge-in) · speaker.py (interruptible TTS)
├── brain/    interpreter.py (LLM intent + regex fallback + repair) · memory.py (context)
├── control/  apps.py · browser.py · screen.py (OCR click) · mouse.py · keyboard.py
├── files/    manager.py
├── system/   os_control.py
└── config/   settings.py (all tunables) · buildlog.py
```

Notes:
- Intent dicts: `{"action", "target", "parameters"}`. The LLM output is cross-checked
  against the rule parser; missing targets and sign errors are repaired deterministically.
- Pronouns ("open **it** again") resolve against the last 5 commands.
- Compound commands split on "and"/"then" and execute in order.
- Destructive deletes are soft (jarvis trash folder). Shutdown has a 10-second abort window.
- PyAutoGUI failsafe: slam the mouse into the top-left corner to abort any automation.

## Troubleshooting

- **pip/TLS errors** — this machine had stale `CURL_CA_BUNDLE`/`OPENSSL_CONF` env vars
  pointing at deleted files; `config/settings.py` scrubs them at runtime. Remove them
  permanently in System → Environment Variables.
- **No speech detected** — check the default mic in Windows Sound settings; lower
  `SILENCE_THRESHOLD` in `config/settings.py` for quiet mics.
- **OCR misses a button** — the label must be visible text; increase zoom or use the
  browser-native click ("click X" works via Selenium when Chrome is open).
