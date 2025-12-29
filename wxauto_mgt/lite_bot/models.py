from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IncomingMessage:
    message_id: str
    timestamp: float
    sender_id: str
    sender_name: str
    content: str | None
    msg_type: str  # text | image
    is_group: bool
    group_id: str | None = None
    group_name: str | None = None
    is_at: bool = False
    conversation_id: str | None = None
    image_bytes: bytes | None = None
    image_name: str | None = None
    image_mime: str | None = None
    raw: dict[str, Any] | None = None


@dataclass
class SessionInfo:
    scope: str  # private | group
    session_id: str
    session_key: str
    display_name: str
