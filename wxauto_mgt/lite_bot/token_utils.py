from __future__ import annotations

import math
from typing import Iterable


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def estimate_message_tokens(message: dict[str, object]) -> int:
    content = message.get("content")
    if isinstance(content, list):
        tokens = 0
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                tokens += estimate_tokens(str(item.get("text", "")))
        return tokens
    return estimate_tokens(str(content or ""))


def estimate_messages_tokens(messages: Iterable[dict[str, str]]) -> int:
    return sum(estimate_message_tokens(msg) for msg in messages)


def truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    max_chars = max_tokens * 4
    return text[:max_chars]
