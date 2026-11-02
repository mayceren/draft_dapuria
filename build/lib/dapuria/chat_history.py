"""Local, scoped conversation storage; model/index data never enters this store."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

STATE_KEYS = ("messages", "phase", "pending", "latest_result")


class ChatHistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    owner_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    PRIMARY KEY (owner_id, id)
                )
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, owner_id: str, conversation_id: str, state: dict[str, Any]) -> None:
        messages = state.get("messages", [])
        if not messages:
            return
        snapshot = {key: state.get(key) for key in STATE_KEYS}
        payload = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        first_query = next((message["content"] for message in messages if message["role"] == "user"), "Percakapan")
        title = " ".join(first_query.split())[:72]
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO conversations (owner_id, id, title, created_at, updated_at, snapshot)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_id, id) DO UPDATE SET
                    updated_at = excluded.updated_at, snapshot = excluded.snapshot
            """, (owner_id, conversation_id, title, now, now, payload))

    def list(self, owner_id: str, search: str = "") -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("""
                SELECT id, title, created_at, updated_at FROM conversations
                WHERE owner_id = ? ORDER BY updated_at DESC, id
            """, (owner_id,)).fetchall()
        query = search.strip().casefold()
        return [dict(row) for row in rows if query in row["title"].casefold()]

    def load(self, owner_id: str, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot FROM conversations WHERE owner_id = ? AND id = ?",
                (owner_id, conversation_id),
            ).fetchone()
        if row is None:
            return None
        snapshot = json.loads(row["snapshot"])
        if (
            not isinstance(snapshot, dict)
            or not all(key in snapshot for key in STATE_KEYS)
            or not isinstance(snapshot.get("messages"), list)
            or snapshot.get("phase") not in {"await_query", "await_confirmation"}
        ):
            raise ValueError("Format riwayat percakapan tidak didukung.")
        if snapshot["phase"] == "await_confirmation" and not isinstance(snapshot.get("pending"), dict):
            raise ValueError("Data klarifikasi pada riwayat tidak lengkap.")
        return snapshot

    def rename(self, owner_id: str, conversation_id: str, title: str) -> None:
        title = " ".join(title.split())[:72]
        if not title:
            raise ValueError("Judul percakapan tidak boleh kosong.")
        with self._connect() as connection:
            connection.execute(
                "UPDATE conversations SET title = ? WHERE owner_id = ? AND id = ?",
                (title, owner_id, conversation_id),
            )

    def delete(self, owner_id: str, conversation_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM conversations WHERE owner_id = ? AND id = ?",
                (owner_id, conversation_id),
            )


def conversation_text(messages: list[dict[str, Any]]) -> str:
    lines = ["DAPURIA · Riwayat percakapan", ""]
    for message in messages:
        role = "Kamu" if message["role"] == "user" else "Dapuria"
        lines.extend([f"{role}:", message["content"], ""])
        for rank, recipe in enumerate((message.get("result") or {}).get("results", []), 1):
            lines.extend([f"Rekomendasi {rank}", recipe_text(recipe), ""])
    return "\n".join(lines)


def recipe_text(recipe: dict[str, Any]) -> str:
    names = recipe.get("ingredient_names") or list(dict.fromkeys(
        recipe.get("matched_recipe_items", []) + recipe.get("missing_items", [])
    ))
    missing = recipe.get("missing_items", [])
    return "\n".join([
        recipe.get("title") or "Resep tanpa judul", "", "BAHAN-BAHAN",
        *(f"- {name}" for name in names), "", "YANG PERLU DISIAPKAN",
        *(f"- {name}" for name in missing),
        *([] if missing else ["Tidak ada bahan tambahan yang tercatat."]),
        "", "LANGKAH MEMASAK",
        recipe.get("steps_text") or "Langkah memasak belum tersedia pada data resep ini.",
    ])
