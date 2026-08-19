"""Test individual regexes."""
import sys, re
sys.path.insert(0, ".")

from brain.memory import memory

memory.clear()

from brain.interpreter import _rule_parse

# Test the slang regex directly
c = "crank it up"
print("1:", bool(re.search(r"\b(crank|turn|make) (?:it|the )?up\b", c)))

c2 = "volume thoda kam kar"
print("volume kam check:", bool(re.search(r"\bvolume (?:kam|low)", c2)))

# Trace what _rule_parse does step by step
import inspect
src = inspect.getsource(_rule_parse)
# Print the first 60 lines of the function
for i, line in enumerate(src.split("\n")[:60], 1):
    print(f"{i:3}| {line}")