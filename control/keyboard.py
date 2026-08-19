"""Keyboard actions: typing, hotkeys, shortcuts."""
import pyautogui


def type_text(text: str, interval: float = 0.03) -> None:
    pyautogui.typewrite(text, interval=interval)


def press(key: str) -> None:
    pyautogui.press(key)


def hotkey(combo: str) -> None:
    """combo like "ctrl+s" or "ctrl+shift+t"."""
    keys = [k.strip().lower() for k in combo.split("+")]
    pyautogui.hotkey(*keys)


def enter() -> None:
    pyautogui.press("enter")


if __name__ == "__main__":
    print("keyboard module OK (no side-effect test)")
