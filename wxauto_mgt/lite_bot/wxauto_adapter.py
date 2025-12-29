from __future__ import annotations

import time
from typing import Any, Iterable

from wxauto_mgt.lite_bot.models import IncomingMessage, SessionInfo


class WxautoAdapter:
    """
    将 wxauto 消息转换为统一模型，并发送消息。

    wxauto 的具体字段可能因版本而异，请根据实际数据结构调整 parse_raw。
    """

    def __init__(self, wxauto_client: Any) -> None:
        self.wxauto = wxauto_client

    def send_text(self, session: SessionInfo, text: str) -> None:
        target = session.display_name
        self.wxauto.SendMsg(text, target)

    def poll_messages(self) -> Iterable[dict[str, Any]]:
        return self.wxauto.GetListenMessage()

    def parse_raw(self, raw: dict[str, Any]) -> IncomingMessage:
        msg_type = raw.get("type", "text")
        content = raw.get("content")
        is_group = raw.get("is_group", False)
        return IncomingMessage(
            message_id=str(raw.get("msg_id") or raw.get("id") or ""),
            timestamp=float(raw.get("timestamp") or time.time()),
            sender_id=str(raw.get("sender_id") or raw.get("sender") or ""),
            sender_name=str(raw.get("sender_name") or raw.get("sender") or ""),
            content=content if isinstance(content, str) else None,
            msg_type=msg_type,
            is_group=is_group,
            group_id=raw.get("group_id"),
            group_name=raw.get("group_name"),
            is_at=bool(raw.get("is_at")),
            conversation_id=raw.get("conversation_id"),
            image_bytes=raw.get("image_bytes"),
            image_name=raw.get("image_name"),
            image_mime=raw.get("image_mime"),
            raw=raw,
        )
