"""
Qwen3-VL Vision Engine for ULTRON AI
Implements screen vision capabilities using Qwen3-VL via Ollama
"""

import requests
import base64
import json
from io import BytesIO
from PIL import Image
import mss
import pyautogui
import time
import logging
from typing import Optional, Tuple, Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants from specification
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
VISION_MODEL = "qwen3-vl:4b"
SCREENSHOT_TIMEOUT = 30  # seconds
MAX_SCREENSHOT_SIZE = (1920, 1080)  # max width, height for resizing

# Mock mode for testing when Ollama is not available
# Accessed via package import to ensure we get the package-level variable
def _get_mock_mode():
    from . import MOCK_MODE
    return MOCK_MODE


class VisionError(Exception):
    """Base exception for vision-related errors"""
    pass


class ElementNotFoundError(VisionError):
    """Raised when an element is not found on screen"""
    pass


class VisionEngine:
    """Main vision engine class handling Qwen3-VL interactions"""

    def __init__(self):
        """Initialize the vision engine"""
        self.screen_width, self.screen_height = pyautogui.size()
        logger.info(f"Vision engine initialized for screen size: {self.screen_width}x{self.screen_height}")

        # Enable PyAutoGUI failsafe and set pause
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    def capture_screen(self, region: Optional[Dict[str, int]] = None) -> str:
        """
        Capture screen or region and return base64 PNG string.

        Args:
            region: Optional dict {"top": y, "left": x, "width": w, "height": h}
                   for targeted region capture instead of full screen

        Returns:
            Base64 encoded PNG screenshot string
        """
        try:
            with mss.mss() as sct:
                if region:
                    target = region
                else:
                    target = sct.monitors[1]  # primary monitor

                screenshot = sct.grab(target)
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

                # Resize if too large for fast processing
                max_w, max_h = MAX_SCREENSHOT_SIZE
                if img.width > max_w or img.height > max_h:
                    img.thumbnail((max_w, max_h), Image.LANCZOS)

                buffer = BytesIO()
                img.save(buffer, format="PNG")
                return base64.b64encode(buffer.getvalue()).decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            raise VisionError(f"Screen capture failed: {e}")

    def call_qwen3_vl(self, prompt: str, screenshot_base64: Optional[str] = None,
                       region: Optional[Dict[str, int]] = None) -> str:
        """
        Send a vision query to Qwen3-VL running locally via Ollama.

        Args:
            prompt: The vision instruction prompt
            screenshot_base64: Base64 encoded PNG screenshot string
                               If None, a fresh screenshot is taken
            region: Optional dict for targeted region capture

        Returns:
            Qwen3-VL's response as a plain string
        """
        if _get_mock_mode():
            # Return mock responses for testing
            logger.debug(f"[MOCK] Vision request: {prompt[:100]}...")
            if "Find the" in prompt and "coordinates" in prompt:
                # Mock element location response
                return "FOUND: x=100 y=100"
            elif "Read the following" in prompt:
                # Mock text reading response
                return "Mock text content"
            elif "state of" in prompt:
                # Mock state checking response
                return "ENABLED"
            elif "succeed" in prompt.lower():
                # Mock action verification
                return "SUCCESS: YES"
            elif "Analyze this screenshot" in prompt:
                # Mock screen state analysis
                return ("1. Application: Mock Application\n"
                       "2. State: Idle\n"
                       "3. Elements: Button (center), Text field (top)\n"
                       "4. Loading indicator: None\n"
                       "5. Error messages: None\n"
                       "6. Recent action: Application launched")
            elif "task:" in prompt and "plan" in prompt.lower():
                # Mock task planning response
                return ("1. ACTION TYPE: CLICK\n"
                       "   TARGET: Button at x=100 y=100\n"
                       "   PURPOSE: Click the button\n"
                       "2. ACTION TYPE: TYPE\n"
                       "   TARGET: Hello World\n"
                       "   PURPOSE: Enter text")
            elif "VISIBLE:" in prompt or "SCROLL:" in prompt:
                # Mock scroll position analysis
                return "VISIBLE: x=150 y=150"
            elif "SCROLL_NEEDED:" in prompt or "FOUND:" in prompt:
                # Mock dropdown/menu navigation
                return "FOUND: x=200 y=200"
            else:
                # Default mock response
                return "Mock vision response"

        # Capture fresh screenshot if none provided
        if screenshot_base64 is None:
            screenshot_base64 = self.capture_screen(region)

        payload = {
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [screenshot_base64],
            "stream": False,
            "options": {
                "temperature": 0.1,   # low temp for precise, consistent responses
                "top_p": 0.9,
                "num_predict": 512    # enough for detailed analysis
            }
        }

        try:
            logger.debug(f"Sending vision request to Qwen3-VL: {prompt[:100]}...")
            response = requests.post(
                OLLAMA_ENDPOINT,
                json=payload,
                timeout=SCREENSHOT_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()
            vision_response = result.get("response", "").strip()
            logger.debug(f"Qwen3-VL response: {vision_response[:200]}...")
            return vision_response

        except requests.exceptions.ConnectionError:
            error_msg = ("Qwen3-VL is not running. Start Ollama and ensure "
                        "qwen3-vl:4b is pulled and available.")
            logger.error(error_msg)
            raise VisionError(error_msg)
        except requests.exceptions.Timeout:
            error_msg = ("Qwen3-VL took too long to respond. "
                        "The model may be overloaded or the image too large.")
            logger.error(error_msg)
            raise VisionError(error_msg)
        except Exception as e:
            error_msg = f"Vision engine error: {str(e)}"
            logger.error(error_msg)
            raise VisionError(error_msg)

    def find_element(self, element_description: str,
                      region: Optional[Dict[str, int]] = None) -> Tuple[int, int]:
        """
        Find a UI element on screen using Qwen3-VL.
        Returns (x, y) coordinates or raises ElementNotFoundError.

        Args:
            element_description: Description of the element to find
            region: Optional region to search in

        Returns:
            Tuple of (x, y) coordinates

        Raises:
            ElementNotFoundError: If element is not found
        """
        prompt = (
            f"Look at this screenshot carefully.\n"
            f"Find the {element_description} on the screen.\n"
            f"Tell me its exact location as pixel coordinates (x, y) "
            f"at the center of the element.\n"
            f"The screen resolution is {self.screen_width}x{self.screen_height}.\n"
            f"If the element is not visible, say NOT_FOUND.\n"
            f"Respond in this exact format only:\n"
            f"FOUND: x=[X_VALUE] y=[Y_VALUE]\n"
            f"or\n"
            f"NOT_FOUND"
        )

        response = self.call_qwen3_vl(prompt, region=region)

        if response.startswith("FOUND:"):
            # Parse coordinates from "FOUND: x=123 y=456"
            parts = response.replace("FOUND:", "").strip().split()
            x = int(parts[0].split("=")[1])
            y = int(parts[1].split("=")[1])

            # Validate coordinates are within screen bounds
            if not (0 <= x <= self.screen_width and 0 <= y <= self.screen_height):
                raise VisionError(f"Invalid coordinates returned: ({x}, {y})")

            logger.info(f"Found element '{element_description}' at ({x}, {y})")
            return (x, y)
        else:
            logger.warning(f"Element not found: {element_description}")
            raise ElementNotFoundError(f"Element not found: {element_description}")

    def verify_action(self, action_description: str,
                       expected_result: str) -> Tuple[bool, str]:
        """
        Verify that a performed action succeeded.
        Returns (success: bool, reason: str)

        Args:
            action_description: Description of the action that was performed
            expected_result: What should have happened as a result

        Returns:
            Tuple of (success, reason)
        """
        prompt = (
            f"I just performed this action: {action_description}\n"
            f"The expected result was: {expected_result}\n"
            f"Look at this screenshot and tell me:\n"
            f"Did the action succeed? Answer YES or NO.\n"
            f"If NO, describe what you see instead.\n"
            f"Format:\n"
            f"SUCCESS: YES\n"
            f"or\n"
            f"SUCCESS: NO\n"
            f"REASON: [what is on screen instead]"
        )

        response = self.call_qwen3_vl(prompt)

        if "SUCCESS: YES" in response:
            logger.info(f"Action verified successfully: {action_description}")
            return (True, "")
        else:
            reason = ""
            if "REASON:" in response:
                reason = response.split("REASON:")[1].strip()
            logger.warning(f"Action verification failed: {action_description}. Reason: {reason}")
            return (False, reason)

    def read_screen_text(self, what_to_read: str) -> str:
        """
        Read specific text from the current screen.

        Args:
            what_to_read: Description of what text to read

        Returns:
            The text read from screen
        """
        prompt = (
            f"Read the following from this screenshot:\n"
            f"{what_to_read}\n"
            f"Return only the exact text you can read. "
            f"No explanation."
        )
        return self.call_qwen3_vl(prompt)

    def check_element_state(self, element_description: str,
                              possible_states: List[str]) -> str:
        """
        Check the current state of a UI element.

        Args:
            element_description: Description of the element to check
            possible_states: List of possible state strings

        Returns:
            The current state of the element
        """
        states_str = " or ".join(possible_states)
        prompt = (
            f"Look at this screenshot and tell me the state of: "
            f"{element_description}\n"
            f"Possible states: {states_str}\n"
            f"Respond with only the state. Nothing else."
        )
        return self.call_qwen3_vl(prompt).strip().upper()

    def analyze_screen_state(self) -> Dict[str, Any]:
        """
        Analyze the current state of the screen.

        Returns:
            Dictionary containing screen analysis information
        """
        prompt = (
            "Analyze this screenshot and answer the following questions:\n"
            "1. What application or website is currently in focus?\n"
            "2. What is the current state of the screen?\n"
            "   (e.g., home page, search results, video playing, settings open)\n"
            "3. What are the main interactive elements visible?\n"
            "   List them with their approximate locations.\n"
            "4. Is there any loading indicator, spinner, or progress bar visible?\n"
            "5. Is there any error message, dialog box, or popup visible?\n"
            "   If yes, what does it say?\n"
            "6. What was the most recent action likely to have done to the screen?\n"
            "Answer each question clearly and concisely."
        )

        response = self.call_qwen3_vl(prompt)
        # Parse response into structured format
        lines = response.split('\n')
        analysis = {}
        current_question = None
        current_answer = []

        for line in lines:
            if line.strip().startswith(tuple(f"{i}." for i in range(1, 7))):
                if current_question is not None:
                    analysis[current_question] = '\n'.join(current_answer).strip()
                current_question = line.strip()
                current_answer = [line.split('.', 1)[1].strip()] if '.' in line else ['']
            elif current_question is not None and line.strip():
                current_answer.append(line.strip())

        if current_question is not None:
            analysis[current_question] = '\n'.join(current_answer).strip()

        return analysis

    def plan_task(self, task_description: str) -> List[Dict[str, Any]]:
        """
        Use Qwen3-VL to plan a sequence of actions for a task.

        Args:
            task_description: Description of the task to plan

        Returns:
            List of action steps
        """
        prompt = (
            f"Look at this screenshot carefully.\n"
            f"I need to complete this task: {task_description}\n"
            f"The screen resolution is {self.screen_width}x{self.screen_height}.\n\n"
            f"Analyze what you see and create a step-by-step plan to complete\n"
            f"this task using only mouse clicks, keyboard input, and scroll actions.\n\n"
            f"For each step, specify:\n"
            f"- ACTION TYPE: CLICK / TYPE / SCROLL / HOTKEY / WAIT / SCREENSHOT\n"
            f"- TARGET: the element to interact with and its pixel coordinates (x, y)\n"
            f"  OR the text to type OR the key combination to press\n"
            f"- PURPOSE: why this step is needed\n\n"
            f"Return your plan as a numbered list. Be precise with coordinates.\n"
            f"Only include steps that are achievable from the current screen state.\n"
            f"If the task cannot be started from what is currently on screen,\n"
            f"say CANNOT_START and explain what needs to happen first."
        )

        response = self.call_qwen3_vl(prompt)

        # Parse the response into structured steps
        steps = []
        lines = response.split('\n')
        current_step = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a new step (starts with a number)
            if line[0].isdigit() and '. ' in line:
                if current_step:
                    steps.append(current_step)
                # Start new step
                step_content = line.split('. ', 1)[1]
                current_step = {"raw": step_content}

                # Parse action type
                if "ACTION TYPE:" in step_content:
                    action_part = step_content.split("ACTION TYPE:", 1)[1]
                    action_type = action_part.split('\n')[0].strip()
                    current_step["action_type"] = action_type

                # Parse target
                if "TARGET:" in step_content:
                    target_part = step_content.split("TARGET:", 1)[1]
                    target_lines = target_part.split('\n')
                    target = target_lines[0].strip()
                    current_step["target"] = target

                    # Try to extract coordinates if present
                    import re
                    coord_match = re.search(r'\((\d+),\s*(\d+)\)', target)
                    if coord_match:
                        current_step["coordinates"] = (int(coord_match.group(1)), int(coord_match.group(2)))

                # Parse purpose
                if "PURPOSE:" in step_content:
                    purpose_part = step_content.split("PURPOSE:", 1)[1]
                    purpose_lines = purpose_part.split('\n')
                    current_step["purpose"] = purpose_lines[0].strip()
            elif current_step and line:
                # Continuation of current step
                if "raw" in current_step:
                    current_step["raw"] += " " + line
                else:
                    current_step["raw"] = line

        # Don't forget the last step
        if current_step:
            steps.append(current_step)

        return steps

    def scroll_position_analysis(self, element_or_content_description: str) -> Dict[str, Any]:
        """
        Determine if content is above or below current view.

        Args:
            element_or_content_description: What to look for

        Returns:
            Dictionary with analysis results
        """
        prompt = (
            f"Look at this screenshot.\n"
            f"I am looking for: {element_or_content_description}\n"
            f"Is it visible on screen right now?\n"
            f"If yes: give me its pixel coordinates (x, y).\n"
            f"If no: tell me which direction I need to scroll to find it.\n"
            f"Format:\n"
            f"VISIBLE: x=[X] y=[Y]\n"
            f"or\n"
            f"SCROLL: [UP/DOWN/LEFT/RIGHT]\n"
            f"or\n"
            f"NOT_ON_PAGE"
        )

        response = self.call_qwen3_vl(prompt)

        result = {}
        if response.startswith("VISIBLE:"):
            coords_part = response.replace("VISIBLE:", "").strip()
            parts = coords_part.split()
            x = int(parts[0].split("=")[1])
            y = int(parts[1].split("=")[1])
            result = {"visible": True, "x": x, "y": y}
        elif response.startswith("SCROLL:"):
            direction = response.replace("SCROLL:", "").strip()
            result = {"visible": False, "scroll_direction": direction}
        elif response.startswith("NOT_ON_PAGE"):
            result = {"visible": False, "not_on_page": True}
        else:
            result = {"error": f"Unexpected response: {response}"}

        return result

    def dropdown_menu_navigation(self, option_name: str) -> Dict[str, Any]:
        """
        Find a specific item within an open dropdown/menu.

        Args:
            option_name: Name of the option to find

        Returns:
            Dictionary with search results
        """
        prompt = (
            f"A [dropdown/menu/context menu] is open on screen.\n"
            f"I need to click on the option: {option_name}\n"
            f"Look at the screenshot and find this option.\n"
            f"Give me its exact pixel coordinates (x, y).\n"
            f"If the option is not visible in the current menu, say SCROLL_NEEDED\n"
            f"and specify which direction to scroll.\n"
            f"Format:\n"
            f"FOUND: x=[X] y=[Y]\n"
            f"or\n"
            f"SCROLL_NEEDED: [UP/DOWN]\n"
            f"or\n"
            f"NOT_FOUND"
        )

        response = self.call_qwen3_vl(prompt)

        result = {}
        if response.startswith("FOUND:"):
            coords_part = response.replace("FOUND:", "").strip()
            parts = coords_part.split()
            x = int(parts[0].split("=")[1])
            y = int(parts[1].split("=")[1])
            result = {"found": True, "x": x, "y": y}
        elif response.startswith("SCROLL_NEEDED:"):
            direction = response.replace("SCROLL_NEEDED:", "").strip()
            result = {"scroll_needed": True, "direction": direction}
        elif response.startswith("NOT_FOUND"):
            result = {"found": False}
        else:
            result = {"error": f"Unexpected response: {response}"}

        return result


# Mouse control functions
def click_element(x: int, y: int) -> None:
    """
    Perform a single left click at the specified coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    try:
        pyautogui.moveTo(x, y, duration=0.3)  # smooth human-like move
        time.sleep(0.1)                         # brief pause before click
        pyautogui.click(x, y)
        time.sleep(0.5)                         # wait for UI response
        logger.debug(f"Clicked at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to click at ({x}, {y}): {e}")
        raise

def double_click_element(x: int, y: int) -> None:
    """
    Perform a double click at the specified coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    try:
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.1)
        pyautogui.doubleClick(x, y)
        time.sleep(0.5)
        logger.debug(f"Double clicked at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to double click at ({x}, {y}): {e}")
        raise

def right_click_element(x: int, y: int) -> None:
    """
    Perform a right click at the specified coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    try:
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.1)
        pyautogui.rightClick(x, y)
        time.sleep(0.3)
        logger.debug(f"Right clicked at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to right click at ({x}, {y}): {e}")
        raise

def drag_element(start_x: int, start_y: int, end_x: int, end_y: int) -> None:
    """
    Click and drag from start coordinates to end coordinates.

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        end_x: Ending X coordinate
        end_y: Ending Y coordinate
    """
    try:
        pyautogui.moveTo(start_x, start_y, duration=0.3)
        time.sleep(0.1)
        pyautogui.dragTo(end_x, end_y, duration=0.5, button="left")
        time.sleep(0.3)
        logger.debug(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
    except Exception as e:
        logger.error(f"Failed to drag from ({start_x}, {start_y}) to ({end_x}, {end_y}): {e}")
        raise

def scroll_at(x: int, y: int, direction: str, amount: int = 3) -> None:
    """
    Scroll at the specified coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        direction: Direction to scroll (UP, DOWN, LEFT, RIGHT)
        amount: Amount to scroll (default 3)
    """
    try:
        pyautogui.moveTo(x, y, duration=0.2)
        if direction == "UP":
            pyautogui.scroll(amount)
        elif direction == "DOWN":
            pyautogui.scroll(-amount)
        elif direction == "LEFT":
            pyautogui.hscroll(-amount)
        elif direction == "RIGHT":
            pyautogui.hscroll(amount)
        time.sleep(0.3)
        logger.debug(f"Scrolled {direction} by {amount} at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to scroll at ({x}, {y}): {e}")
        raise

def hover_element(x: int, y: int) -> None:
    """
    Hover mouse over the specified coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    try:
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.8)
        logger.debug(f"Hovered at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to hover at ({x}, {y}): {e}")
        raise


# Keyboard control functions
def type_text(text: str, interval: float = 0.05) -> None:
    """
    Type text with human-like interval between keystrokes.

    Args:
        text: Text to type
        interval: Interval between keystrokes in seconds
    """
    try:
        pyautogui.typewrite(text, interval=interval)
        time.sleep(0.2)
        logger.debug(f"Typed text: {text[:50]}{'...' if len(text) > 50 else ''}")
    except Exception as e:
        logger.error(f"Failed to type text: {e}")
        raise

def type_text_unicode(text: str) -> None:
    """
    Type Unicode/Hinglish text using clipboard method.

    Args:
        text: Text to type (supports Unicode)
    """
    try:
        import pyperclip
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        logger.debug(f"Typed Unicode text via clipboard: {text[:50]}{'...' if len(text) > 50 else ''}")
    except Exception as e:
        logger.error(f"Failed to type Unicode text: {e}")
        raise

def press_key(key: str) -> None:
    """
    Press a single key.

    Args:
        key: Key to press (e.g., 'enter', 'tab', 'escape')
    """
    try:
        pyautogui.press(key)
        time.sleep(0.2)
        logger.debug(f"Pressed key: {key}")
    except Exception as e:
        logger.error(f"Failed to press key '{key}': {e}")
        raise

def press_hotkey(*keys: str) -> None:
    """
    Press a hotkey combination.

    Args:
        *keys: Keys to press together (e.g., "ctrl", "s")
    """
    try:
        pyautogui.hotkey(*keys)
        time.sleep(0.3)
        logger.debug(f"Pressed hotkey: {'+'.join(keys)}")
    except Exception as e:
        logger.error(f"Failed to press hotkey {'+'.join(keys)}: {e}")
        raise

def shift_click(x: int, y: int) -> None:
    """
    Shift-click for multi-select.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    try:
        pyautogui.keyDown("shift")
        pyautogui.click(x, y)
        pyautogui.keyUp("shift")
        time.sleep(0.2)
        logger.debug(f"Shift-clicked at ({x}, {y})")
    except Exception as e:
        logger.error(f"Failed to shift-click at ({x}, {y}): {e}")
        raise

def clear_and_type(x: int, y: int, text: str) -> None:
    """
    Clear input field and type new text.

    Args:
        x: X coordinate of input field
        y: Y coordinate of input field
        text: Text to type
    """
    try:
        click_element(x, y)
        time.sleep(0.1)
        press_hotkey("ctrl", "a")    # select all existing content
        time.sleep(0.1)
        press_key("backspace")        # delete it
        time.sleep(0.1)
        type_text_unicode(text)       # type new content
        logger.debug(f"Cleared and typed at ({x}, {y}): {text[:50]}{'...' if len(text) > 50 else ''}")
    except Exception as e:
        logger.error(f"Failed to clear and type at ({x}, {y}): {e}")
        raise


# Initialize vision engine instance
vision_engine = VisionEngine()

# Export main functions for easy access
def find_element(element_description: str, region: Optional[Dict[str, int]] = None) -> Tuple[int, int]:
    """Find element on screen"""
    return vision_engine.find_element(element_description, region)

def verify_action(action_description: str, expected_result: str) -> Tuple[bool, str]:
    """Verify action success"""
    return vision_engine.verify_action(action_description, expected_result)

def read_screen_text(what_to_read: str) -> str:
    """Read text from screen"""
    return vision_engine.read_screen_text(what_to_read)

def check_element_state(element_description: str, possible_states: List[str]) -> str:
    """Check element state"""
    return vision_engine.check_element_state(element_description, possible_states)

def analyze_screen_state() -> Dict[str, Any]:
    """Analyze screen state"""
    return vision_engine.analyze_screen_state()

def plan_task(task_description: str) -> List[Dict[str, Any]]:
    """Plan task using vision"""
    return vision_engine.plan_task(task_description)

def scroll_position_analysis(element_or_content_description: str) -> Dict[str, Any]:
    """Analyze scroll position"""
    return vision_engine.scroll_position_analysis(element_or_content_description)

def dropdown_menu_navigation(option_name: str) -> Dict[str, Any]:
    """Navigate dropdown/menu"""
    return vision_engine.dropdown_menu_navigation(option_name)


def check_vision_engine() -> bool:
    """
    Verify Qwen3-VL is available and responsive before use.
    Called at ULTRON AI startup.

    Returns:
        True if vision engine is working, False otherwise
    """
    logger.info(f"[DEBUG-CHECK_VISION_ENGINE] MOCK_MODE value: {_get_mock_mode()} (id: {id(_get_mock_mode())})")
    logger.info(f"[DEBUG-CHECK_VISION_ENGINE] __name__: {__name__}")
    if _get_mock_mode():
        logger.info("[ULTRON VISION] Running in MOCK mode")
        return True

    try:
        # Send a minimal test image to verify the model responds
        test_img = Image.new("RGB", (100, 100), color=(30, 30, 30))
        buffer = BytesIO()
        test_img.save(buffer, format="PNG")
        test_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        payload = {
            "model": VISION_MODEL,
            "prompt": "What color is this image? Answer in one word.",
            "images": [test_b64],
            "stream": False
        }

        response = requests.post(
            OLLAMA_ENDPOINT, json=payload, timeout=15
        )
        response.raise_for_status()

        # Vision engine is working
        logger.info("[ULTRON VISION] Qwen3-VL is online and ready.")
        return True

    except Exception as e:
        logger.warning(f"[ULTRON VISION] WARNING: Qwen3-VL unavailable: {e}")
        logger.warning("[ULTRON VISION] Screen-dependent features will not work.")
        logger.warning("[ULTRON VISION] Start Ollama and run: "
                      "ollama run qwen3-vl:4b")
        return False


if __name__ == "__main__":
    # Test the vision engine
    if check_vision_engine():
        print("Vision engine test passed!")

        # Test screenshot capture
        try:
            screenshot = vision_engine.capture_screen()
            print(f"Screenshot captured: {len(screenshot)} characters")
        except Exception as e:
            print(f"Screenshot test failed: {e}")

        # Test screen state analysis
        try:
            state = vision_engine.analyze_screen_state()
            print(f"Screen state analysis: {state}")
        except Exception as e:
            print(f"Screen state analysis failed: {e}")
    else:
        print("Vision engine test failed!")