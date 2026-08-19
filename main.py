"""JARVIS master controller.

Threads (UI mode, the default):
    main thread   — pywebview dashboard window
    voice thread  — wake word → transcribe → push command to queue
    worker thread — drain queue → parse intent → dispatch → speak
    barge thread  — while SPEAKING, listen for "stop" (instant interrupt)

Run modes:
    python main.py                 # dashboard + voice (default)
    python main.py --voice         # headless voice mode (no UI)
    python main.py --text          # type commands instead of speaking (debug)
    python main.py --once "cmd"    # execute one command and exit (testing)
"""
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import settings
from core import state as core_state
from core.state import State
from voice.speaker import speak
from brain import interpreter
from brain.memory import memory


# ── Dispatcher ───────────────────────────────────────────────

def _open_youtube() -> str:
    """Special case: launch the user's Desktop YouTube app shortcut."""
    if os.path.exists(settings.YOUTUBE_SHORTCUT):
        os.startfile(settings.YOUTUBE_SHORTCUT)
        return "Opening YouTube"
    from control.browser import navigate  # fallback: Selenium tab
    return navigate("youtube", browser_type="brave")


def _open_chrome() -> str:
    """Special case: real Chrome with the user's default profile."""
    subprocess.Popen([settings.CHROME_EXE,
                      f"--profile-directory={settings.CHROME_PROFILE}"])
    return "Opening Chrome"


def dispatch(intent: dict) -> str:
    """Route an intent to the right module. Returns the spoken response."""
    action = intent.get("action", "unknown")
    target = intent.get("target") or ""
    params = intent.get("parameters", {}) or {}

    # Lazy imports keep startup fast and let one broken module not sink the rest.
    if action == "open_app":
        t = target.lower().strip()
        # Special launchers first: YouTube desktop app, Chrome default profile,
        # Spotify agent. Then site shortcuts, then normal app search.
        if t in ("youtube", "youtube app"):
            return _open_youtube()
        if "chrome" in t or t in ("browser", "the browser", "a browser", "web browser"):
            return _open_chrome()
        if "spotify" in t:
            from agents import spotify
            return spotify.open_spotify()
        from control.browser import SITE_SHORTCUTS, navigate
        if t in SITE_SHORTCUTS:
            return navigate(target)
        from control.apps import open_app
        return open_app(target)
    if action == "close_app":
        from control.apps import close_app
        return close_app(target)
    if action == "switch_window":
        from control.apps import switch_window
        return switch_window()
    if action == "minimize_window":
        from control.apps import minimize_window
        return minimize_window(target or None)
    if action == "maximize_window":
        from control.apps import maximize_window
        return maximize_window(target or None)

    if action == "browse_url":
        from control.browser import navigate
        return navigate(target)
    if action == "web_search":
        from control.browser import search_google
        return search_google(target)
    if action == "youtube_search":
        from control.browser import search_youtube
        return search_youtube(target)
    if action == "browser_back":
        from control.browser import back
        return back()
    if action == "browser_forward":
        from control.browser import forward
        return forward()
    if action == "new_tab":
        from control.browser import new_tab
        return new_tab(target or None)
    if action == "close_browser":
        from control.browser import close_browser
        return close_browser()
    if action == "read_page":
        from control.browser import read_page
        return read_page()
    if action in ("refresh_page", "reload_page"):
        from control import browser
        if browser._driver is not None:
            browser._driver.refresh()
            return "Refreshed the page"
        return "I can't refresh — no browser page is open. Want me to open one?"
    if action == "identify_song":
        from control.media import get_current_media
        return get_current_media()
    if action == "close_all_windows":
        from control.apps import close_all_windows
        return close_all_windows()
    if action == "set_wake_word":
        from brain.memory import memory as _mem
        word = target or params.get("word", "")
        if not word:
            return "What wake word should I respond to?"
        # Persist to memory + runtime set (Section 7.2)
        existing = _mem.get_preference("custom_wake_words", "")
        words = [w.strip() for w in existing.split(",") if w.strip()] if existing else []
        if word not in words:
            words.append(word)
        _mem.store_preference("custom_wake_words", ",".join(words))
        settings.CUSTOM_WAKE_WORDS.add(word)
        return f"Got it — I'll also respond to {word} from now on"

    if action in ("click_text", "double_click_text", "right_click_text"):
        # Prefer clicking inside the live Selenium page when browser is open.
        if action == "click_text":
            from control import browser
            if browser._driver is not None:
                result = browser.click_element(target)
                if "couldn" not in result.lower():
                    return result
        from control.screen import click_text
        clicks = 2 if action == "double_click_text" else 1
        button = "right" if action == "right_click_text" else "left"
        return click_text(target, button=button, clicks=clicks)
    if action == "scroll":
        direction = params.get("direction", "down")
        amount = int(params.get("amount", 5))
        from control import browser
        if browser._driver is not None:
            return browser.scroll_page(direction, amount)
        from control.mouse import scroll
        scroll(direction, amount)
        return f"Scrolled {direction}"
    if action == "type_text":
        from control.keyboard import type_text
        type_text(target)
        return "Done typing"
    if action == "hotkey":
        from control.keyboard import hotkey
        hotkey(target)
        return f"Pressed {target}"

    if action == "create_folder":
        from files.manager import create_folder
        return create_folder(target, params.get("location"))
    if action == "create_file":
        from files.manager import create_file
        return create_file(target, params.get("location"))
    if action == "delete_path":
        from files.manager import delete_path
        return delete_path(target)
    if action == "move_file":
        from files.manager import move_file
        return move_file(target, params.get("source_dir", "Downloads"),
                         params.get("dest_dir", "Documents"))
    if action == "copy_file":
        from files.manager import copy_file
        return copy_file(target, params.get("source_dir", "Downloads"),
                         params.get("dest_dir", "Documents"))
    if action == "rename_file":
        from files.manager import rename_file
        return rename_file(target, params.get("new_name", target))
    if action == "open_file":
        from files.manager import open_file
        return open_file(target)
    if action == "open_recent":
        from files.manager import open_recent
        return open_recent()
    if action == "search_file":
        from files.manager import search_file
        return search_file(target)
    if action == "read_file":
        from files.manager import read_file
        return read_file(target)
    if action == "list_folder":
        from files.manager import list_folder
        return list_folder(target)

    if action == "volume_set":
        from system.os_control import set_volume
        return set_volume(int(params.get("level", 50)))
    if action == "volume_change":
        from system.os_control import change_volume
        return change_volume(int(params.get("amount", settings.VOLUME_STEP)))
    if action == "volume_mute":
        from system.os_control import toggle_mute
        return toggle_mute()
    if action == "brightness_set":
        from system.os_control import set_brightness
        return set_brightness(int(params.get("level", 50)))
    if action == "brightness_change":
        from system.os_control import change_brightness
        return change_brightness(int(params.get("amount", settings.BRIGHTNESS_STEP)))
    if action == "screenshot":
        from control.screen import take_screenshot
        _, path = take_screenshot(save=True)
        return f"Screenshot saved to Desktop"
    if action == "shutdown":
        from system.os_control import shutdown
        return shutdown()
    if action == "restart":
        from system.os_control import restart
        return restart()
    if action == "sleep":
        from system.os_control import sleep_pc
        return sleep_pc()
    if action == "lock_screen":
        from system.os_control import lock_screen
        return lock_screen()
    if action == "wifi_on":
        from system.os_control import wifi_on
        return wifi_on()
    if action == "wifi_off":
        from system.os_control import wifi_off
        return wifi_off()
    if action == "battery_status":
        from system.os_control import battery_status
        return battery_status()
    if action == "tell_time":
        from system.os_control import tell_time
        return tell_time()
    if action == "tell_date":
        from system.os_control import tell_date
        return tell_date()

    # ── Spotify agent ────────────────────────────────────────────
    if action.startswith("spotify_"):
        from agents import spotify
        if action == "spotify_open":
            return spotify.open_spotify()
        if action == "spotify_play":
            return spotify.play()
        if action == "spotify_pause":
            return spotify.pause()
        if action == "spotify_toggle":
            return spotify.toggle()
        if action == "spotify_next":
            return spotify.next_track()
        if action == "spotify_previous":
            return spotify.previous_track()
        if action == "spotify_seek":
            return spotify.seek(int(params.get("seconds", 10)))
        if action == "spotify_play_playlist":
            return spotify.play_playlist(target or params.get("playlist", ""))
        if action == "spotify_play_nth":
            return spotify.play_nth(int(params.get("n", 1)),
                                    params.get("playlist") or (target or None))
        if action == "spotify_search_play":
            return spotify.search_play(target or params.get("query", ""))
        if action == "spotify_current":
            return spotify.current_track()
        if action == "spotify_volume":
            return spotify.set_volume(int(params.get("level", 50)))
        if action == "spotify_like":
            return spotify.like_current()

    # ── NEW YOUTUBE CONTROLS ─────────────────────────────────────
    if action == "youtube_play":
        from control.browser import youtube_play
        return youtube_play()
    if action == "youtube_pause":
        from control.browser import youtube_pause
        return youtube_pause()
    if action == "youtube_seek":
        from control.browser import youtube_seek
        return youtube_seek(int(params.get("seconds", 10)))
    if action == "youtube_set_quality":
        from control.browser import youtube_set_quality
        return youtube_set_quality(params.get("quality", "720p"))
    if action == "youtube_like":
        from control.browser import youtube_like
        return youtube_like()
    if action == "youtube_dislike":
        from control.browser import youtube_dislike
        return youtube_dislike()
    if action == "youtube_share":
        from control.browser import youtube_share
        return youtube_share()
    if action == "youtube_comment":
        from control.browser import youtube_comment
        return youtube_comment(params.get("comment", ""))
    if action == "youtube_subscribe":
        from control.browser import youtube_subscribe
        return youtube_subscribe()

    if action == "stop":
        return "__INTERRUPT__"
    if action == "quit":
        return "__QUIT__"
    return "Sorry, I didn't understand that command"


# ── Undo history (Section 5.3) ────────────────────────────────

_undo_stack: list[dict] = []


def _push_undo(intent: dict) -> None:
    """Record an action for potential undo."""
    _undo_stack.append(intent)
    if len(_undo_stack) > 20:
        _undo_stack.pop(0)


def _undo_last() -> str:
    """Reverse the last action taken (Section 5.3: 'Undo that')."""
    if not _undo_stack:
        return "There's nothing to undo"
    intent = _undo_stack.pop()
    action = intent.get("action", "")
    target = intent.get("target", "")

    # Reversible actions
    if action == "volume_change":
        from system.os_control import change_volume
        amount = -int(intent.get("parameters", {}).get("amount", 10))
        return change_volume(amount)
    if action == "volume_set":
        from system.os_control import get_volume, set_volume
        return set_volume(get_volume())  # no-op, but confirm
    if action == "brightness_change":
        from system.os_control import change_brightness
        amount = -int(intent.get("parameters", {}).get("amount", 10))
        return change_brightness(amount)
    if action == "create_folder":
        from files.manager import delete_path
        return delete_path(target)
    if action == "create_file":
        from files.manager import delete_path
        return delete_path(target)
    if action == "delete_path":
        return "I can't restore deleted files automatically — check the jarvis trash folder"
    if action == "rename_file":
        from files.manager import rename_file
        new_name = intent.get("parameters", {}).get("new_name", "")
        return rename_file(new_name, target)  # swap back
    if action == "move_file":
        from files.manager import move_file
        params = intent.get("parameters", {})
        return move_file(target, params.get("dest_dir", "Documents"),
                         params.get("source_dir", "Downloads"))
    if action == "copy_file":
        from files.manager import delete_path
        return delete_path(target)
    if action == "task_add":
        from brain.tasks import remove_task
        return remove_task(target)
    if action == "task_complete":
        return "I can't un-complete a task automatically"
    if action == "send_whatsapp":
        return "I can't unsend a WhatsApp message"
    if action == "shutdown":
        from system.os_control import cancel_shutdown
        return cancel_shutdown()
    if action == "restart":
        from system.os_control import cancel_shutdown
        return cancel_shutdown()
    if action == "wifi_on":
        from system.os_control import wifi_off
        return wifi_off()
    if action == "wifi_off":
        from system.os_control import wifi_on
        return wifi_on()
    if action == "volume_mute":
        from system.os_control import toggle_mute
        return toggle_mute()
    if action == "spotify_play":
        from agents import spotify
        return spotify.pause()
    if action == "spotify_pause":
        from agents import spotify
        return spotify.play()
    if action == "media_play":
        from control.media import pause
        return pause()
    if action == "media_pause":
        from control.media import play
        return play()
    if action == "set_preference":
        return "I can't undo a preference change — tell me the new value if you want to change it back"
    return f"I can't undo that action ({action})"


def _evaluate_conditional(intent: dict) -> str | None:
    """Evaluate conditional logic (Section 3.5). Returns a response or None to proceed."""
    if not intent.get("_is_conditional"):
        return None
    condition = intent.get("_condition", "")
    if not condition:
        return None

    cmd_lower = condition.lower()
    from datetime import datetime
    now = datetime.now()

    # Delayed execution: "turn off Wi-Fi in 10 minutes" (Section 3.5)
    delay_match = re.search(r"(?:in|after) (\d+)\s*(minute|min|second|sec|hour|hr)", cmd_lower)
    if delay_match:
        qty = int(delay_match.group(1))
        unit = delay_match.group(2)
        unit_map = {"minute": 60, "min": 60, "second": 1, "sec": 1, "hour": 3600, "hr": 3600}
        delay_seconds = qty * unit_map.get(unit, 60)
        # Schedule the action on a background thread
        action_text = intent.get("action", "")
        target_text = intent.get("target", "")
        params_copy = dict(intent.get("parameters", {}) or {})
        scheduled_intent = {"action": action_text, "target": target_text, "parameters": params_copy}

        def _run_scheduled():
            import time as _time
            _time.sleep(delay_seconds)
            if core_state.stop_event.is_set():
                return
            try:
                result = dispatch(scheduled_intent)
                from voice.speaker import speak as _speak
                _speak(result)
            except Exception:
                pass

        threading.Thread(target=_run_scheduled, daemon=True).start()
        return f"Done — I'll {action_text.replace('_', ' ')} in {qty} {unit}"

    # State-based conditions: "if Spotify is open" / "unless Chrome is running"
    if re.search(r"if .+ is (open|running|active|available)", cmd_lower):
        # The condition is met only if the app is running; if not, inform user
        from agents import spotify as _sp_check
        from control import apps as _apps_check
        app_match = re.search(r"if\s+(.+?)\s+is\s+(open|running)", cmd_lower)
        if app_match:
            app_name = app_match.group(1).strip()
            # Check if the app is running
            import psutil as _psutil
            running = any(
                app_name.replace(" ", "") in (p.info["name"] or "").lower().replace(" ", "").replace(".exe", "")
                for p in _psutil.process_iter(["name"])
            )
            if not running:
                return f"{app_name} isn't running -- skipping that step"
        return None  # condition met; proceed

    # Time-of-day conditions: "if it's past 6 PM"
    m = re.search(r"(?:past|after|before) (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", cmd_lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm and ampm.lower() == "pm" and hour < 12:
            hour += 12
        if ampm and ampm.lower() == "am" and hour == 12:
            hour = 0
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if "before" in cmd_lower:
            if now >= target_time:
                return "It's already past that time — skipping"
            return None  # condition not yet met; skip action
        else:  # past/after
            if now < target_time:
                return f"It's not {hour}:{minute:02d} yet — I'll hold off"
            return None  # condition met; proceed with action
    return None


def _apply_correction(intent: dict, command: str) -> dict:
    """Apply self-correction (Section 5.3) by modifying the intent."""
    if not intent.get("_is_correction"):
        return intent

    cmd_lower = command.lower()
    last = memory.last_intent()
    if not last:
        return intent

    # "make that 1080p" → update the last action's parameters
    if "make that" in cmd_lower or "actually" in cmd_lower:
        # Try to extract the new value
        m = re.search(r"(?:make that|actually)[, ]*(.+?)$", command, re.IGNORECASE)
        if m:
            new_val = m.group(1).strip()
            # If last action was volume/brightness set, update the level
            if last.get("action") in ("volume_set", "brightness_set"):
                m2 = re.search(r"(\d+)", new_val)
                if m2:
                    intent["action"] = last["action"]
                    intent["parameters"] = {"level": int(m2.group(1))}
                    return intent
            # If last action was a search, update the query
            if last.get("action") in ("web_search", "youtube_search", "spotify_search_play"):
                intent["action"] = last["action"]
                intent["target"] = new_val
                return intent

    # "send it to Priya, not Rohan" → redirect the last action
    if "not " in cmd_lower and last.get("action") in ("send_whatsapp", "send_sms", "make_call"):
        m = re.search(r"(?:not|instead of)\s+(\w+)", command, re.IGNORECASE)
        if m:
            intent["action"] = last["action"]
            intent["target"] = m.group(1)
            intent["parameters"] = last.get("parameters", {})
            return intent

    return intent


def _translate_response(response: str, lang: str) -> str:
    """Translate the response back to the user's language (Section 8)."""
    if not lang or lang in ("English", "Hinglish"):
        return response
    # Map language name to deep-translator / Google Translate language code
    _LANG_CODE = {
        "Hindi": "hi", "Spanish": "es", "French": "fr",
        "German": "de", "Chinese": "zh", "Japanese": "ja",
        "Russian": "ru", "Arabic": "ar", "Portuguese": "pt",
    }
    target_code = _LANG_CODE.get(lang, "en")
    try:
        from brain.nlp import translate_text
        return translate_text(response, target_code)
    except Exception:
        return response


def _tone_adapt(response: str, command: str) -> str:
    """Adapt tone based on user input (Section 6.2)."""
    cmd_lower = command.lower()

    # Frustrated user → calm, solution-focused, retry immediately
    frustrated = any(w in cmd_lower for w in (
        "not working", "nothing is happening", "why isn't", "this is broken",
        "ugh", "damn", "wtf", "stupid", "idiot", "useless",
    ))
    if frustrated:
        if response and not response.startswith("Got it"):
            return f"Got it — let me try that a different way. {response}"
        return response

    # Emotional / tired user → empathetic acknowledgment
    if any(w in cmd_lower for w in ("exhausted", "tired", "so much", "overwhelmed")):
        if not response.startswith("I hear you"):
            return f"I hear you. {response}"
        return response

    # Casual user → keep response casual
    if any(w in cmd_lower for w in ("yo", "hey", "sup", "bro", "dude", "man", "pls")):
        return response
    return response


def _proactive_followup(intent: dict, response: str) -> str:
    """Offer a proactive follow-up when contextually appropriate (Section 6.1)."""
    action = intent.get("action", "")
    if action in ("screenshot", "screenshot_or_note"):
        return f"{response} Want me to send it to anyone?"
    if action in ("research", "save_research"):
        return f"{response} Want me to open it?"
    if action == "task_add":
        return f"{response} Anything else to add?"
    if action == "open_app":
        return f"{response} Need me to do anything with it?"
    if action in ("web_search", "youtube_search", "browse_url"):
        return f"{response} Want me to read the page or click something?"
    if action in ("send_whatsapp", "send_sms", "make_call"):
        return f"{response} Anything else I can help with?"
    return response


def execute(command: str) -> str:
    """Parse (possibly compound) command, run each step, return combined response."""
    core_state.set_state(State.THINKING)
    intents = interpreter.parse_compound(command)
    responses = []
    detected_lang = "English"
    for intent in intents:
        if core_state.stop_event.is_set():
            break  # user said stop mid-compound — abandon remaining steps

        # Capture detected language for response translation
        if intent.get("_detected_language"):
            detected_lang = intent["_detected_language"]

        # Clarification handling (Section 5.1-5.2)
        if intent.get("_requires_clarification"):
            question = intent.get("_clarification_question") or "What did you want me to do?"
            question = _translate_response(question, detected_lang)
            responses.append(question)
            continue

        # Self-correction handling (Section 5.3)
        intent = _apply_correction(intent, command)

        # Undo handling (Section 5.3)
        if intent.get("action") == "undo":
            result = _undo_last()
            result = _translate_response(result, detected_lang)
            responses.append(result)
            continue

        # Conditional evaluation (Section 3.5)
        cond_result = _evaluate_conditional(intent)
        if cond_result:
            cond_result = _translate_response(cond_result, detected_lang)
            responses.append(cond_result)
            continue

        # Confirmation gating (Section 3.5): "only after I confirm"
        if intent.get("_requires_confirmation"):
            action_desc = intent.get("action", "").replace("_", " ")
            target_desc = intent.get("target", "")
            msg = f"Should I {action_desc} {target_desc}? Just say yes to confirm."
            responses.append(_translate_response(msg, detected_lang))
            continue

        # Hold preference (Section 3.5): "keep the volume at 50 unless I say otherwise"
        hold_pref = intent.get("_hold_preference")
        if hold_pref:
            from brain.memory import memory as _mem
            _mem.store_preference(hold_pref["key"], hold_pref["value"])
            responses.append(_translate_response(
                f"Got it — I'll keep that at {hold_pref['value']} unless you say otherwise.",
                detected_lang))
            continue

        try:
            result = dispatch(intent)
        except Exception as e:
            traceback.print_exc()
            result = f"I couldn't do that -- {e.__class__.__name__}"

        # Error communication (Section 6.4): explain and propose next step
        if "failed" in result.lower() or "couldn" in result.lower():
            result = f"{result} Want me to try a different approach?"

        if result in ("__INTERRUPT__", "__QUIT__"):
            core_state.set_state(State.IDLE)
            return result

        # Record for undo (only reversible actions)
        if intent.get("action") not in ("stop", "quit", "unknown", "undo"):
            _push_undo(intent)

        # Proactive follow-up (Section 6.1)
        result = _proactive_followup(intent, result)

        # Tone adaptation (Section 6.2)
        result = _tone_adapt(result, command)

        responses.append(result)

        # Process chained steps (Section 3.4)
        if intent.get("_is_chained") and intent.get("_chain_steps"):
            for step in intent["_chain_steps"]:
                if core_state.stop_event.is_set():
                    break
                step_intent = {
                    "action": step.get("action", "unknown"),
                    "target": step.get("target") or "",
                    "parameters": step.get("parameters", {}),
                }
                try:
                    step_result = dispatch(step_intent)
                except Exception as e:
                    traceback.print_exc()
                    step_result = f"That step failed: {e.__class__.__name__}"
                if step_result in ("__INTERRUPT__", "__QUIT__"):
                    core_state.set_state(State.IDLE)
                    return step_result
                if step_intent.get("action") not in ("stop", "quit", "unknown"):
                    _push_undo(step_intent)
                step_result = _proactive_followup(step_intent, step_result)
                step_result = _tone_adapt(step_result, command)
                responses.append(step_result)
                # Section 3.4: if a chained step fails, report it and ask
                # whether to continue with the remaining steps or stop.
                if "failed" in step_result.lower() or "couldn" in step_result.lower():
                    remaining = len(intent["_chain_steps"]) - (intent["_chain_steps"].index(step) + 1)
                    if remaining > 0:
                        responses.append(
                            f"{step_result} Want me to continue with the remaining {remaining} steps, or stop here?"
                        )
                        break

    # Language preference: remember the user's dominant language (Section 8.3)
    if detected_lang not in ("English", "Hinglish"):
        memory.store_preference("language_preference", detected_lang)

    core_state.set_state(State.IDLE)
    final_response = ". ".join(r for r in responses if r)
    # Translate the final response to the user's language (Section 8.1)
    final_response = _translate_response(final_response, detected_lang)
    return final_response


# ── Threads ────────────────────────────────────────────────

def _worker_loop() -> None:
    """Drain the command queue; single consumer keeps execution serialized."""
    while True:
        command = core_state.command_queue.get()
        if command is None:
            break
        core_state.stop_event.clear()  # fresh command resets any prior stop
        try:
            response = execute(command)
        except Exception:
            traceback.print_exc()
            response = "Something went wrong."
        if response == "__QUIT__":
            speak("Goodbye.")
            os._exit(0)
        if response == "__INTERRUPT__" or core_state.stop_event.is_set():
            continue  # interrupted — stay silent, await next command
        # Speak on a side thread so barge-in listening can overlap.
        barge = threading.Thread(target=_barge_watch, daemon=True)
        speak_thread = threading.Thread(target=speak, args=(response,), daemon=True)
        speak_thread.start()
        barge.start()
        speak_thread.join()


def _barge_watch() -> None:
    """Listen for a spoken 'stop' while JARVIS talks."""
    import time
    time.sleep(0.3)  # let speak() flip state to SPEAKING first
    if core_state.get_state() == State.SPEAKING:
        from voice import listener
        listener.listen_for_stop()


def _voice_loop() -> None:
    from voice import listener
    while True:
        try:
            core_state.set_state(State.IDLE)
            command, conf = listener.listen_for_command(
                on_wake=lambda: core_state.set_state(State.LISTENING))
            if not command:
                continue
            print(f"[main] heard: {command!r} (conf {conf:.2f})")
            if core_state.is_stop_command(command):
                core_state.request_stop()
                continue
            if conf < settings.STT_CONFIDENCE_THRESHOLD:
                threading.Thread(target=speak, daemon=True,
                                 args=("Sorry, I didn't catch that. Please repeat.",)).start()
                continue
            core_state.push_chat("user", command)
            core_state.command_queue.put(command)
        except Exception:
            traceback.print_exc()


# ── Entry modes ──────────────────────────────────────────────

def ui_mode() -> None:
    """Dashboard window + voice + worker threads."""
    from dashboard import ui, info

    def on_ready(_window):
        info.start()
        threading.Thread(target=_worker_loop, daemon=True, name="worker").start()
        threading.Thread(target=_voice_loop, daemon=True, name="voice").start()
        threading.Thread(target=speak, daemon=True,
                         args=("JARVIS online. All systems operational.",)).start()

    ui.run(on_ready)  # blocks until the window closes
    os._exit(0)


def voice_mode() -> None:
    """Headless: voice + worker only."""
    threading.Thread(target=_worker_loop, daemon=True, name="worker").start()
    speak("JARVIS online. All systems operational.")
    _voice_loop()


def text_mode() -> None:
    speak("JARVIS online. Text mode. Type commands, or exit to quit.")
    while True:
        try:
            command = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not command:
            continue
        if command.lower() in ("exit", "quit"):
            break
        core_state.stop_event.clear()
        response = execute(command)
        if response == "__QUIT__":
            break
        if response == "__INTERRUPT__":
            continue
        speak(response)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--once":
        cmd = " ".join(args[1:])
        result = execute(cmd)
        print(f"RESULT: {result}")
    elif args and args[0] == "--text":
        text_mode()
    elif args and args[0] == "--voice":
        voice_mode()
    else:
        ui_mode()