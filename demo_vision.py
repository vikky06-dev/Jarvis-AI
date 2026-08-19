"""
Demonstration of ULTRON AI Vision Module
Shows how to use the vision capabilities in mock mode
"""

import core.vision

def demo_vision_capabilities():
    """Demonstrate various vision capabilities"""
    print("=" * 60)
    print("ULTRON AI Vision Module Demonstration")
    print("=" * 60)

    # Enable mock mode for demonstration
    core.vision.MOCK_MODE = True
    print("[CONFIG] Mock mode enabled\n")

    # Import functions we'll use
    from core.vision import (
        find_element, verify_action, read_screen_text,
        check_element_state, analyze_screen_state
    )
    from core.vision.workflows import (
        youtube_search, spotify_search, notepad_write,
        browser_navigate, wifi_toggle
    )

    print("[DEMO] Testing core vision functions:")
    print("-" * 40)

    # Test element finding
    try:
        coords = find_element("Play button")
        print(f"[FOUND] Play button at coordinates: {coords}")
    except Exception as e:
        print(f"[ERROR] Failed to find element: {e}")

    # Test text reading
    try:
        text = read_screen_text("Currently playing song")
        print(f"[TEXT] Currently playing: '{text}'")
    except Exception as e:
        print(f"[ERROR] Failed to read text: {e}")

    # Test state checking
    try:
        state = check_element_state("Wi-Fi toggle", ["ENABLED", "DISABLED"])
        print(f"[STATE] Wi-Fi toggle is: {state}")
    except Exception as e:
        print(f"[ERROR] Failed to check state: {e}")

    # Test screen state analysis
    try:
        state = analyze_screen_state()
        print(f"[ANALYSIS] Screen analysis completed with {len(state)} components")
    except Exception as e:
        print(f"[ERROR] Failed to analyze screen: {e}")

    print("\n[DEMO] Testing workflow functions:")
    print("-" * 40)

    # Test YouTube search
    try:
        result = youtube_search("Never Gonna Give You Up")
        print(f"[YOUTUBE] Search result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"[ERROR] YouTube search failed: {e}")

    # Test Spotify search
    try:
        result = spotify_search("Blinding Lights")
        print(f"[SPOTIFY] Search result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"[ERROR] Spotify search failed: {e}")

    # Test Notepad write
    try:
        result = notepad_write("Hello, this is a test document from ULTRON AI!")
        print(f"[NOTEPAD] Write result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"[ERROR] Notepad write failed: {e}")

    # Test browser navigation
    try:
        result = browser_navigate("https://www.example.com")
        print(f"[BROWSER] Navigation result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"[ERROR] Browser navigation failed: {e}")

    # Test Wi-Fi toggle
    try:
        result = wifi_toggle(False)
        print(f"[WIFI] Toggle result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"[ERROR] Wi-Fi toggle failed: {e}")

    print("\n" + "=" * 60)
    print("Demonstration completed successfully!")
    print("In a real environment with Ollama and qwen3-vl:4b running,")
    print("these functions would interact with actual screen elements.")
    print("=" * 60)

if __name__ == "__main__":
    demo_vision_capabilities()