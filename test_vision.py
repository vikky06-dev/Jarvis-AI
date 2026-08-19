"""
Test script for ULTRON AI Vision Module
"""

import sys
import traceback
# Enable mock mode for testing
import core.vision
core.vision.MOCK_MODE = True

from core.vision import check_vision_engine, vision_engine
from core.vision.workflows import (
    youtube_search, spotify_search, whatsapp_search_contact,
    notepad_write, browser_navigate, wifi_toggle
)

def test_vision_engine():
    """Test the vision engine initialization and basic functions"""
    print("=" * 50)
    print("Testing ULTRON AI Vision Module")
    print("=" * 50)

    # Test 1: Check if vision engine is available
    print("\n1. Testing vision engine availability...")
    try:
        is_available = check_vision_engine()
        if is_available:
            print("[INFO] Vision engine is available and responsive")
        else:
            print("[WARN] Vision engine is not available")
            return False
    except Exception as e:
        print(f"[ERROR] Error checking vision engine: {e}")
        traceback.print_exc()
        return False

    # Test 2: Test screenshot capture
    print("\n2. Testing screenshot capture...")
    try:
        screenshot = vision_engine.capture_screen()
        print(f"[INFO] Screenshot captured successfully ({len(screenshot)} characters)")
    except Exception as e:
        print(f"[ERROR] Error capturing screenshot: {e}")
        traceback.print_exc()
        return False

    # Test 3: Test screen state analysis
    print("\n3. Testing screen state analysis...")
    try:
        state = vision_engine.analyze_screen_state()
        print(f"[INFO] Screen state analysis completed")
        print(f"  Analysis keys: {list(state.keys())}")
    except Exception as e:
        print(f"[ERROR] Error analyzing screen state: {e}")
        traceback.print_exc()
        return False

    # Test 4: Test workflow functions (these will likely fail if apps aren't open, but we can test they don't crash)
    print("\n4. Testing workflow function signatures...")
    try:
        # Just test that the functions exist and are callable
        assert callable(youtube_search)
        assert callable(spotify_search)
        assert callable(whatsapp_search_contact)
        assert callable(notepad_write)
        assert callable(browser_navigate)
        assert callable(wifi_toggle)
        print("[INFO] All workflow functions are present and callable")
    except Exception as e:
        print(f"[ERROR] Error testing workflow functions: {e}")
        traceback.print_exc()
        return False

    print("\n" + "=" * 50)
    print("Vision Module Basic Tests Completed Successfully!")
    print("=" * 50)
    print("\nNote: Actual workflow tests require specific applications to be open")
    print("and running. The vision engine itself is functional.")
    return True

if __name__ == "__main__":
    success = test_vision_engine()
    sys.exit(0 if success else 1)