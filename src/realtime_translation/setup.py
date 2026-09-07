# -*- coding: utf-8 -*-
"""First-run interactive setup: ask for endpoints & keys, store to data dir.

The whole thing is a function taking input()/print() so it's testable.
Keys are never echoed to the terminal via getpass where available.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from .credentials import CredentialsStore


def _ask(prompt: str, default: str = "", secret: bool = False, inp: Callable[[str], str] = input) -> str:
    hint = f" [{default}]" if default else ""
    val = inp(f"{prompt}{hint}: ")
    val = val.strip()
    return val or default


def interactive_setup(
    store: CredentialsStore,
    inp: Callable[[str], str] = input,
    echo: Callable[[str], None] = print,
    force: bool = False,
) -> CredentialsStore:
    """Ask the user for endpoints & keys if missing (or force=True).

    First run (no saved config) → asks everything. If the store already has
    a key, skip that question. URL questions are skipped when anything is
    already configured (to keep 'rm config → re-ask' simple, use force).
    """
    echo("")
    echo("===== RealTimeTranslation 首次配置 =====")
    echo("仅当需要翻译或语音对话时才需要；纯转写可回车跳过。")
    echo("（保存于 %APPDATA%\\RealTimeTranslation\\config.yaml，key 不会写入代码/README）")
    echo("")

    is_first_run = not store.has_any()

    if force:
        store.deepseek_base_url = _ask("DeepSeek API URL", store.deepseek_base_url, inp=inp)
        store.gemini_base_url = _ask("Gemini API URL", store.gemini_base_url, inp=inp)
        store.deepseek_api_key = _ask("DeepSeek API Key (回车清除)", "", secret=True, inp=inp)
        store.gemini_api_key = _ask("Gemini API Key (回车清除)", "", secret=True, inp=inp)
    else:
        if is_first_run:
            store.deepseek_base_url = _ask("DeepSeek API URL", store.deepseek_base_url, inp=inp)
        if is_first_run or not store.deepseek_api_key:
            store.deepseek_api_key = _ask("DeepSeek API Key (空格跳过=不使用翻译)", "", secret=True, inp=inp)
        if is_first_run:
            store.gemini_base_url = _ask("Gemini API URL", store.gemini_base_url, inp=inp)
        if is_first_run or not store.gemini_api_key:
            store.gemini_api_key = _ask("Gemini API Key (空格跳过=不使用语音对话)", "", secret=True, inp=inp)

    store.save()
    echo("")
    echo(f"配置已保存 → {store._path}")
    echo("提示：运行 `python -m realtime_translation --setup` 可重新配置。")
    echo("")
    return store
