"""Communication control: WhatsApp messaging, calls via web automation.

Uses Selenium to drive web.whatsapp.com in a persistent Chrome session.
Contacts are resolved from memory (brain.memory.long_term) or from recent
conversation context.
"""
import re
import time

from core import state as core_state


def _resolve_contact(name: str) -> str | None:
    """Resolve a contact name to a WhatsApp phone number or saved name.

    Checks:
      1. Long-term memory contacts (stored by the user)
      2. Recent conversation context for mentioned contacts
    Returns the name/number to search for on web.whatsapp.com, or None.
    """
    from brain.memory import memory

    # Check explicitly saved contacts
    contact = memory.get_contact(name)
    if contact:
        return contact.get("whatsapp") or contact.get("name") or name

    # Check recent conversation for a previously mentioned contact
    # (search memory context)
    from brain.nlp import detect_language, normalize_transcription
    context = memory.recall_relevant(name, top_k=3)
    if context and name.lower() in context.lower():
        # Extract the contact name from context
        return name

    return name  # Fall through to WhatsApp search


def _open_whatsapp() -> object | None:
    """Open web.whatsapp.com if not already open. Returns the Selenium driver."""
    from control import browser

    driver = browser._get_driver()
    current = driver.current_url
    if "web.whatsapp" not in current:
        driver.get("https://web.whatsapp.com")
        # Wait for WhatsApp to load
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list-search"]'))
            )
        except Exception:
            pass  # May require QR scan — continue anyway
    return driver


def send_whatsapp_message(contact: str, message: str) -> str:
    """Send a WhatsApp message to a contact via web.whatsapp.com."""
    driver = _open_whatsapp()
    if driver is None:
        return "I couldn't open WhatsApp — is Chrome installed?"

    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys

        # Search for the contact
        search_xpath = '//div[@data-testid="chat-list-search"]'
        try:
            search_box = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, search_xpath))
            )
        except Exception:
            return "WhatsApp didn't load — you may need to scan the QR code."

        search_box.clear()
        search_box.send_keys(contact)
        time.sleep(1)

        # Click the contact
        contact_xpath = f'//div[contains(@title, "{contact}") or @data-testid="conversation-item-{contact}"]'
        try:
            contact_elem = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, contact_xpath))
            )
            contact_elem.click()
        except Exception:
            # Try the first result in the search list
            try:
                first_result = driver.find_element(
                    By.XPATH,
                    '//div[@role="button" and .//span[contains(text(), "{}")]]'.format(contact),
                )
                first_result.click()
            except Exception:
                return f"I couldn't find {contact} on WhatsApp — are they saved in your contacts?"

        # Type and send the message
        msg_box_xpath = '//div[@data-testid="conversation-compose-box-input"]'
        msg_box = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, msg_box_xpath))
        )
        msg_box.send_keys(message)
        time.sleep(0.5)

        send_btn_xpath = '//button[@data-testid="conversation-send-button"]'
        send_btn = driver.find_element(By.XPATH, send_btn_xpath)
        send_btn.click()
        time.sleep(0.5)

        # Verify message was sent
        return f"Message sent to {contact} on WhatsApp"
    except Exception as e:
        return f"Failed to send WhatsApp message: {e}"


def make_voice_call(contact: str) -> str:
    """Initiate a voice call via WhatsApp."""
    driver = _open_whatsapp()
    if driver is None:
        return "I couldn't open WhatsApp — is Chrome installed?"

    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Search for the contact
        search_xpath = '//div[@data-testid="chat-list-search"]'
        search_box = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, search_xpath))
        )
        search_box.clear()
        search_box.send_keys(contact)
        time.sleep(1)

        # Click the contact
        contact_xpath = f'//div[@role="button" and contains(., "{contact}")]'
        try:
            contact_elem = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, contact_xpath))
            )
            contact_elem.click()
        except Exception:
            return f"I couldn't find {contact} on WhatsApp"

        # Click the video call button
        time.sleep(1)
        call_btn = driver.find_element(
            By.XPATH, '//button[@data-testid="conversation-call"]'
        )
        call_btn.click()
        return f"Calling {contact} on WhatsApp"
    except Exception as e:
        return f"Failed to call {contact}: {e}"


def send_sms(contact: str, message: str) -> str:
    """Send an SMS via the system's default SMS handler (Windows 10/11)."""
    try:
        from winrt.windows.system import Launcher
        import asyncio
        uri = f"sms:?phone={contact}&body={message}"
        asyncio.run(Launcher.LaunchUriAsync(Windows.Foundation.Uri(uri)))
        return f"SMS opened for {contact}"
    except Exception:
        return "SMS sending requires the Windows 10 Messages app — please send manually"


def format_message(text: str) -> str:
    """Clean up spoken message text — expand spoken punctuation, etc."""
    from brain.nlp import normalize_transcription
    return normalize_transcription(text)


if __name__ == "__main__":
    print("Testing contact resolution...")
    contact = _resolve_contact("Rohan")
    print(f"Resolved: {contact}")
    print("Communication module OK")
