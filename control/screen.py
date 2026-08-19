"""Screen interaction: screenshot, OCR, click-anything-by-label.

pytesseract is the primary OCR (fast); easyocr is an optional fallback
loaded lazily only if tesseract fails, since easyocr pulls in torch.
"""
import sys
from datetime import datetime

import pyautogui
from PIL import Image

from config import settings
from . import mouse


def _init_tesseract():
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_EXE
    return pytesseract


def take_screenshot(save: bool = True) -> tuple[Image.Image, str | None]:
    img = pyautogui.screenshot()
    path = None
    if save:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = str(settings.SCREENSHOT_DIR / f"jarvis_screenshot_{stamp}.png")
        img.save(path)
    return img, path


def _ocr_words_tesseract(img: Image.Image) -> list[dict]:
    pytesseract = _init_tesseract()
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text or int(data["conf"][i]) < settings.OCR_CONFIDENCE_MIN:
            continue
        words.append({
            "text": text,
            "x": data["left"][i] + data["width"][i] // 2,
            "y": data["top"][i] + data["height"][i] // 2,
            "line": (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
        })
    return words


def _ocr_words_easyocr(img: Image.Image) -> list[dict]:
    import numpy as np
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = reader.readtext(np.array(img))
    words = []
    for bbox, text, conf in results:
        if conf < 0.3:
            continue
        xs = [p[0] for p in bbox]; ys = [p[1] for p in bbox]
        words.append({
            "text": text.strip(),
            "x": int(sum(xs) / 4),
            "y": int(sum(ys) / 4),
            "line": (0, 0, 0),
        })
    return words


def ocr_words(img: Image.Image | None = None) -> list[dict]:
    if img is None:
        img, _ = take_screenshot(save=False)
    try:
        words = _ocr_words_tesseract(img)
        if words:
            return words
    except Exception as e:
        print(f"[screen] tesseract failed: {e}", file=sys.stderr)
    try:
        return _ocr_words_easyocr(img)
    except Exception as e:
        print(f"[screen] easyocr fallback failed: {e}", file=sys.stderr)
        return []


def find_text(label: str, img: Image.Image | None = None) -> tuple[int, int] | None:
    """Locate `label` on screen; supports multi-word labels within one OCR line."""
    label_words = label.lower().split()
    words = ocr_words(img)
    if not words:
        return None

    # single word: direct match, prefer exact over substring
    if len(label_words) == 1:
        target = label_words[0]
        exact = [w for w in words if w["text"].lower().strip(":.,") == target]
        subs = [w for w in words if target in w["text"].lower()]
        pick = (exact or subs)
        return (pick[0]["x"], pick[0]["y"]) if pick else None

    # multi word: search word sequences within the same OCR line
    from itertools import groupby
    for _, group in groupby(sorted(words, key=lambda w: w["line"]), key=lambda w: w["line"]):
        line = list(group)
        texts = [w["text"].lower().strip(":.,") for w in line]
        for i in range(len(texts) - len(label_words) + 1):
            if texts[i:i + len(label_words)] == label_words:
                span = line[i:i + len(label_words)]
                return (sum(w["x"] for w in span) // len(span),
                        sum(w["y"] for w in span) // len(span))
    # loose fallback: first word only
    return find_text(label_words[0], img)


def click_text(label: str, button: str = "left", clicks: int = 1) -> str:
    pos = find_text(label)
    if pos is None:
        return f"I couldn't find {label} on the screen"
    mouse.click(pos[0], pos[1], button=button, clicks=clicks)
    return f"Clicked {label}"


def scroll_until_found(label: str, direction: str = "down", max_scrolls: int = 10) -> str:
    for _ in range(max_scrolls):
        if find_text(label):
            return click_text(label)
        mouse.scroll(direction, 5)
    return f"Couldn't find {label} after scrolling"


if __name__ == "__main__":
    img, path = take_screenshot()
    words = ocr_words(img)
    print(f"screenshot saved: {path}")
    print(f"OCR found {len(words)} words; sample: {[w['text'] for w in words[:10]]}")
