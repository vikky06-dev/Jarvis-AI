"""Notepad agent — automation of Windows Notepad.

Supports:
- Writing text to Notepad
- Basic formatting (font, size via dialog)
- Find and replace
- Save/Save As
- Open existing files
- Undo/Redo
"""

import subprocess
import time
from pathlib import Path

from config import settings
from core import state as core_state
import pyautogui
import pygetwindow as gw


def _get_notepad_window() -> gw.Win32Window | None:
    """Get the active Notepad window, or open one if none exists."""
    # Try to find existing Notepad window
    notepad_windows = [w for w in gw.getAllWindows()
                      if 'notepad' in w.title.lower() and w.title]

    if notepad_windows:
        return notepad_windows[0]

    # No Notepad window found, open a new one
    subprocess.Popen(['notepad.exe'])
    time.sleep(1)  # Wait for Notepad to open

    # Try again to find the window
    notepad_windows = [w for w in gw.getAllWindows()
                      if 'notepad' in w.title.lower() and w.title]
    return notepad_windows[0] if notepad_windows else None


def write_text(text: str) -> str:
    """Write text to the active Notepad window."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)
        pyautogui.write(text)
        return f"Text written to Notepad"
    except Exception as e:
        return f"Failed to write text to Notepad: {str(e)}"


def set_font(font_name: str, font_size: int = None) -> str:
    """Change font in Notepad via Format -> Font dialog."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)

        # Open Format menu
        pyautogui.hotkey('alt', 'o')
        time.sleep(0.5)
        # Select Font option
        pyautogui.press('f')
        time.sleep(1)

        # Font selection would be complex here - for simplicity,
        # we'll note that full font control requires more complex automation
        return f"Font dialog opened - please select {font_name} manually"
    except Exception as e:
        return f"Failed to open font dialog: {str(e)}"


def find_replace(find_text: str, replace_with: str = "", replace_all: bool = False) -> str:
    """Find and/or replace text in Notepad."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)

        # Open Find dialog
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(0.5)

        # Enter find text
        pyautogui.write(find_text)

        if replace_with:
            # Click Replace tab
            pyautogui.press('alt', 'r')
            time.sleep(0.5)
            # Enter replace text
            pyautogui.write(replace_with)

            if replace_all:
                # Click Replace All
                pyautogui.press('alt', 'a')
                return f"Replaced all instances of '{find_text}' with '{replace_with}'"
            else:
                # Click Replace
                pyautogui.press('alt', 'p')
                return f"Replaced first instance of '{find_text}' with '{replace_with}'"
        else:
            # Just find - click Find Next
            pyautogui.press('enter')
            return f"Searching for '{find_text}' in Notepad"

    except Exception as e:
        return f"Failed to perform find/replace: {str(e)}"


def save_file(file_path: str = None) -> str:
    """Save the current Notepad file."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)

        if file_path:
            # Save As
            pyautogui.hotkey('ctrl', 'shift', 's')
            time.sleep(1)
            # Type file path
            pyautogui.write(file_path)
            pyautogui.press('enter')
            return f"Saved Notepad file as {file_path}"
        else:
            # Save
            pyautogui.hotkey('ctrl', 's')
            return "Notepad file saved"
    except Exception as e:
        return f"Failed to save Notepad file: {str(e)}"


def open_file(file_path: str) -> str:
    """Open a file in Notepad."""
    try:
        subprocess.Popen(['notepad.exe', file_path])
        time.sleep(1)
        return f"Opened {file_path} in Notepad"
    except Exception as e:
        return f"Failed to open file in Notepad: {str(e)}"


def undo() -> str:
    """Perform Undo in Notepad."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'z')
        return "Undo performed in Notepad"
    except Exception as e:
        return f"Failed to perform undo: {str(e)}"


def redo() -> str:
    """Perform Redo in Notepad."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'y')
        return "Redo performed in Notepad"
    except Exception as e:
        return f"Failed to perform redo: {str(e)}"


def clear_all() -> str:
    """Clear all text in Notepad."""
    win = _get_notepad_window()
    if not win:
        return "Couldn't find or open Notepad window"

    try:
        win.activate()
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        return "All text cleared from Notepad"
    except Exception as e:
        return f"Failed to clear Notepad: {str(e)}"


if __name__ == "__main__":
    # For testing
    print("Notepad agent loaded")