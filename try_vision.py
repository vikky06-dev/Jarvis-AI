import core.vision
core.vision.MOCK_MODE = False  # This line turns on "practice mode"

from core.vision.workflows import youtube_search, notepad_write

# Try it out!
youtube_search("relaxing music")   # Pretends to search YouTube
notepad_write("Hello from my computer!")  # Pretends to type in Notepad
print("Script completed successfully!")