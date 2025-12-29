from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any

from wxauto_mgt.lite_bot.config import BotConfig
from wxauto_mgt.lite_bot.llm_client import LlmClient
from wxauto_mgt.lite_bot.models import IncomingMessage, SessionInfo
from wxauto_mgt.lite_bot.rate_limit import CooldownManager, DedupeCache, FailureTracker
from wxauto_mgt.lite_bot.storage import SessionStore
from wxauto_mgt.lite_bot.token_utils import (
    estimate_messages_tokens,
    estimate_tokens,
    truncate_text_to_tokens,
)

logger = logging.getLogger("wxauto_lite_bot")


class WxAutoBot:
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        base_dir = Path(config.storage.base_dir)
        self.store = SessionStore(base_dir)
        self.client = LlmClient(config.api)
        self.dedupe = DedupeCache(config.dedupe.window_seconds)
        self.session_cooldown = CooldownManager(config.rate_limit.session_cooldown_seconds)
        self.user_cooldown = CooldownManager(config.rate_limit.user_cooldown_seconds)
        self.failure_tracker = FailureTracker(
            config.failure.max_consecutive_failures,
            config.failure.cooldown_seconds,
        )
        self.vision_cache: dict[str, str] = {}

    def handle_message(self, msg: IncomingMessage, adapter: Any) -> None:
        if self._is_self_message(msg):
            logger.debug("skip self message: %s", msg.message_id)
            return

        session = self._resolve_session(msg)
        unique_key = msg.message_id or self._hash_content(msg)
        if self.dedupe.seen_recently(unique_key):
            logger.info("dedupe hit: %s", unique_key)
            return

        if self.failure_tracker.is_blocked(session.session_id):
            logger.warning("session blocked due to failures: %s", session.session_id)
            return

        should_reply = self._should_trigger(msg)
        logger.info(
            "message received scope=%s sender=%s trigger=%s",
            session.scope,
            msg.sender_name,
            should_reply,
        )

        image_meta = None
        if msg.msg_type == "image" and msg.image_bytes and msg.image_mime:
            image_meta = self.store.save_image(
                session.scope,
                session.session_id,
                msg.image_bytes,
                msg.image_mime,
                msg.message_id,
            )

        self._append_history(msg, session, image_meta)

        if not should_reply:
            return

        if self.session_cooldown.in_cooldown(session.session_id):
            logger.info("session cooldown: %s", session.session_id)
            return
        if self.user_cooldown.in_cooldown(msg.sender_id):
            logger.info("user cooldown: %s", msg.sender_id)
            return

        response_text = self._generate_reply(msg, session, image_meta)
        if response_text:
            adapter.send_text(session, response_text)
            self._append_reply(session, response_text)

    def _is_self_message(self, msg: IncomingMessage) -> bool:
        if not self.config.self_user_id:
            return False
        return msg.sender_id == self.config.self_user_id

    def _resolve_session(self, msg: IncomingMessage) -> SessionInfo:
        scope = "group" if msg.is_group else "private"
        if msg.conversation_id:
            session_key = msg.conversation_id
        elif msg.is_group:
            session_key = msg.group_id or msg.group_name or msg.sender_id
        else:
            session_key = msg.sender_id
        display_name = msg.group_name if msg.is_group else msg.sender_name
        session_id = self.store.resolve_session(scope, session_key, display_name)
        return SessionInfo(
            scope=scope,
            session_id=session_id,
            session_key=session_key,
            display_name=display_name,
        )

    def _hash_content(self, msg: IncomingMessage) -> str:
        base = f"{msg.sender_id}:{msg.content}:{msg.timestamp}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    def _should_trigger(self, msg: IncomingMessage) -> bool:
        if msg.is_group:
            if self.config.trigger.group_mode == "mention_keyword":
                return msg.is_at and self._match_keywords(msg.content, self.config.trigger.group_keywords)
            return msg.is_at

        if self.config.trigger.private_mode == "always":
            return True
        if self.config.trigger.private_mode == "keyword":
            return self._match_keywords(msg.content, self.config.trigger.private_keywords)
        if self.config.trigger.private_mode == "regex" and self.config.trigger.private_regex:
            return bool(re.search(self.config.trigger.private_regex, msg.content or ""))
        return False

    def _match_keywords(self, content: str | None, keywords: list[str]) -> bool:
        if not content or not keywords:
            return False
        lowered = content.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    def _append_history(self, msg: IncomingMessage, session: SessionInfo, image_meta: Any) -> None:
        record = {
            "timestamp": msg.timestamp,
            "direction": "received",
            "sender": msg.sender_name,
            "type": msg.msg_type,
            "content": msg.content,
            "message_id": msg.message_id,
            "session_key": session.session_key,
        }
        if image_meta:
            record["image"] = {
                "path": image_meta.relative_path,
                "sha256": image_meta.sha256,
                "size": image_meta.size,
                "mime": image_meta.mime_type,
            }
        self.store.append_history(session.scope, session.session_id, record)

    def _append_reply(self, session: SessionInfo, content: str) -> None:
        record = {
            "timestamp": time.time(),
            "direction": "sent",
            "sender": "bot",
            "type": "text",
            "content": content,
            "message_id": hashlib.sha1(f"reply:{content}:{time.time()}".encode("utf-8")).hexdigest(),
            "session_key": session.session_key,
        }
        self.store.append_history(session.scope, session.session_id, record)

    def _generate_reply(
        self,
        msg: IncomingMessage,
        session: SessionInfo,
        image_meta: Any,
    ) -> str:
        fixed_reply = self._fixed_reply_for_scope(session.scope)
        if fixed_reply:
            return fixed_reply
        if msg.msg_type == "image" and not self._should_process_image(msg):
            logger.info("image ignored by config")
            return ""

        history = self.store.load_history(session.scope, session.session_id)
        if msg.message_id:
            history = [record for record in history if record.get("message_id") != msg.message_id]
        history_messages = self._history_to_messages(history)

        system_prompt = self.config.persona.prompt_for_scope(session.scope)
        system_message = {"role": "system", "content": system_prompt}

        latest_user = self._build_latest_message(msg, image_meta)

        response_tokens = self._max_output_tokens(session.scope)
        budget = self.config.limits.token_budget - response_tokens
        if budget <= 0:
            logger.warning("token budget too small")
            return self.config.failure.fallback_reply

        if image_meta and image_meta.sha256 in self.vision_cache:
            cached = self.vision_cache[image_meta.sha256]
            logger.info("vision cache hit: %s", image_meta.sha256)
            return truncate_text_to_tokens(cached, response_tokens)

        messages = self._trim_context(
            [system_message],
            history_messages,
            latest_user,
            budget,
        )

        try:
            reply = self.client.send(messages)
            self.failure_tracker.register_success(session.session_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("llm call failed: %s", exc)
            self.failure_tracker.register_failure(session.session_id)
            return self.config.failure.fallback_reply

        reply = reply.strip()
        if not reply:
            return ""
        if image_meta:
            self.vision_cache[image_meta.sha256] = reply
        reply = truncate_text_to_tokens(reply, response_tokens)
        return reply

    def _fixed_reply_for_scope(self, scope: str) -> str | None:
        if scope == "group":
            return self.config.reply.group_fixed_reply
        return self.config.reply.private_fixed_reply

    def _should_process_image(self, msg: IncomingMessage) -> bool:
        if msg.is_group:
            return self.config.vision.enable_group and msg.is_at
        return self.config.vision.enable_private

    def _history_to_messages(self, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for record in history:
            role = "assistant" if record.get("direction") == "sent" else "user"
            if record.get("type") == "image":
                content = f"[图片] hash={record.get('image', {}).get('sha256', '')}"
            else:
                content = record.get("content") or ""
            if record.get("sender") and role == "user":
                content = f"{record['sender']}: {content}"
            messages.append({"role": role, "content": content})
        return messages

    def _build_latest_message(self, msg: IncomingMessage, image_meta: Any) -> list[dict[str, Any]]:
        if msg.msg_type == "image" and msg.image_bytes and msg.image_mime:
            text_prompt = msg.content or "请描述这张图片。"
            return [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text_prompt},
                        LlmClient.image_to_message(msg.image_bytes, msg.image_mime),
                    ],
                }
            ]

        content = msg.content or ""
        return [{"role": "user", "content": content}]

    def _trim_context(
        self,
        system_messages: list[dict[str, Any]],
        history_messages: list[dict[str, Any]],
        latest_messages: list[dict[str, Any]],
        budget: int,
    ) -> list[dict[str, Any]]:
        system_tokens = estimate_messages_tokens(system_messages)
        latest_tokens = estimate_messages_tokens(latest_messages)
        if latest_tokens > self.config.limits.max_single_message_tokens:
            latest_messages = self._truncate_latest(latest_messages)
            latest_tokens = estimate_messages_tokens(latest_messages)

        total = system_tokens + latest_tokens
        if total > budget:
            latest_messages = self._truncate_latest(latest_messages, budget - system_tokens)
            latest_tokens = estimate_messages_tokens(latest_messages)
            total = system_tokens + latest_tokens

        remaining = budget - total
        trimmed_history: list[dict[str, Any]] = []
        for record in reversed(history_messages):
            record_tokens = estimate_tokens(record.get("content", ""))
            if record_tokens <= remaining:
                trimmed_history.append(record)
                remaining -= record_tokens
            else:
                break

        trimmed_history.reverse()
        return [*system_messages, *trimmed_history, *latest_messages]

    def _truncate_latest(self, latest_messages: list[dict[str, Any]], budget: int | None = None) -> list[dict[str, Any]]:
        if not latest_messages:
            return latest_messages
        budget = budget or self.config.limits.max_single_message_tokens
        message = latest_messages[0]
        if isinstance(message.get("content"), list):
            for item in message["content"]:
                if item.get("type") == "text":
                    item["text"] = truncate_text_to_tokens(item["text"], budget)
            return latest_messages
        message["content"] = truncate_text_to_tokens(message.get("content", ""), budget)
        return latest_messages

    def _max_output_tokens(self, scope: str) -> int:
        if scope == "group":
            return min(self.config.limits.max_group_output_tokens, self.config.api.max_output_tokens)
        return min(self.config.limits.max_private_output_tokens, self.config.api.max_output_tokens)
