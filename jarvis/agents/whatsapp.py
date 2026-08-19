"""WhatsApp agent — via WhatsApp Web automation.

Requires:
  1. User to be logged into WhatsApp Web in Chrome
  2. Or to scan QR code on first use

Basic functionality:
- Send messages to contacts/groups
- Share media (images, videos, documents)
- Make voice/video calls (limited support)
"""

import subprocess
import sys
import time
from pathlib import Path

from config import settings
from core import state as core_state
from control.browser import _get_driver, _notify_if_blocked
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException

_WHATSAPP_WEB_URL = "https://web.whatsapp.com"


def _ensure_whatsapp_loaded() -> str | None:
    """Ensure WhatsApp Web is loaded and ready. Returns error message if fails."""
    d = _get_driver()
    try:
        d.get(_WHATSAPP_WEB_URL)
        # Wait for page to load
        time.sleep(3)

        # Check if we need to scan QR code
        try:
            qr_code = d.find_element(By.XPATH, "//div[@data-ref]//canvas[@aria-label='Scan me!']")
            return "Please scan the QR code to link WhatsApp Web"
        except NoSuchElementException:
            # Check if chat list is loaded (indicates we're logged in)
            try:
                d.find_element(By.XPATH, "//div[@id='pane-side']")
                return None  # Success, WhatsApp Web is ready
            except NoSuchElementException:
                return "WhatsApp Web is loading..."
    except Exception as e:
        return f"Failed to load WhatsApp Web: {str(e)}"


def _find_contact(contact_name: str) -> bool:
    """Search for and select a contact or group."""
    d = _get_driver()
    try:
        # Click on search box
        search_box = d.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='3']")
        search_box.click()
        search_box.clear()

        # Type contact name
        search_box.send_keys(contact_name)
        time.sleep(1)

        # Select the first result
        contact = d.find_element(By.XPATH, f"//span[@title='{contact_name}']")
        contact.click()
        time.sleep(1)
        return True
    except NoSuchElementException:
        try:
            # Try partial match
            contact = d.find_element(By.XPATH, f"//span[contains(@title, '{contact_name}')]")
            contact.click()
            time.sleep(1)
            return True
        except NoSuchElementException:
            return False
    except Exception:
        return False


def send_message(contact: str, message: str) -> str:
    """Send a text message to a contact or group."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    d = _get_driver()
    try:
        # Find message input box
        msg_box = d.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='1']")
        msg_box.click()
        msg_box.clear()
        msg_box.send_keys(message)
        msg_box.send_keys(Keys.ENTER)
        return f"Message sent to {contact}"
    except Exception as e:
        return f"Failed to send message: {str(e)}"


def send_media(contact: str, file_path: str, caption: str = "") -> str:
    """Send media (image, video, document) to a contact or group."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    d = _get_driver()
    try:
        # Click attach button
        attach_btn = d.find_element(By.XPATH, "//div[@title='Attach']")
        attach_btn.click()
        time.sleep(0.5)

        # Choose file type based on extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            # Image
            file_input = d.find_element(By.XPATH, "//input[@accept='image/*']")
        elif file_ext in ['.mp4', '.avi', '.mov', '.mkv']:
            # Video
            file_input = d.find_element(By.XPATH, "//input[@accept='video/*']")
        elif file_ext in ['.mp3', '.wav', '.ogg', '.flac']:
            # Audio
            file_input = d.find_element(By.XPATH, "//input[@accept='audio/*']")
        else:
            # Document
            file_input = d.find_element(By.XPATH, "//input[@accept='*']")

        file_input.send_keys(file_path)
        time.sleep(2)  # Wait for file to process

        # Add caption if provided
        if caption:
            try:
                caption_box = d.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='1']")
                caption_box.send_keys(caption)
            except NoSuchElementException:
                pass  # Caption box might not be available for all file types

        # Send
        send_btn = d.find_element(By.XPATH, "//span[@data-icon='send']")
        send_btn.click()
        return f"Media sent to {contact}"
    except Exception as e:
        return f"Failed to send media: {str(e)}"


def make_voice_call(contact: str) -> str:
    """Make a voice call to a contact."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    d = _get_driver()
    try:
        call_btn = d.find_element(By.XPATH, "//div[@title='Voice call']")
        call_btn.click()
        return f"Voice call initiated with {contact}"
    except Exception as e:
        return f"Failed to initiate voice call: {str(e)}"


def make_video_call(contact: str) -> str:
    """Make a video call to a contact."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    d = _get_driver()
    try:
        call_btn = d.find_element(By.XPATH, "//div[@title='Video call']")
        call_btn.click()
        return f"Video call initiated with {contact}"
    except Exception as e:
        return f"Failed to initiate video call: {str(e)}"


def send_reaction(contact: str, emoji: str) -> str:
    """Send an emoji reaction to the last message in a chat."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    d = _get_driver()
    try:
        # This is complex as it requires finding the last message and clicking the reaction button
        # For simplicity, we'll implement a basic version
        return f"Reaction sending not fully implemented for {contact}"
    except Exception as e:
        return f"Failed to send reaction: {str(e)}"


def star_message(contact: str) -> str:
    """Star the last message in a chat."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    if not _find_contact(contact):
        return f"Couldn't find contact: {contact}"

    # Implementation would be similar to send_reaction
    return f"Message starring not fully implemented for {contact}"


def create_group(group_name: str, participants: list[str]) -> str:
    """Create a new group with specified participants."""
    result = _ensure_whatsapp_loaded()
    if result:
        return result

    d = _get_driver()
    try:
        # Click new chat
        new_chat = d.find_element(By.XPATH, "//div[@title='New chat']")
        new_chat.click()

        # Click new group
        new_group = d.find_element(By.XPATH, "//div[@title='New group']")
        new_group.click()

        # Add participants
        for participant in participants:
            if not _find_contact(participant):
                return f"Couldn't find participant: {participant}"

        # Click next
        next_btn = d.find_element(By.XPATH, "//div[@title='Next']")
        next_btn.click()

        # Enter group name
        group_name_box = d.find_element(By.XPATH, "//div[@contenteditable='true'][@data-tab='3']")
        group_name_box.click()
        group_name_box.clear()
        group_name_box.send_keys(group_name)

        # Create group
        create_btn = d.find_element(By.XPATH, "//div[@title='Create']")
        create_btn.click()

        return f"Group '{group_name}' created"
    except Exception as e:
        return f"Failed to create group: {str(e)}"


if __name__ == "__main__":
    # For testing
    print("WhatsApp agent loaded")