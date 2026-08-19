"""Chrome and Brave control via Selenium (webdriver-manager auto-matches ChromeDriver)."""
import sys
import os
import urllib.parse

from config import settings

_chrome_driver = None
_brave_driver = None

SITE_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.in",
    "netflix": "https://www.netflix.com",
}


def _get_chrome_driver():
    global _chrome_driver
    if _chrome_driver is not None:
        try:
            _ = _chrome_driver.current_url  # probe: still alive?
            return _chrome_driver
        except Exception:
            _chrome_driver = None
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception as e:
        print(f"[browser] webdriver-manager failed ({e}); trying Selenium Manager", file=sys.stderr)
        service = None
    options = webdriver.ChromeOptions()
    options.binary_location = settings.CHROME_EXE
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--start-maximized")
    _chrome_driver = (webdriver.Chrome(service=service, options=options)
                   if service else webdriver.Chrome(options=options))
    _chrome_driver.set_page_load_timeout(settings.BROWSER_PAGE_LOAD_TIMEOUT)
    return _chrome_driver


def _get_brave_driver():
    global _brave_driver
    if _brave_driver is not None:
        try:
            _ = _brave_driver.current_url  # probe: still alive?
            return _brave_driver
        except Exception:
            _brave_driver = None
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception as e:
        print(f"[browser] webdriver-manager failed ({e}); trying Selenium Manager", file=sys.stderr)
        service = None
    options = webdriver.ChromeOptions()
    # Check if Brave is installed
    if os.path.exists(settings.BRAVE_EXE):
        options.binary_location = settings.BRAVE_EXE
    else:
        # Fallback to Chrome if Brave not found
        options.binary_location = settings.CHROME_EXE
        print("[browser] Brave not found, falling back to Chrome", file=sys.stderr)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--start-maximized")
    _brave_driver = (webdriver.Chrome(service=service, options=options)
                   if service else webdriver.Chrome(options=options))
    _brave_driver.set_page_load_timeout(settings.BROWSER_PAGE_LOAD_TIMEOUT)
    return _brave_driver


def open_browser(browser_type="chrome") -> str:
    if browser_type.lower() == "brave":
        _get_brave_driver()
        return "Brave is open"
    else:
        _get_chrome_driver()
        return "Chrome is open"


def close_browser(browser_type="chrome") -> str:
    global _chrome_driver, _brave_driver
    if browser_type.lower() == "brave":
        if _brave_driver:
            try:
                _brave_driver.quit()
            except Exception:
                pass
            _brave_driver = None
            return "Closed Brave"
        return "Brave isn't open"
    else:
        if _chrome_driver:
            try:
                _chrome_driver.quit()
            except Exception:
                pass
            _chrome_driver = None
            return "Closed Chrome"
        return "Chrome isn't open"


def _normalize_url(target: str) -> str:
    t = target.lower().strip().rstrip("/.")
    if t in SITE_SHORTCUTS:
        return SITE_SHORTCUTS[t]
    if t.startswith(("http://", "https://")):
        return target
    if "." in t:
        return "https://" + target.strip()
    return "https://www.google.com/search?q=" + urllib.parse.quote(target)


def navigate(target: str, browser_type: str = "chrome") -> str:
    if browser_type.lower() == "brave":
        d = _get_brave_driver()
    else:
        d = _get_chrome_driver()
    url = _normalize_url(target)
    try:
        d.get(url)
    except Exception as e:
        return f"Couldn't load {target}: page timed out"
    _notify_if_blocked(d)
    return f"Opened {target}"


def search_google(query: str) -> str:
    d = _get_chrome_driver()
    d.get("https://www.google.com/search?q=" + urllib.parse.quote(query))
    _notify_if_blocked(d)
    return f"Here are Google results for {query}"


def search_youtube(query: str) -> str:
    # Use Brave for YouTube specifically as requested
    d = _get_brave_driver()
    d.get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return f"Here are YouTube results for {query}"


def back() -> str:
    _get_chrome_driver().back()
    return "Went back"


def forward() -> str:
    _get_chrome_driver().forward()
    return "Went forward"


def new_tab(url: str | None = None, browser_type: str = "chrome") -> str:
    if browser_type.lower() == "brave":
        d = _get_brave_driver()
    else:
        d = _get_chrome_driver()
    d.switch_to.new_window("tab")
    if url:
        d.get(_normalize_url(url))
    return "Opened a new tab"


def scroll_page(direction: str = "down", amount: int = 5) -> str:
    d = _get_chrome_driver()
    px = amount * 120 * (1 if direction == "down" else -1)
    d.execute_script(f"window.scrollBy(0, {px});")
    return f"Scrolled {direction}"


def click_element(text: str) -> str:
    """Click a link/button/input whose visible text or label matches."""
    from selenium.webdriver.common.by import By
    d = _get_chrome_driver()
    xpaths = [
        f'//button[contains(normalize-space(.), "{text}")]',
        f'//a[contains(normalize-space(.), "{text}")]',
        f'//*[@role="button"][contains(normalize-space(.), "{text}")]',
        f'//input[@type="submit" or @type="button"][contains(@value, "{text}")]',
        f'//*[contains(normalize-space(text()), "{text}")]',
    ]
    for xp in xpaths:
        try:
            els = d.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    el.click()
                    return f"Clicked {text}"
        except Exception:
            continue
    return f"Couldn't find {text} on the page"


def fill_field(label: str, value: str) -> str:
    from selenium.webdriver.common.by import By
    d = _get_chrome_driver()
    xpaths = [
        f'//input[@placeholder and contains(@placeholder, "{label}")]',
        f'//input[@name and contains(@name, "{label.lower()}")]',
        f'//input[@aria-label and contains(@aria-label, "{label}")]',
        f'//label[contains(normalize-space(.), "{label}")]//input',
        f'//label[contains(normalize-space(.), "{label}")]/following::input[1]',
    ]
    for xp in xpaths:
        try:
            els = d.find_elements(By.XPATH, xp)
            for el in els:
                if el.is_displayed():
                    el.clear()
                    el.send_keys(value)
                    return f"Typed into {label}"
        except Exception:
            continue
    return f"Couldn't find a {label} field"


def read_page() -> str:
    d = _get_chrome_driver()
    title = d.title or "Untitled page"
    try:
        body = d.find_element("tag name", "body").text
    except Exception:
        body = ""
    snippet = " ".join(body.split()[:60])
    return f"The page is titled {title}. It says: {snippet}"


def _notify_if_blocked(driver) -> None:
    """Detect CAPTCHA / cookie walls and tell the user instead of fighting them."""
    try:
        title = (driver.title or "").lower()
        src = driver.page_source[:20000].lower()
        # Substring "captcha" appears in benign Google scripts — only alert
        # on real challenge pages.
        if ("unusual traffic" in src or "verify you are human" in src
                or "i'm not a robot" in src or "captcha" in title):
            from voice.speaker import speak
            speak("This page is showing a CAPTCHA. Please solve it manually.")
        elif "accept all" in src or "cookie" in src and "consent" in src:
            # try a best-effort dismiss of common cookie banners
            for label in ("Accept all", "I agree", "Accept"):
                if "couldn" not in click_element(label).lower():
                    break
    except Exception:
        pass


# Advanced YouTube Controls
def youtube_play() -> str:
    """Play the current YouTube video"""
    d = _get_brave_driver()
    try:
        # Find and click the play button
        play_button = d.find_element("css selector", ".ytp-play-button")
        play_button.click()
        return "Playing YouTube video"
    except Exception:
        return "Could not find play button on YouTube"


def youtube_pause() -> str:
    """Pause the current YouTube video"""
    d = _get_brave_driver()
    try:
        # Find and click the pause button (same as play button when playing)
        play_button = d.find_element("css selector", ".ytp-play-button")
        play_button.click()
        return "Paused YouTube video"
    except Exception:
        return "Could not find play button on YouTube"


def youtube_seek(seconds: int) -> str:
    """Seek forward or backward by specified seconds"""
    d = _get_brave_driver()
    try:
        # Get current time
        current_time = d.execute_script("return document.getElementById('movie_player').getCurrentTime();")
        # Seek to new position
        new_time = max(0, current_time + seconds)
        d.execute_script(f"document.getElementById('movie_player').seekTo({new_time}, true);")
        direction = "forward" if seconds >= 0 else "backward"
        return f"Seeked {abs(seconds)} seconds {direction}"
    except Exception as e:
        return f"Could not seek on YouTube: {str(e)}"


def youtube_set_quality(quality: str) -> str:
    """Set YouTube video quality (e.g., '720p', '1080p', 'highest', 'lowest')"""
    d = _get_brave_driver()
    try:
        # Click on settings button
        settings_button = d.find_element("css selector", ".ytp-settings-button")
        settings_button.click()

        # Wait for menu to appear
        import time
        time.sleep(0.5)

        # Click on quality option
        quality_option = d.find_element("xpath", f"//div[contains(text(), '{quality}') or contains(@data-value, '{quality}')]")
        quality_option.click()

        # Close settings menu
        settings_button.click()

        return f"YouTube quality set to {quality}"
    except Exception as e:
        return f"Could not set YouTube quality: {str(e)}"


def youtube_like() -> str:
    """Like the current YouTube video"""
    d = _get_brave_driver()
    try:
        like_button = d.find_element("css selector", ".ytp-like-button")
        like_button.click()
        return "Liked YouTube video"
    except Exception:
        return "Could not find like button on YouTube"


def youtube_dislike() -> str:
    """Dislike the current YouTube video"""
    d = _get_brave_driver()
    try:
        dislike_button = d.find_element("css selector", ".ytp-dislike-button")
        dislike_button.click()
        return "Disliked YouTube video"
    except Exception:
        return "Could not find dislike button on YouTube"


def youtube_share() -> str:
    """Open share dialog for current YouTube video"""
    d = _get_brave_driver()
    try:
        share_button = d.find_element("css selector", ".ytp-share-button")
        share_button.click()
        return "Opened YouTube share dialog"
    except Exception:
        return "Could not find share button on YouTube"


def youtube_comment(comment_text: str) -> str:
    """Add a comment to the current YouTube video"""
    d = _get_brave_driver()
    try:
        # Click on the comment box
        comment_box = d.find_element("css selector", "#simplebox-placeholder")
        comment_box.click()

        # Type the comment
        comment_input = d.find_element("css selector", "#contenteditable-root")
        comment_input.send_keys(comment_text)

        # Click the submit button
        submit_button = d.find_element("css selector", "#submit-button")
        submit_button.click()

        return f"Added comment: {comment_text}"
    except Exception as e:
        return f"Could not add comment to YouTube: {str(e)}"


def youtube_subscribe() -> str:
    """Subscribe to the current YouTube channel"""
    d = _get_brave_driver()
    try:
        subscribe_button = d.find_element("css selector", "#subscribe-button")
        subscribe_button.click()
        return "Subscribed to YouTube channel"
    except Exception:
        return "Could not find subscribe button on YouTube"


if __name__ == "__main__":
    print(open_browser())
    print(navigate("google.com"))
    print(read_page()[:120])
    print(close_browser())