"""Chrome control via Selenium (webdriver-manager auto-matches ChromeDriver)."""
import sys
import urllib.parse

from config import settings

_driver = None

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


def _get_driver():
    global _driver
    if _driver is not None:
        try:
            _ = _driver.current_url  # probe: still alive?
            return _driver
        except Exception:
            _driver = None
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
    _driver = (webdriver.Chrome(service=service, options=options)
               if service else webdriver.Chrome(options=options))
    _driver.set_page_load_timeout(settings.BROWSER_PAGE_LOAD_TIMEOUT)
    return _driver


def open_browser() -> str:
    _get_driver()
    return "Chrome is open"


def close_browser() -> str:
    global _driver
    if _driver:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
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


def navigate(target: str) -> str:
    d = _get_driver()
    url = _normalize_url(target)
    try:
        d.get(url)
    except Exception as e:
        return f"Couldn't load {target}: page timed out"
    _notify_if_blocked(d)
    return f"Opened {target}"


def search_google(query: str) -> str:
    d = _get_driver()
    d.get("https://www.google.com/search?q=" + urllib.parse.quote(query))
    _notify_if_blocked(d)
    return f"Here are Google results for {query}"


def search_youtube(query: str) -> str:
    d = _get_driver()
    d.get("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query))
    return f"Here are YouTube results for {query}"


def back() -> str:
    _get_driver().back()
    return "Went back"


def forward() -> str:
    _get_driver().forward()
    return "Went forward"


def new_tab(url: str | None = None) -> str:
    d = _get_driver()
    d.switch_to.new_window("tab")
    if url:
        d.get(_normalize_url(url))
    return "Opened a new tab"


def scroll_page(direction: str = "down", amount: int = 5) -> str:
    d = _get_driver()
    px = amount * 120 * (1 if direction == "down" else -1)
    d.execute_script(f"window.scrollBy(0, {px});")
    return f"Scrolled {direction}"


def click_element(text: str) -> str:
    """Click a link/button/input whose visible text or label matches."""
    from selenium.webdriver.common.by import By
    d = _get_driver()
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
    d = _get_driver()
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
    d = _get_driver()
    title = d.title or "Untitled page"
    try:
        body = d.find_element("tag name", "body").text
    except Exception:
        body = ""
    snippet = " ".join(body.split()[:60])
    return f"The page is titled {title}. It says: {snippet}"


# ── YOUTUBE CONTROLS ─────────────────────────────────────
def youtube_play() -> str:
    """Play the current YouTube video."""
    d = _get_driver()
    try:
        # Try to find the play button
        play_button = d.find_element(By.CSS_SELECTOR, ".ytp-play-button[aria-label='Play'], button.ytp-play-button[aria-label='Play']")
        play_button.click()
        return "Playing YouTube video"
    except Exception:
        try:
            # Alternative selector
            play_button = d.find_element(By.XPATH, "//button[@aria-label='Play']")
            play_button.click()
            return "Playing YouTube video"
        except Exception:
            return "Couldn't find YouTube play button"


def youtube_pause() -> str:
    """Pause the current YouTube video."""
    d = _get_driver()
    try:
        # Try to find the pause button
        pause_button = d.find_element(By.CSS_SELECTOR, ".ytp-play-button[aria-label='Pause'], button.ytp-play-button[aria-label='Pause']")
        pause_button.click()
        return "Paused YouTube video"
    except Exception:
        try:
            # Alternative selector
            pause_button = d.find_element(By.XPATH, "//button[@aria-label='Pause']")
            pause_button.click()
            return "Paused YouTube video"
        except Exception:
            return "Couldn't find YouTube pause button"


def youtube_seek(seconds: int) -> str:
    """Seek forward or backward by specified seconds on YouTube."""
    d = _get_driver()
    try:
        if seconds > 0:
            # Forward
            js = f"var player = document.getElementById('movie_player'); if (player) {{ player.seekTo(player.getCurrentTime() + {seconds}, true); }};";
            d.execute_script(js)
            return f"Seeked forward {seconds} seconds"
        else:
            # Backward
            js = f"var player = document.getElementById('movie_player'); if (player) {{ player.seekTo(player.getCurrentTime() - {abs(seconds)}, true); }};";
            d.execute_script(js)
            return f"Seeked backward {abs(seconds)} seconds"
    except Exception:
        return f"Couldn't seek {'forward' if seconds > 0 else 'backward'} on YouTube"


def youtube_set_quality(quality: str) -> str:
    """Set YouTube video quality."""
    d = _get_driver()
    try:
        # Click on settings button
        settings_button = d.find_element(By.CSS_SELECTOR, ".ytp-settings-button")
        settings_button.click()
        # Wait a bit for menu to appear
        import time
        time.sleep(0.5)
        # Click on quality option
        quality_option = d.find_element(By.XPATH, f"//div[contains(@class, 'ytp-menuitem') and contains(text(), '{quality}')]")
        quality_option.click()
        # Close settings menu
        settings_button.click()
        return f"YouTube quality set to {quality}"
    except Exception:
        return f"Couldn't set YouTube quality to {quality}"


def youtube_like() -> str:
    """Like the current YouTube video."""
    d = _get_driver()
    try:
        like_button = d.find_element(By.XPATH, "//ytd-toggle-button-renderer[@title='I like this']")
        like_button.click()
        return "Liked YouTube video"
    except Exception:
        try:
            like_button = d.find_element(By.XPATH, "//button[@aria-label='Like']")
            like_button.click()
            return "Liked YouTube video"
        except Exception:
            return "Couldn't like YouTube video"


def youtube_dislike() -> str:
    """Dislike the current YouTube video."""
    d = _get_driver()
    try:
        dislike_button = d.find_element(By.XPATH, "//ytd-toggle-button-renderer[@title='I dislike this']")
        dislike_button.click()
        return "Disliked YouTube video"
    except Exception:
        try:
            dislike_button = d.find_element(By.XPATH, "//button[@aria-label='Dislike']")
            dislike_button.click()
            return "Disliked YouTube video"
        except Exception:
            return "Couldn't dislike YouTube video"


def youtube_share() -> str:
    """Share the current YouTube video."""
    d = _get_driver()
    try:
        share_button = d.find_element(By.XPATH, "//button[@aria-label='Share']")
        share_button.click()
        return "Opened YouTube share dialog"
    except Exception:
        return "Couldn't open YouTube share dialog"


def youtube_comment(comment: str) -> str:
    """Add a comment to the current YouTube video."""
    d = _get_driver()
    try:
        # Click on comment box
        comment_box = d.find_element(By.XPATH, "//div[@id='simplebox-placeholder']")
        comment_box.click()
        # Enter comment
        comment_input = d.find_element(By.XPATH, "//div[@id='contenteditable-root']")
        comment_input.send_keys(comment)
        # Click submit
        submit_button = d.find_element(By.XPATH, "//button[@aria-label='Comment']")
        submit_button.click()
        return f"Commented on YouTube video: {comment}"
    except Exception:
        return f"Couldn't comment on YouTube video"


def youtube_subscribe() -> str:
    """Subscribe to the current YouTube channel."""
    d = _get_driver()
    try:
        subscribe_button = d.find_element(By.XPATH, "//ytd-subscribe-button-renderer//paper-button")
        subscribe_button.click()
        return "Subscribed to YouTube channel"
    except Exception:
        try:
            subscribe_button = d.find_element(By.XPATH, "//button[@aria-label='Subscribe']")
            subscribe_button.click()
            return "Subscribed to YouTube channel"
        except Exception:
            return "Couldn't subscribe to YouTube channel"


def youtube_next_video() -> str:
    """Skip to next video in YouTube playlist/queue."""
    d = _get_driver()
    try:
        next_button = d.find_element(By.CSS_SELECTOR, ".ytp-next-button")
        next_button.click()
        return "Skipped to next YouTube video"
    except Exception:
        try:
            next_button = d.find_element(By.XPATH, "//button[@title='Next video']")
            next_button.click()
            return "Skipped to next YouTube video"
        except Exception:
            return "Couldn't skip to next YouTube video"


def youtube_previous_video() -> str:
    """Skip to previous video in YouTube playlist/queue."""
    d = _get_driver()
    try:
        prev_button = d.find_element(By.CSS_SELECTOR, ".ytp-prev-button")
        prev_button.click()
        return "Skipped to previous YouTube video"
    except Exception:
        try:
            prev_button = d.find_element(By.XPATH, "//button[@title='Previous video']")
            prev_button.click()
            return "Skipped to previous YouTube video"
        except Exception:
            return "Couldn't skip to previous YouTube video"


def youtube_toggle_captions() -> str:
    """Toggle captions on/off for YouTube video."""
    d = _get_driver()
    try:
        cc_button = d.find_element(By.CSS_SELECTOR, ".ytp-caption-button")
        cc_button.click()
        return "Toggled YouTube captions"
    except Exception:
        try:
            cc_button = d.find_element(By.XPATH, "//button[@aria-label='Captions']")
            cc_button.click()
            return "Toggled YouTube captions"
        except Exception:
            return "Couldn't toggle YouTube captions"


def youtube_theater_mode() -> str:
    """Toggle theater mode for YouTube."""
    d = _get_driver()
    try:
        theater_button = d.find_element(By.CSS_SELECTOR, ".ytp-theater-mode-button")
        theater_button.click()
        return "Toggled YouTube theater mode"
    except Exception:
        try:
            theater_button = d.find_element(By.XPATH, "//button[@aria-label='Theater mode']")
            theater_button.click()
            return "Toggled YouTube theater mode"
        except Exception:
            return "Couldn't toggle YouTube theater mode"


def youtube_fullscreen() -> str:
    """Toggle fullscreen for YouTube video."""
    d = _get_driver()
    try:
        fs_button = d.find_element(By.CSS_SELECTOR, ".ytp-fullscreen-button")
        fs_button.click()
        return "Toggled YouTube fullscreen"
    except Exception:
        try:
            fs_button = d.find_element(By.XPATH, "//button[@aria-label='Full screen']")
            fs_button.click()
            return "Toggled YouTube fullscreen"
        except Exception:
            return "Couldn't toggle YouTube fullscreen"


def youtube_volume(volume_percent: int) -> str:
    """Control YouTube volume independently (0-100)."""
    d = _get_driver()
    try:
        # Find the volume slider
        volume_slider = d.find_element(By.CSS_SELECTOR, ".ytp-volume-slider")
        # Click to focus
        volume_slider.click()
        # Set volume via JavaScript
        js = f"var slider = document.querySelector('.ytp-volume-slider'); if (slider) {{ slider.value = {volume_percent}; var event = new Event('input', {{ bubbles: true }}); slider.dispatchEvent(event); }};"
        d.execute_script(js)
        return f"YouTube volume set to {volume_percent}%"
    except Exception:
        return f"Couldn't set YouTube volume to {volume_percent}%"


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


if __name__ == "__main__":
    print(open_browser())
    print(navigate("google.com"))
    print(read_page()[:120])
    print(close_browser())
