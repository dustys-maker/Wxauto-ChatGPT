from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class StoredImage:
    relative_path: str
    sha256: str
    size: int
    mime_type: str


class SessionIndex:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.index_path = base_dir / "session_index.json"
        self.data: dict[str, Any] = {"version": 1, "sessions": {}}
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        self.data = json.loads(self.index_path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_or_create(self, scope: str, key: str, display_name: str) -> str:
        sessions = self.data.setdefault("sessions", {})
        session_key = f"{scope}:{key}"
        if session_key in sessions:
            return sessions[session_key]["id"]
        session_id = hashlib.sha1(session_key.encode("utf-8")).hexdigest()[:16]
        sessions[session_key] = {
            "id": session_id,
            "display_name": display_name,
            "scope": scope,
            "key": key,
        }
        self.save()
        return session_id


class SessionStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.index = SessionIndex(base_dir)

    def resolve_session(self, scope: str, key: str, display_name: str) -> str:
        return self.index.get_or_create(scope, key, display_name)

    def _session_dir(self, scope: str, session_id: str) -> Path:
        return self.base_dir / scope / session_id

    def append_history(self, scope: str, session_id: str, record: dict[str, Any]) -> None:
        session_dir = self._session_dir(scope, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        history_path = session_dir / "history.jsonl"
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

    def load_history(self, scope: str, session_id: str) -> list[dict[str, Any]]:
        history_path = self._session_dir(scope, session_id) / "history.jsonl"
        if not history_path.exists():
            return []
        records: list[dict[str, Any]] = []
        with history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def save_image(
        self,
        scope: str,
        session_id: str,
        image_bytes: bytes,
        mime_type: str,
        message_id: str | None,
    ) -> StoredImage:
        session_dir = self._session_dir(scope, session_id)
        images_dir = session_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256(image_bytes).hexdigest()
        extension = mime_type.split("/")[-1] if "/" in mime_type else "bin"
        stable_name = message_id or sha256[:16]
        filename = f"{stable_name}.{extension}"
        target_path = images_dir / filename

        if not target_path.exists():
            target_path.write_bytes(image_bytes)

        relative_path = os.path.relpath(target_path, self.base_dir)
        return StoredImage(
            relative_path=relative_path,
            sha256=sha256,
            size=len(image_bytes),
            mime_type=mime_type,
        )
