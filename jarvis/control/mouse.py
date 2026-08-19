"""Mouse actions via PyAutoGUI."""
import pyautogui

from config import settings

pyautogui.FAILSAFE = settings.PYAUTOGUI_FAILSAFE
pyautogui.PAUSE = 0.1


def move_to(x: int, y: int) -> None:
    pyautogui.moveTo(x, y, duration=settings.CLICK_MOVE_DURATION)


def click(x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> None:
    if x is not None and y is not None:
        move_to(x, y)
    pyautogui.click(button=button, clicks=clicks)


def double_click(x: int | None = None, y: int | None = None) -> None:
    click(x, y, clicks=2)


def right_click(x: int | None = None, y: int | None = None) -> None:
    click(x, y, button="right")


def scroll(direction: str = "down", amount: int = 5) -> None:
    """amount = wheel clicks; each click ~120 units."""
    units = amount * 120
    pyautogui.scroll(-units if direction == "down" else units)


def drag_to(x: int, y: int, duration: float = 0.5) -> None:
    pyautogui.dragTo(x, y, duration=duration)


def hover(x: int, y: int) -> None:
    move_to(x, y)


def center() -> tuple[int, int]:
    w, h = pyautogui.size()
    return w // 2, h // 2


if __name__ == "__main__":
    cx, cy = center()
    move_to(cx, cy)
    print(f"cursor moved to screen center ({cx}, {cy})")
