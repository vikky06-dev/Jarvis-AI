"""Diagnostic: trace failing NLP commands through the rule parser."""
import sys, re, traceback
sys.path.insert(0, ".")

from brain.nlp import extract_intent, split_compound, normalize_transcription, detect_language
from brain.interpreter import _rule_parse, parse

failing = [
    "Get Spotify going",
    "I want to listen to Spotify",
    "Pause",
    "Hold on",
    "Pause that",
    "Can you pause for a second?",
    "Freeze",
    "Shh",
    "Crank it up",
    "Dim this thing down",
    "Make it louder",
    "Volume thoda kam kar",
    "YouTube pe koi lo-fi daal",
    "Wifi band kar",
    "Notepad mein likh: test",
    "Brightness thodi badha",
    "Ye file Desktop pe save kar",
    "Flip the Wi-Fi off",
    "Chuck that file in my Downloads",
]

for cmd in failing:
    print(f"\n### {cmd!r}")
    try:
        norm = normalize_transcription(cmd)
        print(f"  normalized: {norm!r}")
        print(f"  lang: {detect_language(cmd)}")
        parts = split_compound(cmd)
        print(f"  split_compound: {parts}")
        ruled = _rule_parse(cmd)
        print(f"  _rule_parse: {ruled}")
        result = extract_intent(cmd)
        print(f"  extract_intent actions: {result.get('actions')}  conf={result.get('confidence')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()