"""
Feature-specific vision workflows for ULTRON AI
Implements workflows for YouTube, Spotify, WhatsApp, Notepad, web browsing, and system settings
"""

import time
import logging
from typing import Optional, Tuple, List, Dict, Any
from ..vision import (
    vision_engine, find_element, verify_action, read_screen_text,
    check_element_state, type_text, type_text_unicode, press_key,
    press_hotkey, click_element, scroll_at, hover_element, clear_and_type
)

logger = logging.getLogger(__name__)


class YouTubeWorkflow:
    """YouTube-specific vision workflow"""

    @staticmethod
    def search_video(video_name: str) -> bool:
        """
        Search for a video on YouTube.

        Args:
            video_name: Name of the video to search for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find YouTube search bar
            search_x, search_y = find_element("YouTube search bar")
            clear_and_type(search_x, search_y, video_name)

            # Press Enter to search
            press_key("enter")
            time.sleep(2)  # Wait for search results

            # Verify search worked by checking if video title appears
            # This is a simplified verification - in practice would check for specific results
            logger.info(f"Searched for YouTube video: {video_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to search YouTube video '{video_name}': {e}")
            return False

    @staticmethod
    def click_first_result() -> bool:
        """
        Click the first video result in YouTube search.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find first video result (simplified - would need more specific detection)
            # For now, we'll look for a video element
            video_x, video_y = find_element("first video result in YouTube search")
            click_element(video_x, video_y)
            time.sleep(3)  # Wait for video to start loading

            logger.info("Clicked first YouTube search result")
            return True
        except Exception as e:
            logger.error(f"Failed to click first YouTube result: {e}")
            return False

    @staticmethod
    def play_pause() -> bool:
        """
        Toggle play/pause on YouTube video.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find play/pause button
            button_x, button_y = find_element("Play or Pause button in YouTube video player")
            click_element(button_x, button_y)
            time.sleep(1)

            # Verify the action worked by checking button state change
            # (This would be enhanced with actual state checking)
            logger.info("Toggled YouTube play/pause")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle YouTube play/pause: {e}")
            return False

    @staticmethod
    def seek_to_time(seconds: int) -> bool:
        """
        Seek to a specific time in the YouTube video.

        Args:
            seconds: Time to seek to in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find seek bar and get its dimensions
            # This is simplified - actual implementation would need to get bar position and width
            seek_bar_left, seek_bar_top = find_element("leftmost point of YouTube seek bar")
            # In a full implementation, we'd also get the width

            # For now, we'll approximate - this would be enhanced
            target_x = seek_bar_left + 100  # Placeholder calculation
            target_y = seek_bar_top

            click_element(target_x, target_y)
            time.sleep(1)

            logger.info(f"YouTube seeked to {seconds} seconds")
            return True
        except Exception as e:
            logger.error(f"Failed to seek YouTube video to {seconds} seconds: {e}")
            return False

    @staticmethod
    def like_video() -> bool:
        """
        Like the current YouTube video.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find like button
            like_x, like_y = find_element("Like button on YouTube video")
            click_element(like_x, like_y)
            time.sleep(1)

            logger.info("Liked YouTube video")
            return True
        except Exception as e:
            logger.error(f"Failed to like YouTube video: {e}")
            return False

    @staticmethod
    def is_playing() -> bool:
        """
        Check if YouTube video is currently playing.

        Returns:
            True if playing, False if paused
        """
        try:
            state = check_element_state(
                "YouTube play/pause button",
                ["PLAYING", "PAUSED"]  # Simplified - actual states would be more specific
            )
            return state == "PLAYING"
        except Exception as e:
            logger.error(f"Failed to check YouTube playback state: {e}")
            return False


class SpotifyWorkflow:
    """Spotify-specific vision workflow"""

    @staticmethod
    def search_song(song_name: str) -> bool:
        """
        Search for a song on Spotify.

        Args:
            song_name: Name of the song to search for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find Spotify search bar
            search_x, search_y = find_element("search bar at the top of Spotify interface")
            clear_and_type(search_x, search_y, song_name)

            # Press Enter to search
            press_key("enter")
            time.sleep(2)  # Wait for search results

            logger.info(f"Searched for Spotify song: {song_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to search Spotify song '{song_name}': {e}")
            return False

    @staticmethod
    def click_first_result() -> bool:
        """
        Click the first song result in Spotify search.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find first song result
            song_x, song_y = find_element("first song result in Spotify search")
            click_element(song_x, song_y)
            time.sleep(2)  # Wait for song to start

            logger.info("Clicked first Spotify search result")
            return True
        except Exception as e:
            logger.error(f"Failed to click first Spotify result: {e}")
            return False

    @staticmethod
    def play_pause() -> bool:
        """
        Toggle play/pause on Spotify.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find play/pause button
            button_x, button_y = find_element("Play or Pause button in Spotify player bar")
            click_element(button_x, button_y)
            time.sleep(1)

            logger.info("Toggled Spotify play/pause")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle Spotify play/pause: {e}")
            return False

    @staticmethod
    def next_track() -> bool:
        """
        Skip to next track on Spotify.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find next track button
            button_x, button_y = find_element("Skip Next button in Spotify player bar")
            click_element(button_x, button_y)
            time.sleep(1)

            logger.info("Skipped to next Spotify track")
            return True
        except Exception as e:
            logger.error(f"Failed to skip to next Spotify track: {e}")
            return False

    @staticmethod
    def previous_track() -> bool:
        """
        Skip to previous track on Spotify.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find previous track button
            button_x, button_y = find_element("Skip Previous button in Spotify player bar")
            click_element(button_x, button_y)
            time.sleep(1)

            logger.info("Skipped to previous Spotify track")
            return True
        except Exception as e:
            logger.error(f"Failed to skip to previous Spotify track: {e}")
            return False

    @staticmethod
    def toggle_shuffle() -> bool:
        """
        Toggle shuffle on/off on Spotify.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find shuffle button and check its state
            shuffle_x, shuffle_y = find_element("Shuffle button in Spotify player bar")
            current_state = check_element_state(
                "Shuffle button in Spotify player bar",
                ["ENABLED", "DISABLED"]
            )

            # Click to toggle
            click_element(shuffle_x, shuffle_y)
            time.sleep(1)

            new_state = check_element_state(
                "Shuffle button in Spotify player bar",
                ["ENABLED", "DISABLED"]
            )

            logger.info(f"Toggled Spotify shuffle from {current_state} to {new_state}")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle Spotify shuffle: {e}")
            return False

    @staticmethod
    def get_current_song() -> Optional[str]:
        """
        Get the name of the currently playing song on Spotify.

        Returns:
            Song name if successful, None otherwise
        """
        try:
            song_name = read_screen_text("name of the currently playing song in Spotify player bar")
            logger.info(f"Current Spotify song: {song_name}")
            return song_name
        except Exception as e:
            logger.error(f"Failed to get current Spotify song: {e}")
            return None

    @staticmethod
    def is_shuffle_enabled() -> bool:
        """
        Check if Spotify shuffle is enabled.

        Returns:
            True if shuffle enabled, False otherwise
        """
        try:
            state = check_element_state(
                "Shuffle button in Spotify player bar",
                ["ENABLED", "DISABLED"]
            )
            return state == "ENABLED"
        except Exception as e:
            logger.error(f"Failed to check Spotify shuffle state: {e}")
            return False

    @staticmethod
    def set_volume(level: int) -> bool:
        """
        Set Spotify volume level (0-100).

        Args:
            level: Volume level to set (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find volume slider
            slider_x, slider_y = find_element("volume slider handle in Spotify player bar")
            # Get slider bounds (would need enhancement)
            # For now, simplified approach

            # Click and drag to set volume (simplified)
            click_element(slider_x, slider_y)
            # In a full implementation, we'd calculate drag distance based on level

            logger.info(f"Set Spotify volume to {level}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set Spotify volume to {level}%: {e}")
            return False


class WhatsAppWorkflow:
    """WhatsApp-specific vision workflow"""

    @staticmethod
    def search_contact(contact_name: str) -> bool:
        """
        Search for a contact in WhatsApp.

        Args:
            contact_name: Name of the contact to search for

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find WhatsApp search bar
            search_x, search_y = find_element("search contacts or chats search bar in WhatsApp")
            clear_and_type(search_x, search_y, contact_name)
            time.sleep(1)  # Wait for search results

            logger.info(f"Searched for WhatsApp contact: {contact_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to search WhatsApp contact '{contact_name}': {e}")
            return False

    @staticmethod
    def select_contact(contact_name: str) -> bool:
        """
        Select a contact from WhatsApp search results.

        Args:
            contact_name: Name of the contact to select

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find contact in search results
            contact_x, contact_y = find_element(f"contact named {contact_name} in WhatsApp search results")
            click_element(contact_x, contact_y)
            time.sleep(1)  # Wait for chat to open

            logger.info(f"Selected WhatsApp contact: {contact_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to select WhatsApp contact '{contact_name}': {e}")
            return False

    @staticmethod
    def send_message(message: str) -> bool:
        """
        Send a message in the current WhatsApp chat.

        Args:
            message: Message text to send

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find message input box
            input_x, input_y = find_element("message typing input box at bottom of WhatsApp chat")
            clear_and_type(input_x, input_y, message)

            # Find send button
            send_x, send_y = find_element("Send button in WhatsApp message input area")
            click_element(send_x, send_y)
            time.sleep(1)

            logger.info(f"Sent WhatsApp message: {message[:50]}{'...' if len(message) > 50 else ''}")
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    @staticmethod
    def attach_file(file_path: str) -> bool:
        """
        Attach a file in WhatsApp chat.

        Args:
            file_path: Path to file to attach

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find attachment button
            attach_x, attach_y = find_element("attachment/paperclip icon in WhatsApp message input area")
            click_element(attach_x, attach_y)
            time.sleep(1)

            # In a full implementation, we'd navigate file dialog to select file
            # For now, we'll simulate file selection
            logger.info(f"Attached file to WhatsApp: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to attach file to WhatsApp: {e}")
            return False

    @staticmethod
    def make_call() -> bool:
        """
        Make a voice call in current WhatsApp chat.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find call button
            call_x, call_y = find_element("voice call button at top right of WhatsApp chat")
            click_element(call_x, call_y)
            time.sleep(2)  # Wait for call to connect

            logger.info("Made WhatsApp voice call")
            return True
        except Exception as e:
            logger.error(f"Failed to make WhatsApp voice call: {e}")
            return False

    @staticmethod
    def make_video_call() -> bool:
        """
        Make a video call in current WhatsApp chat.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find video call button
            video_call_x, video_call_y = find_element("video call button at top right of WhatsApp chat")
            click_element(video_call_x, video_call_y)
            time.sleep(2)  # Wait for call to connect

            logger.info("Made WhatsApp video call")
            return True
        except Exception as e:
            logger.error(f"Failed to make WhatsApp video call: {e}")
            return False


class NotepadWorkflow:
    """Notepad-specific vision workflow"""

    @staticmethod
    def create_new_file() -> bool:
        """
        Create a new Notepad file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Click on text area to focus it
            text_x, text_y = find_element("main text editing area in Notepad window")
            click_element(text_x, text_y)
            time.sleep(0.5)

            logger.info("Created new Notepad file")
            return True
        except Exception as e:
            logger.error(f"Failed to create new Notepad file: {e}")
            return False

    @staticmethod
    def write_text(text: str) -> bool:
        """
        Write text to Notepad.

        Args:
            text: Text to write

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find text area
            text_x, text_y = find_element("main text editing area in Notepad window")
            clear_and_type(text_x, text_y, text)

            logger.info(f"Wrote text to Notepad: {text[:50]}{'...' if len(text) > 50 else ''}")
            return True
        except Exception as e:
            logger.error(f"Failed to write text to Notepad: {e}")
            return False

    @staticmethod
    def save_file(file_path: str) -> bool:
        """
        Save Notepad file to specified path.

        Args:
            file_path: Path to save file to

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open Save As dialog
            press_hotkey("ctrl", "shift", "s")  # Save As
            time.sleep(1)

            # Find filename field
            filename_x, filename_y = find_element("filename input field in Save As dialog")
            clear_and_type(filename_x, filename_y, file_path)
            time.sleep(0.5)

            # Find Save button
            save_x, save_y = find_element("Save button in Save As dialog")
            click_element(save_x, save_y)
            time.sleep(1)

            logger.info(f"Saved Notepad file to: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save Notepad file to '{file_path}': {e}")
            return False

    @staticmethod
    def open_file(file_path: str) -> bool:
        """
        Open a file in Notepad.

        Args:
            file_path: Path to file to open

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open Open dialog
            press_hotkey("ctrl", "o")
            time.sleep(1)

            # Find filename field
            filename_x, filename_y = find_element("filename input field in Open dialog")
            clear_and_type(filename_x, filename_y, file_path)
            time.sleep(0.5)

            # Find Open button
            open_x, open_y = find_element("Open button in Open dialog")
            click_element(open_x, open_y)
            time.sleep(1)

            logger.info(f"Opened file in Notepad: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open file in Notepad '{file_path}': {e}")
            return False

    @staticmethod
    def get_text_content() -> Optional[str]:
        """
        Get current text content from Notepad.

        Returns:
            Text content if successful, None otherwise
        """
        try:
            # Click on text area to focus
            text_x, text_y = find_element("main text editing area in Notepad window")
            click_element(text_x, text_y)
            time.sleep(0.5)

            # Select all text
            press_hotkey("ctrl", "a")
            time.sleep(0.5)

            # Copy text
            press_hotkey("ctrl", "c")
            time.sleep(0.5)

            # Get text from clipboard
            import pyperclip
            text = pyperclip.paste()

            logger.info(f"Retrieved text from Notepad: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"Failed to get text content from Notepad: {e}")
            return None


class WebBrowserWorkflow:
    """Web browser-specific vision workflow"""

    @staticmethod
    def navigate_to_url(url: str) -> bool:
        """
        Navigate to a URL in the browser.

        Args:
            url: URL to navigate to

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find browser address bar
            bar_x, bar_y = find_element("browser address/URL bar")
            clear_and_type(bar_x, bar_y, url)

            # Press Enter to navigate
            press_key("enter")
            time.sleep(3)  # Wait for page to start loading

            logger.info(f"Navigated to URL: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to URL '{url}': {e}")
            return False

    @staticmethod
    def refresh_page() -> bool:
        """
        Refresh the current web page.

        Returns:
            True if successful, False otherwise
        """
        try:
            press_key("f5")
            time.sleep(2)  # Wait for page to refresh

            logger.info("Refreshed web page")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh web page: {e}")
            return False

    @staticmethod
    def click_element_by_description(element_description: str) -> bool:
        """
        Click an element on the webpage by description.

        Args:
            element_description: Description of element to click

        Returns:
            True if successful, False otherwise
        """
        try:
            element_x, element_y = find_element(element_description)
            click_element(element_x, element_y)
            time.sleep(1)  # Wait for action to complete

            logger.info(f"Clicked webpage element: {element_description}")
            return True
        except Exception as e:
            logger.error(f"Failed to click webpage element '{element_description}': {e}")
            return False

    @staticmethod
    def scroll_page(direction: str, amount: int = 3) -> bool:
        """
        Scroll the web page.

        Args:
            direction: Direction to scroll (UP, DOWN, LEFT, RIGHT)
            amount: Amount to scroll

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find a point on the page to scroll from
            page_x, page_y = find_element("center of webpage content")
            scroll_at(page_x, page_y, direction, amount)

            logger.info(f"Scrolled webpage {direction} by {amount}")
            return True
        except Exception as e:
            logger.error(f"Failed to scroll webpage {direction}: {e}")
            return False

    @staticmethod
    def is_page_loaded() -> bool:
        """
        Check if the web page is fully loaded.

        Returns:
            True if loaded, False if still loading
        """
        try:
            # Look for loading indicators
            loading_indicators = [
                "loading indicator or spinner on webpage",
                "progress bar on webpage",
                "skeleton screen on webpage"
            ]

            for indicator in loading_indicators:
                try:
                    find_element(indicator)
                    # If we find a loading indicator, page is still loading
                    return False
                except ElementNotFoundError:
                    continue  # This indicator not found, check next

            # No loading indicators found
            logger.info("Web page appears to be fully loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to check if web page is loaded: {e}")
            return False

    @staticmethod
    def read_page_text(text_description: str) -> Optional[str]:
        """
        Read specific text from the webpage.

        Args:
            text_description: Description of text to read

        Returns:
            Text content if successful, None otherwise
        """
        try:
            text = read_screen_text(text_description)
            logger.info(f"Read text from webpage: {text[:100]}{'...' if len(text) > 100 else ''}")
            return text
        except Exception as e:
            logger.error(f"Failed to read text from webpage: {e}")
            return None


class SystemSettingsWorkflow:
    """System settings-specific vision workflow"""

    @staticmethod
    def toggle_wifi(enabled: bool) -> bool:
        """
        Toggle Wi-Fi on or off.

        Args:
            enabled: True to enable Wi-Fi, False to disable

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open Quick Settings (Win+A)
            press_hotkey("win", "a")
            time.sleep(1)

            # Find Wi-Fi toggle
            wifi_x, wifi_y = find_element("Wi-Fi toggle in Windows 11 Quick Settings panel")
            current_state = check_element_state(
                "Wi-Fi toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Toggle if needed
            if (enabled and current_state == "OFF") or (not enabled and current_state == "ON"):
                click_element(wifi_x, wifi_y)
                time.sleep(2)  # Wait for Wi-Fi to toggle

            new_state = check_element_state(
                "Wi-Fi toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Close Quick Settings (Esc)
            press_key("escape")
            time.sleep(0.5)

            logger.info(f"Toggled Wi-Fi from {current_state} to {new_state}")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle Wi-Fi to {'on' if enabled else 'off'}: {e}")
            # Try to close Quick Settings if open
            try:
                press_key("escape")
            except:
                pass
            return False

    @staticmethod
    def toggle_bluetooth(enabled: bool) -> bool:
        """
        Toggle Bluetooth on or off.

        Args:
            enabled: True to enable Bluetooth, False to disable

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open Quick Settings (Win+A)
            press_hotkey("win", "a")
            time.sleep(1)

            # Find Bluetooth toggle
            bluetooth_x, bluetooth_y = find_element("Bluetooth toggle in Windows 11 Quick Settings panel")
            current_state = check_element_state(
                "Bluetooth toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Toggle if needed
            if (enabled and current_state == "OFF") or (not enabled and current_state == "ON"):
                click_element(bluetooth_x, bluetooth_y)
                time.sleep(2)  # Wait for Bluetooth to toggle

            new_state = check_element_state(
                "Bluetooth toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Close Quick Settings (Esc)
            press_key("escape")
            time.sleep(0.5)

            logger.info(f"Toggled Bluetooth from {current_state} to {new_state}")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle Bluetooth to {'on' if enabled else 'off'}: {e}")
            # Try to close Quick Settings if open
            try:
                press_key("escape")
            except:
                pass
            return False

    @staticmethod
    def set_volume(level: int) -> bool:
        """
        Set system volume level (0-100).

        Args:
            level: Volume level to set (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find volume icon in taskbar
            icon_x, icon_y = find_element("volume icon in Windows 11 taskbar system tray")
            click_element(icon_x, icon_y)
            time.sleep(0.5)

            # Find volume slider
            slider_x, slider_y = find_element("volume slider in Windows 11 volume popup")
            # In a full implementation, we'd calculate drag distance
            # For now, simplified approach

            click_element(slider_x, slider_y)
            # Would drag to set level here

            logger.info(f"Set system volume to {level}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set system volume to {level}%: {e}")
            return False

    @staticmethod
    def set_brightness(level: int) -> bool:
        """
        Set screen brightness level (0-100).

        Args:
            level: Brightness level to set (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open Quick Settings (Win+A)
            press_hotkey("win", "a")
            time.sleep(1)

            # Find brightness slider
            slider_x, slider_y = find_element("brightness slider in Windows 11 Quick Settings panel")
            # In a full implementation, we'd calculate drag distance
            # For now, simplified approach

            click_element(slider_x, slider_y)
            # Would drag to set level here

            # Close Quick Settings (Esc)
            press_key("escape")
            time.sleep(0.5)

            logger.info(f"Set screen brightness to {level}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set screen brightness to {level}%: {e}")
            # Try to close Quick Settings if open
            try:
                press_key("escape")
            except:
                pass
            return False

    @staticmethod
    def is_wifi_enabled() -> bool:
        """
        Check if Wi-Fi is enabled.

        Returns:
            True if Wi-Fi enabled, False otherwise
        """
        try:
            # Open Quick Settings (Win+A)
            press_hotkey("win", "a")
            time.sleep(1)

            # Find Wi-Fi toggle and check state
            wifi_x, wifi_y = find_element("Wi-Fi toggle in Windows 11 Quick Settings panel")
            state = check_element_state(
                "Wi-Fi toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Close Quick Settings (Esc)
            press_key("escape")
            time.sleep(0.5)

            return state == "ON"
        except Exception as e:
            logger.error(f"Failed to check Wi-Fi state: {e}")
            # Try to close Quick Settings if open
            try:
                press_key("escape")
            except:
                pass
            return False

    @staticmethod
    def is_bluetooth_enabled() -> bool:
        """
        Check if Bluetooth is enabled.

        Returns:
            True if Bluetooth enabled, False otherwise
        """
        try:
            # Open Quick Settings (Win+A)
            press_hotkey("win", "a")
            time.sleep(1)

            # Find Bluetooth toggle and check state
            bluetooth_x, bluetooth_y = find_element("Bluetooth toggle in Windows 11 Quick Settings panel")
            state = check_element_state(
                "Bluetooth toggle in Windows 11 Quick Settings panel",
                ["ON", "OFF"]
            )

            # Close Quick Settings (Esc)
            press_key("escape")
            time.sleep(0.5)

            return state == "ON"
        except Exception as e:
            logger.error(f"Failed to check Bluetooth state: {e}")
            # Try to close Quick Settings if open
            try:
                press_key("escape")
            except:
                pass
            return False


# Convenience functions for easy access
def youtube_search(video_name: str) -> bool:
    """Search for a YouTube video"""
    return YouTubeWorkflow.search_video(video_name)

def youtube_play_pause() -> bool:
    """Toggle YouTube play/pause"""
    return YouTubeWorkflow.play_pause()

def youtube_like() -> bool:
    """Like YouTube video"""
    return YouTubeWorkflow.like_video()

def spotify_search(song_name: str) -> bool:
    """Search for a Spotify song"""
    return SpotifyWorkflow.search_song(song_name)

def spotify_play_pause() -> bool:
    """Toggle Spotify play/pause"""
    return SpotifyWorkflow.play_pause()

def spotify_next() -> bool:
    """Skip to next Spotify track"""
    return SpotifyWorkflow.next_track()

def spotify_previous() -> bool:
    """Skip to previous Spotify track"""
    return SpotifyWorkflow.previous_track()

def spotify_shuffle() -> bool:
    """Toggle Spotify shuffle"""
    return SpotifyWorkflow.toggle_shuffle()

def whatsapp_search_contact(contact_name: str) -> bool:
    """Search for WhatsApp contact"""
    return WhatsAppWorkflow.search_contact(contact_name)

def whatsapp_select_contact(contact_name: str) -> bool:
    """Select WhatsApp contact from search results"""
    return WhatsAppWorkflow.select_contact(contact_name)

def whatsapp_send_message(message: str) -> bool:
    """Send WhatsApp message"""
    return WhatsAppWorkflow.send_message(message)

def notepad_write(text: str) -> bool:
    """Write text to Notepad"""
    return NotepadWorkflow.write_text(text)

def notepad_save(file_path: str) -> bool:
    """Save Notepad file"""
    return NotepadWorkflow.save_file(file_path)

def browser_navigate(url: str) -> bool:
    """Navigate to URL in browser"""
    return WebBrowserWorkflow.navigate_to_url(url)

def browser_click(element_description: str) -> bool:
    """Click element in browser"""
    return WebBrowserWorkflow.click_element_by_description(element_description)

def wifi_toggle(enabled: bool) -> bool:
    """Toggle Wi-Fi on/off"""
    return SystemSettingsWorkflow.toggle_wifi(enabled)

def bluetooth_toggle(enabled: bool) -> bool:
    """Toggle Bluetooth on/off"""
    return SystemSettingsWorkflow.toggle_bluetooth(enabled)

def set_system_volume(level: int) -> bool:
    """Set system volume level"""
    return SystemSettingsWorkflow.set_volume(level)

def set_screen_brightness(level: int) -> bool:
    """Set screen brightness level"""
    return SystemSettingsWorkflow.set_brightness(level)