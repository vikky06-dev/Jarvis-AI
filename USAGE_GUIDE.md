# ULTRON AI Vision Module - Usage Guide

## Overview
The ULTRON AI Vision Module provides computer vision capabilities for interacting with desktop applications using the Qwen3-VL vision language model via Ollama. The module includes:

1. **Core Vision Engine** (`core/vision/vision.py`) - Handles screen capture, element detection, text reading, and state analysis
2. **Feature Workflows** (`core/vision/workflows/`) - Pre-built automation workflows for common applications
3. **Mock Mode** - For testing without requiring Ollama/Qwen3-VL

## Installation Requirements

### Dependencies
```bash
pip install -r requirements.txt
```

### Required Software
- **Ollama** - https://ollama.ai/
- **Qwen3-VL Model** - `ollama run qwen3-vl:4b` (or your preferred variant)
- **Python 3.10+**

## Configuration

### Mock Mode (Default for Testing)
Set in `core/vision/vision.py`:
```python
MOCK_MODE = True  # Default - uses simulated responses
```

### Real Mode (Requires Ollama & Qwen3-VL)
Set in `core/vision/vision.py`:
```python
MOCK_MODE = False  # Uses actual Ollama API
```

Ensure Ollama is running and the model is available:
```bash
ollama serve  # Start Ollama service
ollama run qwen3-vl:4b  # Pull/verify model
```

## Core Vision Functions

### Basic Operations
```python
from core.vision import (
    find_element, verify_action, read_screen_text,
    check_element_state, analyze_screen_state,
    click_element, type_text, press_key
)

# Find element coordinates
coords = find_element("Submit button")
# Returns: (x, y) tuple

# Read text from screen area
text = read_screen_text("Status bar")
# Returns: extracted text string

# Check element state
state = check_element_state("Wi-Fi toggle", ["ENABLED", "DISABLED"])
# Returns: matched state string

# Analyze overall screen state
state = analyze_screen_state()
# Returns: dict with UI components and their states

# Click element
success = click_element("OK button")

# Type text
success = type_text("Hello World", "text input field")

# Press key
success = press_key("enter")
```

### Action Verification Pipeline
```python
from core.vision import verify_action

# Perform action and verify result
result = verify_action(
    action_description="Click the login button",
    verification_prompt="Is the login form visible after clicking?",
    action_function=lambda: click_element("Login button")
)
# Returns: True if action successful and verified
```

## Feature Workflows

### YouTube Automation
```python
from core.vision.workflows import youtube_search, youtube_play, youtube_like

youtube_search("Python tutorial")
youtube_play()
youtube_like()
```

### Spotify Automation
```python
from core.vision.workflows import spotify_search, spotify_play, spotify_next_track

spotify_search("Bohemian Rhapsody")
spotify_play()
spotify_next_track()
```

### WhatsApp Automation
```python
from core.vision.workflows import whatsapp_search_contact, whatsapp_send_message

whatsapp_search_contact("John Doe")
whatsapp_send_message("Hello from ULTRON AI!")
```

### Notepad Automation
```python
from core.vision.workflows import notepad_write, notepad_save, notepad_open

notepad_write("Meeting notes from today's session")
notepad_save("meeting_notes.txt")
notepad_open("meeting_notes.txt")
```

### Web Browser Automation
```python
from core.vision.workflows import browser_navigate, browser_click, browser_scroll

browser_navigate("https://github.com")
browser_click("Sign in button")
browser_scroll(down=3)
```

### System Settings
```python
from core.vision.workflows import wifi_toggle, set_system_volume, set_brightness

wifi_toggle(False)  # Disable Wi-Fi
set_system_volume(70)  # Set volume to 70%
set_brightness(80)  # Set brightness to 80%
```

## Testing the Module

Run the test suite:
```bash
python test_vision.py
```

Run the demonstration:
```bash
python demo_vision.py
```

## Mock Mode Behavior

When `MOCK_MODE = True`:
- All functions return simulated successful responses
- Element finding returns fixed coordinates (100, 100)
- Text reading returns mock content
- Workflows simulate successful execution
- No actual screen capture or Ollama API calls are made

This allows development and testing without requiring the vision model to be running.

## Transitioning to Real Mode

To use with actual Qwen3-VL:
1. Install and start Ollama
2. Pull the Qwen3-VL model: `ollama pull qwen3-vl:4b`
3. Set `MOCK_MODE = False` in `core/vision/vision.py`
4. Ensure your screen resolution matches expectations (defaults to 1920x1200)
5. Run your automation scripts

## Troubleshooting

### Common Issues

1. **Module Import Errors**
   - Ensure you're running from the JARVIS root directory
   - Check that all `__init__.py` files exist in packages

2. **Ollama Connection Issues**
   - Verify Ollama is running: `ollama list`
   - Check model availability: `ollama run qwen3-vl:4b`
   - Ensure no firewall blocking port 11434

3. **Screen Resolution Mismatch**
   - The vision engine detects screen size automatically
   - Update default resolution in `core/vision/vision.py` if needed

4. **Element Detection Failures**
   - In mock mode: returns fixed coordinates
   - In real mode: depends on Qwen3-VL accuracy
   - Try adjusting UI element description specificity

## Extending the Module

### Adding New Workflows
1. Create a new class in `core/vision/workflows/workflows.py`
2. Inherit from BaseWorkflow or create new workflow class
3. Implement application-specific methods
4. Export convenience functions in `__init__.py`

### Custom Vision Prompts
The vision engine uses predefined prompts in `core/vision/vision.py`:
- FIND_ELEMENT_PROMPT
- READ_TEXT_PROMPT
- CHECK_ELEMENT_STATE_PROMPT
- ANALYZE_SCREEN_STATE_PROMPT
- VERIFY_ACTION_PROMPT

Modify these to improve accuracy for your specific use case.

## Security & Privacy Notes

- Screen captures are processed locally when using Ollama
- No screen data is sent to external servers (unless using remote Ollama)
- Consider application permissions when automating sensitive tasks
- Mock mode provides safe testing environment

## Example Complete Script

```python
# example_automation.py
import core.vision
from core.vision.workflows import youtube_search, spotify_search, notepad_write

# Enable mock mode for testing (set False for real usage)
core.vision.MOCK_MODE = True

def main():
    print("Starting ULTRON AI automation...")
    
    # Search for content
    youtube_result = youtube_search("AI news today")
    spotify_result = spotify_search("Focus music")
    
    # Create notes
    notes = f"""
    ULTRON AI Session Results:
    - YouTube search: {'Success' if youtube_result else 'Failed'}
    - Spotify search: {'Success' if spotify_result else 'Failed'}
    """
    notepad_write(notes)
    
    print("Automation complete!")

if __name__ == "__main__":
    main()
```

Run with: `python example_automation.py`

---

**Ready for ULTRON AI Vision Operations!**