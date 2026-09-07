# -*- coding: utf-8 -*-
"""Translation backends behind a common protocol.

All backends return str | None. None means "failed or not available" —
downstream must tolerate None and mark the entry accordingly.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional, Protocol

import httpx

log = logging.getLogger(__name__)

DEEPSEEK_SYSTEM_PROMPT = ("你是一个专业的翻译引擎。只输出译文本身，不加任何解释、"
                          "注释、备选版本或参考句。直接给出翻译结果。")


class Translator(Protocol):
    def translate(self, text: str, direction: str) -> Optional[str]: ...


class NoTranslator:
    def __init__(self):
        self.name = "off"

    def translate(self, text: str, direction: str) -> Optional[str]:
        return None


class FakeTranslator:
    def __init__(self):
        self.name = "fake"

    def translate(self, text: str, direction: str) -> Optional[str]:
        if not text:
            return None
        return f"译|{text}"


class DeepSeekTranslator:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout_s: float = 20.0,
    ):
        self.name = "deepseek"
        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not set — run `--setup` or set the env var "
                "(see README)"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=timeout_s)

    def translate(self, text: str, direction: str) -> Optional[str]:
        if not text or not direction:
            return None
        out_lang = "英文" if direction == "zh2en" else "中文"
        prompt = (
            f"请把下面的文本翻译成{out_lang}，只输出译文：\n\n{text}"
        )
        try:
            resp = self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 512,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip() or None
        except Exception as exc:
            log.warning("deepseek translate failed: %s", exc)
            return None


class OllamaTranslator:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "mttranslate",
        timeout_s: float = 25.0,
    ):
        self.name = "ollama"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=timeout_s)

    def translate(self, text: str, direction: str) -> Optional[str]:
        if not text or not direction:
            return None
        out_lang = "English" if direction == "zh2en" else "Chinese"
        prompt = (
            f"Translate the following text to {out_lang}. Output only the "
            f"translation, nothing else:\n\n{text}"
        )
        try:
            resp = self._client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 128},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (data.get("response") or "").strip() or None
        except Exception as exc:
            log.warning("ollama translate failed: %s", exc)
            return None


def create_translator(backend: str, creds=None) -> Translator:
    """Factory: 'deepseek' | 'ollama' | 'off' | 'fake'. creds = CredentialsStore."""
    backend = (backend or "off").lower()
    if backend == "off":
        return NoTranslator()
    if backend == "fake":
        return FakeTranslator()
    if backend == "deepseek":
        if creds is not None and creds.deepseek_api_key:
            return DeepSeekTranslator(
                api_key=creds.deepseek_api_key,
                base_url=creds.deepseek_base_url,
                model=creds.deepseek_model,
            )
        return DeepSeekTranslator()
    if backend == "ollama":
        return OllamaTranslator()
    raise ValueError(f"unknown translate backend: {backend!r}")
