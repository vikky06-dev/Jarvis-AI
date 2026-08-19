"""Isolate rule-parser failures with clean memory."""
import sys, re
sys.path.insert(0, ".")

from brain.memory import memory

memory.clear()

from brain.interpreter import _rule_parse

cases = [
    "Crank it up",
    "Dim this thing down",
    "Make it louder",
    "Pause",
    "Hold on",
    "Freeze",
    "Shh",
    "Volume thoda kam kar",
    "Wifi band kar",
    "Flip the Wi-Fi off",
    "Chuck that file in my Downloads",
    "Get Spotify going",
]

for cmd in cases:
    r = _rule_parse(cmd)
    print(f"{cmd!r:40} -> {r}")

print()
print("--- with memory pollution ---")
memory.add("open Chrome", {"action": "open_app", "target": "Chrome", "parameters": {}})
for cmd in ["Crank it up", "Make it louder", "Play it again"]:
    r = _rule_parse(cmd)
    print(f"{cmd!r:40} -> {r}")