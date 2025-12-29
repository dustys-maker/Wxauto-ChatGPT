from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests

from wxauto_mgt.lite_bot.config import ApiConfig


class LlmClient:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    def _headers(self) -> dict[str, str]:
        api_key = os.getenv(self.config.api_key_env, "")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _extra_params(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in self.config.extra_params.items():
            if self.config.extra_params_enabled.get(key, False):
                payload[key] = value
        return payload

    def _build_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {"messages": messages}
        if self.config.core_params_enabled.get("model", True):
            payload["model"] = self.config.model
        if self.config.core_params_enabled.get("stream", True):
            payload["stream"] = self.config.stream
        if self.config.core_params_enabled.get("max_tokens", True):
            payload["max_tokens"] = self.config.max_output_tokens
        payload.update(self._extra_params())
        return payload

    def send(self, messages: list[dict[str, Any]]) -> str:
        payload = self._build_payload(messages)
        response = requests.post(
            self.config.endpoint,
            headers=self._headers(),
            json=payload,
            timeout=self.config.timeout_seconds,
            stream=self.config.stream,
        )
        response.raise_for_status()

        if not self.config.stream:
            data = response.json()
            return self._extract_content(data)

        chunks: list[str] = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                line = line[6:]
            if line.strip() == "[DONE]":
                break
            data = json.loads(line)
            delta = data.get("choices", [{}])[0].get("delta", {})
            if "content" in delta:
                chunks.append(delta["content"])
        return "".join(chunks)

    def _extract_content(self, data: dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        if "content" in message:
            return message["content"] or ""
        return choices[0].get("text", "") or ""

    @staticmethod
    def image_to_message(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64}"
            },
        }
