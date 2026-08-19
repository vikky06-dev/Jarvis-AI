"""ULTRON AI — Memory subsystem.

Two tiers:
  1. Short-term: in-memory deque of the last N commands+intents (pronoun resolution).
  2. Long-term: ChromaDB semantic store + SQLite log for persistence across sessions.

Also handles user preference learning (Section 4.3) and preference application.
"""
import json
import os
import sqlite3
from collections import deque
from datetime import datetime
from pathlib import Path

from config import settings


# ── Short-term memory (session-scoped) ──────────────────────────

class ShortTermMemory:
    """Rolling window of recent commands+intents for pronoun resolution."""

    def __init__(self, maxlen: int = settings.CONTEXT_WINDOW):
        self.history: deque = deque(maxlen=maxlen)

    def add(self, command: str, intent: dict) -> None:
        self.history.append({
            "command": command,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })

    def last_intent(self) -> dict | None:
        return self.history[-1]["intent"] if self.history else None

    def last_target(self) -> str | None:
        """Most recent non-empty target — what 'it'/'that' refers to."""
        for item in reversed(self.history):
            target = item["intent"].get("target")
            if target:
                return target
        return None

    def last_action(self) -> str | None:
        if self.history:
            return self.history[-1]["intent"].get("action")
        return None

    def context_lines(self) -> list[str]:
        """Render history for the LLM prompt."""
        return [
            f'- "{h["command"]}" -> {h["intent"].get("action")} {h["intent"].get("target") or ""}'.strip()
            for h in self.history
        ]

    def get(self, index: int) -> dict | None:
        """Get a history entry by index (0 = oldest)."""
        if -len(self.history) <= index < len(self.history):
            return self.history[index]
        return None

    def clear(self) -> None:
        self.history.clear()


# ── Long-term memory (persistent) ─────────────────────────────────

class LongTermMemory:
    """Persistent memory using ChromaDB for semantic search + SQLite for logging.

    Falls back gracefully if ChromaDB is not installed (pure SQLite mode).
    """

    def __init__(self, db_dir: Path = settings.TEMP_DIR):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = self.db_dir / "ultrong_memory.db"
        self._chroma_client = None
        self._chroma_collection = None
        self._init_sqlite()
        self._init_chroma()

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,        -- 'fact', 'preference', 'command', 'conversation'
                content TEXT NOT NULL,
                metadata TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                name TEXT PRIMARY KEY,
                phone TEXT,
                email TEXT,
                whatsapp TEXT,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _init_chroma(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.db_dir / "chroma"),
                settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
            )
            # Get or create the collection
            try:
                self._chroma_collection = self._chroma_client.get_collection("ultron_memories")
            except Exception:
                self._chroma_collection = self._chroma_client.create_collection("ultron_memories")
        except Exception:
            # ChromaDB not available — use SQLite-only mode
            self._chroma_client = None
            self._chroma_collection = None

    # ── Fact storage & retrieval ──

    def store_fact(self, content: str, metadata: dict | None = None) -> int:
        """Store a fact in long-term memory."""
        conn = sqlite3.connect(str(self.sqlite_path))
        row_id = conn.execute(
            "INSERT INTO memories (type, content, metadata) VALUES (?, ?, ?)",
            ("fact", content, json.dumps(metadata or {})),
        ).lastrowid
        conn.commit()
        conn.close()

        # Also store in ChromaDB for semantic search
        if self._chroma_collection:
            try:
                self._chroma_collection.add(
                    documents=[content],
                    metadatas=[metadata or {}],
                    ids=[f"fact_{row_id}"],
                )
            except Exception:
                pass
        return row_id

    def recall_relevant(self, query: str, top_k: int = 5) -> str:
        """Semantic search for relevant memories. Returns a formatted string."""
        # Try ChromaDB first
        if self._chroma_collection:
            try:
                results = self._chroma_collection.query(
                    query_texts=[query],
                    n_results=top_k,
                )
                docs = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                if docs:
                    lines = []
                    for doc, meta in zip(docs, metadatas):
                        lines.append(f"- {doc}")
                    return "; ".join(lines)
            except Exception:
                pass

        # SQLite fallback: fuzzy LIKE search on recent facts
        conn = sqlite3.connect(str(self.sqlite_path))
        cursor = conn.execute(
            "SELECT content, metadata FROM memories WHERE type = 'fact' "
            "ORDER BY created DESC LIMIT ?",
            (top_k,),
        )
        rows = cursor.fetchall()
        conn.close()
        if rows:
            return "; ".join(r[0] for r in rows)
        return ""

    def recall_all_facts(self) -> list[dict]:
        """Retrieve all stored facts (for review)."""
        conn = sqlite3.connect(str(self.sqlite_path))
        cursor = conn.execute(
            "SELECT id, content, metadata, created FROM memories WHERE type = 'fact' "
            "ORDER BY created DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "content": r[1], "metadata": json.loads(r[2] or "{}"), "created": r[3]}
            for r in rows
        ]

    # ── Preference learning (Section 4.3) ──

    def store_preference(self, key: str, value: str) -> None:
        """Store or update a user preference."""
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value, updated) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, str(value)),
        )
        conn.commit()
        conn.close()

        # Also store in ChromaDB for semantic recall
        if self._chroma_collection:
            try:
                self._chroma_collection.add(
                    documents=[f"Preference: {key} = {value}"],
                    metadatas=[{"type": "preference", "key": key}],
                    ids=[f"pref_{key}"],
                )
            except Exception:
                pass

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a user preference by key."""
        conn = sqlite3.connect(str(self.sqlite_path))
        cursor = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default

    def get_all_preferences(self) -> dict:
        """Retrieve all stored preferences."""
        conn = sqlite3.connect(str(self.sqlite_path))
        cursor = conn.execute("SELECT key, value FROM preferences")
        rows = cursor.fetchall()
        conn.close()
        return dict(rows)

    # ── Contact management ──

    def add_contact(self, name: str, phone: str = None, email: str = None,
                    whatsapp: str = None, notes: str = None) -> None:
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.execute(
            "INSERT OR REPLACE INTO contacts (name, phone, email, whatsapp, notes) VALUES (?, ?, ?, ?, ?)",
            (name.lower(), phone, email, whatsapp, notes),
        )
        conn.commit()
        conn.close()

    def get_contact(self, name: str) -> dict | None:
        conn = sqlite3.connect(str(self.sqlite_path))
        cursor = conn.execute(
            "SELECT name, phone, email, whatsapp, notes FROM contacts WHERE name LIKE ?",
            (f"%{name.lower()}%",),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"name": row[0], "phone": row[1], "email": row[2],
                    "whatsapp": row[3], "notes": row[4]}
        return None

    # ── Conversation logging ──

    def log_conversation(self, role: str, text: str, intent: dict | None = None) -> None:
        """Persist a conversation turn to long-term memory."""
        conn = sqlite3.connect(str(self.sqlite_path))
        conn.execute(
            "INSERT INTO memories (type, content, metadata) VALUES (?, ?, ?)",
            ("conversation", text, json.dumps({"role": role, "intent": intent or {}})),
        )
        conn.commit()
        conn.close()


# ── Combined memory facade ─────────────────────────────────────────

# Module-level singletons shared by interpreter + main loop.
short_term = ShortTermMemory()
long_term = LongTermMemory()


class Memory:
    """Unified memory interface combining short-term + long-term storage.

    This class is the public interface used by the rest of the codebase.
    It delegates to short_term (deque) and long_term (SQLite + ChromaDB).
    """

    def add(self, command: str, intent: dict) -> None:
        """Add a command+intent to short-term memory and persist to long-term."""
        short_term.add(command, intent)
        long_term.log_conversation("user", command, intent)

    def last_intent(self) -> dict | None:
        return short_term.last_intent()

    def last_target(self) -> str | None:
        return short_term.last_target()

    def last_action(self) -> str | None:
        return short_term.last_action()

    def context_lines(self) -> list[str]:
        return short_term.context_lines()

    def get(self, index: int) -> dict | None:
        return short_term.get(index)

    def clear(self) -> None:
        short_term.clear()

    # Long-term passthroughs
    def store_fact(self, content: str, metadata: dict | None = None) -> int:
        return long_term.store_fact(content, metadata)

    def recall_relevant(self, query: str, top_k: int = 5) -> str:
        return long_term.recall_relevant(query, top_k)

    def recall_all_facts(self) -> list[dict]:
        return long_term.recall_all_facts()

    def store_preference(self, key: str, value: str) -> None:
        long_term.store_preference(key, value)

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        return long_term.get_preference(key, default)

    def get_all_preferences(self) -> dict:
        return long_term.get_all_preferences()

    def add_contact(self, name: str, phone: str = None, email: str = None,
                    whatsapp: str = None, notes: str = None) -> None:
        long_term.add_contact(name, phone, email, whatsapp, notes)

    def get_contact(self, name: str) -> dict | None:
        return long_term.get_contact(name)

    def log_conversation(self, role: str, text: str, intent: dict | None = None) -> None:
        long_term.log_conversation(role, text, intent)


# Backward-compatible singleton (existing code imports `memory`)
memory = Memory()
