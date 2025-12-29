from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PersonaConfig:
    global_prompt: str = "你是一个有用的微信助手。"
    private_prompt: str | None = None
    group_prompt: str | None = None

    def prompt_for_scope(self, scope: str) -> str:
        if scope == "group" and self.group_prompt:
            return f"{self.global_prompt}\n{self.group_prompt}"
        if scope == "private" and self.private_prompt:
            return f"{self.global_prompt}\n{self.private_prompt}"
        return self.global_prompt


@dataclass
class TriggerConfig:
    private_mode: str = "always"  # always | keyword | regex
    private_keywords: list[str] = field(default_factory=list)
    private_regex: str | None = None
    group_mode: str = "mention"  # mention | mention_keyword
    group_keywords: list[str] = field(default_factory=list)


@dataclass
class ApiConfig:
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 60
    stream: bool = False
    model: str = "gpt-4o-mini"
    max_output_tokens: int = 800
    core_params_enabled: dict[str, bool] = field(default_factory=dict)
    extra_params: dict[str, Any] = field(default_factory=dict)
    extra_params_enabled: dict[str, bool] = field(default_factory=dict)


@dataclass
class LimitsConfig:
    token_budget: int = 4096
    min_reserved_output_tokens: int = 256
    max_group_output_tokens: int = 512
    max_private_output_tokens: int = 800
    max_single_message_tokens: int = 2048


@dataclass
class StorageConfig:
    base_dir: str = "data/wxauto_lite_bot"


@dataclass
class DedupeConfig:
    window_seconds: int = 60


@dataclass
class RateLimitConfig:
    session_cooldown_seconds: int = 3
    user_cooldown_seconds: int = 2


@dataclass
class FailureConfig:
    max_consecutive_failures: int = 3
    cooldown_seconds: int = 60
    fallback_reply: str = "抱歉，我暂时无法回复，请稍后再试。"


@dataclass
class VisionConfig:
    enable_private: bool = True
    enable_group: bool = True


@dataclass
class ReplyConfig:
    private_fixed_reply: str | None = None
    group_fixed_reply: str | None = None


@dataclass
class BotConfig:
    persona: PersonaConfig = field(default_factory=PersonaConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    dedupe: DedupeConfig = field(default_factory=DedupeConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    failure: FailureConfig = field(default_factory=FailureConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    reply: ReplyConfig = field(default_factory=ReplyConfig)
    self_user_id: str | None = None


_DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")


def load_config(path: str | None = None) -> BotConfig:
    config_path = Path(path or os.getenv("WXAUTO_LITE_BOT_CONFIG", _DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        return BotConfig()

    data = json.loads(config_path.read_text(encoding="utf-8"))

    return BotConfig(
        persona=PersonaConfig(**data.get("persona", {})),
        trigger=TriggerConfig(**data.get("trigger", {})),
        api=ApiConfig(**data.get("api", {})),
        limits=LimitsConfig(**data.get("limits", {})),
        storage=StorageConfig(**data.get("storage", {})),
        dedupe=DedupeConfig(**data.get("dedupe", {})),
        rate_limit=RateLimitConfig(**data.get("rate_limit", {})),
        failure=FailureConfig(**data.get("failure", {})),
        vision=VisionConfig(**data.get("vision", {})),
        reply=ReplyConfig(**data.get("reply", {})),
        self_user_id=data.get("self_user_id"),
    )
