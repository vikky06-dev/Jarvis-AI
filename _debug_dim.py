"""Debug: why 'Dim this thing down' doesn't match."""
import re

c = "dim this thing down"

tests = [
    (r"\b(dim|turn down|reduce) (?:this|the )?thing(?: down| off)?\b", "thing-down"),
    (r"\bdim\b.*?\bbrightness\b", "dim-brightness"),
    (r"\bdim\b", "bare-dim"),
]

for pat, name in tests:
    m = re.search(pat, c)
    print(f"{name}: {bool(m)} {m.group(0) if m else ''}")

# Check if the whole block even executes — trace through
from brain.memory import memory
memory.clear()
from brain.interpreter import _rule_parse
print("\nrule_parse:", _rule_parse("Dim this thing down"))

# Try simpler: what if the issue is that it's being caught by something earlier?
for pat in [
    r"\b(kill|shut up|be quiet|mute) (?:the )?volume\b",
    r"\b(crank|turn|make|amp) (?:it |the |things? )?up\b",
    r"\bmake it (?:louder|quieter|softer)\b",
    r"\b(louder|raise|increase) (?:the )?volume\b",
    r"\bvolume (?:thoda|thodi|thora|zara)? ?(?:up|badha|badhao|barha|barhao)\b",
]:
    print(f"prev: {pat!r} -> {bool(re.search(pat, c))}")