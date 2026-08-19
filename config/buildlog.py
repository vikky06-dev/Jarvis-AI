"""Append-only build log used during autonomous build & self-test."""
from datetime import datetime
from .settings import BUILD_LOG

VALID = {"BUILDING", "PASSED", "FAILED", "FIXED", "SKIPPED", "DEGRADED"}


def log(module: str, status: str, notes: str = "") -> None:
    status = status.upper()
    if status not in VALID:
        status = "BUILDING"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] [{module}] [{status}] {notes}\n"
    with open(BUILD_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")
