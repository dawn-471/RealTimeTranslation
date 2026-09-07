# -*- coding: utf-8 -*-
"""Credentials store — API keys & endpoints, never hardcoded in code.

Follows the XDG-style split: code dir is pure code, data dir holds user
config. On Windows: %APPDATA%\\RealTimeTranslation\\config.yaml

The file is plain YAML. Keys are only read from:
  1. the YAML store (data dir), or
  2. environment variables (DEEPSEEK_API_KEY / GEMINI_API_KEY) as fallback
No default key values exist in the code — first-run interactively asks.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

DEFAULT_DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-live-preview"


def default_data_dir() -> str:
    """%APPDATA%\\RealTimeTranslation on Windows, ~/.config/... elsewhere."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "RealTimeTranslation")
    home = os.path.expanduser("~")
    return os.path.join(home, ".config", "RealTimeTranslation")


@dataclass
class CredentialsStore:
    data_dir: str = field(default_factory=default_data_dir)
    # deepseek (translation)
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    deepseek_api_key: str = ""
    # gemini live (voice chat)
    gemini_base_url: str = DEFAULT_GEMINI_BASE
    gemini_model: str = DEFAULT_GEMINI_MODEL
    gemini_api_key: str = ""
    # configure after load
    _path: Optional[str] = field(default=None, init=False)

    def __post_init__(self):
        os.makedirs(self.data_dir, exist_ok=True)
        self._path = os.path.join(self.data_dir, "config.yaml")
        self._load()

    def _load(self) -> None:
        if self._path and os.path.exists(self._path):
            with open(self._path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for k, v in data.items():
                if hasattr(self, k) and v is not None:
                    setattr(self, k, v)
        # env fallback for keys (only if not already set)
        if not self.deepseek_api_key:
            self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "deepseek_base_url": self.deepseek_base_url,
                "deepseek_model": self.deepseek_model,
                "deepseek_api_key": self.deepseek_api_key,
                "gemini_base_url": self.gemini_base_url,
                "gemini_model": self.gemini_model,
                "gemini_api_key": self.gemini_api_key,
            }, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def has_any(self) -> bool:
        return bool(self.deepseek_api_key or self.gemini_api_key)

    def has_deepseek(self) -> bool:
        return bool(self.deepseek_api_key)

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)
