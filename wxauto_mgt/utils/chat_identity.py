"""
聊天身份识别工具

用于区分群聊与单聊，并生成稳定的聊天唯一键，避免历史记录混淆。
"""

from typing import Tuple, Optional


def detect_chat_type(chat_name: Optional[str], sender: Optional[str] = None, sender_remark: Optional[str] = None) -> str:
    """
    识别聊天类型

    Args:
        chat_name: 聊天名称
        sender: 发送者
        sender_remark: 发送者备注名

    Returns:
        str: "group" 或 "private"（未知返回 "unknown"）
    """
    if not chat_name:
        return "unknown"

    if sender:
        if sender != chat_name:
            return "group"
        return "private"

    if sender_remark and sender_remark != chat_name:
        return "group"

    return "private"


def build_chat_key(chat_name: Optional[str], chat_type: Optional[str]) -> str:
    """
    构建聊天唯一键

    Args:
        chat_name: 聊天名称
        chat_type: 聊天类型

    Returns:
        str: 聊天唯一键
    """
    if not chat_name:
        return ""

    normalized_type = chat_type or "unknown"
    return f"{normalized_type}:{chat_name}"


def get_chat_identity(chat_name: Optional[str],
                      sender: Optional[str] = None,
                      sender_remark: Optional[str] = None) -> Tuple[str, str]:
    """
    获取聊天身份信息（类型 + 唯一键）

    Args:
        chat_name: 聊天名称
        sender: 发送者
        sender_remark: 发送者备注名

    Returns:
        Tuple[str, str]: (chat_type, chat_key)
    """
    chat_type = detect_chat_type(chat_name, sender, sender_remark)
    chat_key = build_chat_key(chat_name, chat_type)
    return chat_type, chat_key
