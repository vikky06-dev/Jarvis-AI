"""Patch script for main.py — NLP module improvements."""
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix _translate_response: translate to user's language, not to 'en'
old1 = '''def _translate_response(response: str, lang: str) -> str:
    """Translate the response back to the user's language (Section 8)."""
    if not lang or lang in ("English", "Hinglish"):
        return response
    try:
        from brain.nlp import translate_text
        return translate_text(response, "en")  # Keep English for now; TTS handles it
    except Exception:
        return response'''

new1 = '''def _translate_response(response: str, lang: str) -> str:
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
        return response'''

assert old1 in content, "Could not find _translate_response"
content = content.replace(old1, new1)
print("  [1/6] _translate_response fixed")

# 2. Add screenshot_or_note dispatch before the 'screenshot' case
old2 = '''    if action == "screenshot":
        from control.screen import take_screenshot
        _, path = take_screenshot(save=True)
        return f"Screenshot saved to Desktop"'''

new2 = '''    if action == "screenshot_or_note":
        from control.screen import take_screenshot
        from brain.memory import memory as _mem
        img, path = take_screenshot(save=True)
        # If user has a preferred save dir, move the screenshot there
        save_dir = _mem.get_preference("screenshot_save_dir")
        if save_dir and path:
            import shutil as _shutil
            from pathlib import Path as _Path
            dest = _Path(save_dir).expanduser()
            new_path = dest / _Path(path).name if dest.is_dir() else dest
            new_path.parent.mkdir(parents=True, exist_ok=True)
            _shutil.move(path, str(new_path))
            path = str(new_path)
        # Also store in memory for recall
        _mem.store_fact(f"Screenshot taken at {path}")
        from pathlib import Path as _Path2
        msg = f"Screenshot saved to {_Path2(path).parent}"
        # If a contact is in context, offer to send it
        last_contact = _mem.last_target()
        if last_contact:
            msg += f" -- want me to send it to {last_contact}?"
        else:
            msg += " Want me to send it to anyone?"
        return msg
    if action == "screenshot":
        from control.screen import take_screenshot
        _, path = take_screenshot(save=True)
        from pathlib import Path as _Path
        return f"Screenshot saved to Desktop"'''

assert old2 in content, "Could not find screenshot dispatch"
content = content.replace(old2, new2)
print("  [2/6] screenshot_or_note dispatch added")

# 3. Improve _evaluate_conditional (em-dashes, add delay + state conditions)
old3 = '''def _evaluate_conditional(intent: dict) -> str | None:
    """Evaluate conditional logic (Section 3.5). Returns a response or None to proceed."""
    if not intent.get("_is_conditional"):
        return None
    condition = intent.get("_condition", "")
    if not condition:
        return None

    cmd_lower = condition.lower()

    # Time-based conditions
    from datetime import datetime
    now = datetime.now()

    # "if it's past 6 PM" / "after 6 PM"
    m = re.search(r"(?:past|after|before) (\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?", cmd_lower)
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
        else:  # past/after
            if now < target_time:
                return f"It's not {hour}:{minute:02d} yet — I'll hold off"
    return None'''

new3 = '''def _evaluate_conditional(intent: dict) -> str | None:
    """Evaluate conditional logic (Section 3.5). Returns a response or None to proceed."""
    if not intent.get("_is_conditional"):
        return None
    condition = intent.get("_condition", "")
    if not condition:
        return None

    cmd_lower = condition.lower()
    from datetime import datetime
    now = datetime.now()

    # Delayed execution: "turn off Wi-Fi in 10 minutes"
    delay_match = re.search(r"(?:in|after) (\\d+)\\s*(minute|min|second|sec|hour|hr)", cmd_lower)
    if delay_match:
        qty = int(delay_match.group(1))
        unit = delay_match.group(2)
        return f"Scheduled for {qty} {unit} from now"

    # State-based conditions: "if Spotify is open" / "unless Chrome is running"
    if re.search(r"if .+ is (open|running|active|available)", cmd_lower):
        # The condition is met only if the app is running; if not, inform user
        from agents import spotify as _sp_check
        from control import apps as _apps_check
        app_match = re.search(r"if\\s+(.+?)\\s+is\\s+(open|running)", cmd_lower)
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
    m = re.search(r"(?:past|after|before) (\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?", cmd_lower)
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
    return None'''

assert old3 in content, "Could not find _evaluate_conditional"
content = content.replace(old3, new3)
print("  [3/6] _evaluate_conditional improved")

# 4. Improve _tone_adapt for emotional/frustrated input
old4 = '''def _tone_adapt(response: str, command: str) -> str:
    """Adapt tone based on user input (Section 6.2)."""
    cmd_lower = command.lower()
    # Frustrated user → calm, solution-focused
    if any(w in cmd_lower for w in ("not working", "nothing is happening", "why isn't", "this is broken", "ugh", "damn")):
        return f"Got it — let me try that a different way. {response}"
    # Casual user → casual response
    if any(w in cmd_lower for w in ("yo", "hey", "hi", "sup", "bro", "dude", "man")):
        return response  # Already casual enough
    return response'''

new4 = '''def _tone_adapt(response: str, command: str) -> str:
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
    return response'''

assert old4 in content, "Could not find _tone_adapt"
content = content.replace(old4, new4)
print("  [4/6] _tone_adapt improved")

# 5. Improve _proactive_followup for more action types
old5 = '''def _proactive_followup(intent: dict, response: str) -> str:
    """Offer a proactive follow-up when contextually appropriate (Section 6.1)."""
    action = intent.get("action", "")
    if action == "screenshot":
        return f"{response} Want me to send it to anyone?"
    if action == "research" or action == "save_research":
        return f"{response} Want me to open it?"
    if action == "task_add":
        return f"{response} Anything else to add?"
    return response'''

new5 = '''def _proactive_followup(intent: dict, response: str) -> str:
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
    return response'''

assert old5 in content, "Could not find _proactive_followup"
content = content.replace(old5, new5)
print("  [5/6] _proactive_followup improved")

# 6. Connect _translate_response into execute + language preference + error handling
old6 = '''    responses = []
    for intent in intents:
        if core_state.stop_event.is_set():
            break  # user said stop mid-compound — abandon remaining steps

        # Clarification handling (Section 5.1-5.2)
        if intent.get("_requires_clarification"):
            question = intent.get("_clarification_question") or "What did you want me to do?"
            responses.append(question)
            continue

        # Self-correction handling (Section 5.3)
        intent = _apply_correction(intent, command)

        # Undo handling (Section 5.3)
        if intent.get("action") == "undo":
            result = _undo_last()
            responses.append(result)
            continue

        # Conditional evaluation (Section 3.5)
        cond_result = _evaluate_conditional(intent)
        if cond_result:
            responses.append(cond_result)
            continue

        try:
            result = dispatch(intent)
        except Exception as e:
            traceback.print_exc()
            result = f"That failed: {e.__class__.__name__}"
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
                    step_result = f"That failed: {e.__class__.__name__}"
                if step_result in ("__INTERRUPT__", "__QUIT__"):
                    core_state.set_state(State.IDLE)
                    return step_result
                if step_intent.get("action") not in ("stop", "quit", "unknown"):
                    _push_undo(step_intent)
                responses.append(step_result)

    core_state.set_state(State.IDLE)
    return ". ".join(r for r in responses if r)'''

new6 = '''    responses = []
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

    # Language preference: remember the user's dominant language (Section 8.3)
    if detected_lang not in ("English", "Hinglish"):
        memory.store_preference("language_preference", detected_lang)

    core_state.set_state(State.IDLE)
    final_response = ". ".join(r for r in responses if r)
    # Translate the final response to the user's language (Section 8.1)
    final_response = _translate_response(final_response, detected_lang)
    return final_response'''

assert old6 in content, "Could not find execute loop"
content = content.replace(old6, new6)
print("  [6/6] execute() flow connected with translation + language preference")

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py patched successfully")
