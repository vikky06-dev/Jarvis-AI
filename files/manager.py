"""File & folder management by voice.

Known-location names ("Desktop", "Downloads") resolve to user folders;
deletes go to a jarvis trash folder instead of permanent removal.
"""
import os
import shutil
import time
from pathlib import Path

from config import settings

HOME = Path.home()
KNOWN_DIRS = {
    "desktop": HOME / "Desktop",
    "downloads": HOME / "Downloads",
    "documents": HOME / "Documents",
    "pictures": HOME / "Pictures",
    "music": HOME / "Music",
    "videos": HOME / "Videos",
    "home": HOME,
}
TRASH = settings.TEMP_DIR / "trash"
RECENT_LOG = settings.TEMP_DIR / "recent_files.txt"


def resolve_dir(name: str | None) -> Path:
    if not name:
        return KNOWN_DIRS["desktop"]
    name = name.strip()
    # A filename tacked onto the folder ("Documents/report.pdf") — keep the dir part.
    head = name.replace("\\", "/").split("/")[0].lower()
    if head in KNOWN_DIRS:
        return KNOWN_DIRS[head]
    p = Path(name)
    if p.is_absolute():
        return p
    # Unknown relative name: treat as a folder under home, never under CWD.
    return HOME / name


def _resolve_file(name: str, search_dirs: list[Path] | None = None) -> Path | None:
    """Find a file by name in the common user dirs (non-recursive first, then shallow)."""
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    dirs = search_dirs or list(KNOWN_DIRS.values())
    for d in dirs:
        cand = d / name
        if cand.exists():
            return cand
    # shallow recursive pass
    for d in dirs:
        if not d.exists():
            continue
        for cand in d.glob(f"**/{name}"):
            return cand
    return None


def _remember(path: Path) -> None:
    with open(RECENT_LOG, "a", encoding="utf-8") as f:
        f.write(str(path) + "\n")


def create_folder(name: str, location: str | None = None) -> str:
    target = resolve_dir(location) / name
    target.mkdir(parents=True, exist_ok=True)
    return f"Created folder {name} in {location or 'Desktop'}"


def create_file(name: str, location: str | None = None) -> str:
    target = resolve_dir(location) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=True)
    _remember(target)
    return f"Created file {name}"


def delete_path(name: str) -> str:
    target = _resolve_file(name)
    if not target:
        return f"I couldn't find {name}"
    TRASH.mkdir(parents=True, exist_ok=True)
    dest = TRASH / f"{int(time.time())}_{target.name}"
    shutil.move(str(target), str(dest))
    return f"Moved {name} to the jarvis trash folder"


def move_file(name: str, source_dir: str, dest_dir: str) -> str:
    src = resolve_dir(source_dir) / name
    if not src.exists():
        found = _resolve_file(name, [resolve_dir(source_dir)])
        if not found:
            return f"I couldn't find {name} in {source_dir}"
        src = found
    dst_dir = resolve_dir(dest_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst_dir / src.name))
    return f"Moved {name} from {source_dir} to {dest_dir}"


def copy_file(name: str, source_dir: str, dest_dir: str) -> str:
    src = resolve_dir(source_dir) / name
    if not src.exists():
        return f"I couldn't find {name} in {source_dir}"
    dst_dir = resolve_dir(dest_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst_dir / src.name))
    return f"Copied {name} to {dest_dir}"


def rename_file(name: str, new_name: str) -> str:
    target = _resolve_file(name)
    if not target:
        return f"I couldn't find {name}"
    target.rename(target.with_name(new_name))
    return f"Renamed {name} to {new_name}"


def open_file(name: str) -> str:
    target = _resolve_file(name)
    if not target:
        return f"I couldn't find {name}"
    os.startfile(str(target))
    _remember(target)
    return f"Opening {target.name}"


def open_recent() -> str:
    if not RECENT_LOG.exists():
        return "I don't have a record of recent files yet"
    lines = RECENT_LOG.read_text(encoding="utf-8").strip().splitlines()
    for line in reversed(lines):
        p = Path(line)
        if p.exists():
            os.startfile(str(p))
            return f"Opening {p.name}"
    return "None of the recent files exist anymore"


def search_file(name: str, root: str = "C:\\") -> str:
    """Search common user dirs first, then walk the drive with a time cap."""
    quick = _resolve_file(name)
    if quick:
        return f"Found it at {quick}"
    matches = []
    deadline = time.time() + 20
    for dirpath, dirnames, filenames in os.walk(root):
        # skip noisy system dirs
        dirnames[:] = [d for d in dirnames
                       if d.lower() not in ("windows", "$recycle.bin", "programdata",
                                            "node_modules", "appdata", ".git")]
        for f in filenames:
            if name.lower() in f.lower():
                matches.append(os.path.join(dirpath, f))
                if len(matches) >= 5:
                    break
        if len(matches) >= 5 or time.time() > deadline:
            break
    if not matches:
        return f"I couldn't find any file matching {name}"
    return "Found: " + "; ".join(matches[:3])


def read_file(name: str) -> str:
    target = _resolve_file(name)
    if not target:
        return f"I couldn't find {name}"
    if target.suffix.lower() not in (".txt", ".md", ".log", ".py", ".json"):
        return f"I can only read text files aloud, and {target.name} isn't one"
    text = target.read_text(encoding="utf-8", errors="replace")
    words = text.split()
    snippet = " ".join(words[:120])
    more = f" ...and {len(words) - 120} more words" if len(words) > 120 else ""
    return f"{target.name} says: {snippet}{more}"


def list_folder(name: str) -> str:
    d = resolve_dir(name)
    if not d.exists():
        return f"I couldn't find a folder called {name}"
    entries = sorted(d.iterdir(), key=lambda p: p.is_file())[:15]
    if not entries:
        return f"The {name} folder is empty"
    listing = ", ".join(e.name + ("/" if e.is_dir() else "") for e in entries)
    return f"In {name}: {listing}"


if __name__ == "__main__":
    print(create_folder("jarvis_test_tmp", "Desktop"))
    print(delete_path("jarvis_test_tmp"))
