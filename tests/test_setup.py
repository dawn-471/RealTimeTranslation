# -*- coding: utf-8 -*-
"""Tests for first-run interactive setup."""
import pytest

from realtime_translation.credentials import CredentialsStore
from realtime_translation.setup import interactive_setup


def _fake_input(*answers):
    """Build an input() callable returning queued answers; '' at end by default."""
    q = list(answers)

    def fn(prompt=""):
        if q:
            return q.pop(0)
        return ""

    return fn


def test_setup_skips_when_keys_present(tmp_path, capsys):
    store = CredentialsStore(data_dir=str(tmp_path))
    store.deepseek_api_key = "sk-existing"
    store.gemini_api_key = "AIza-existing"
    out = interactive_setup(store, inp=_fake_input("", "", "", ""), echo=print)
    assert out.deepseek_api_key == "sk-existing"
    assert out.gemini_api_key == "AIza-existing"
    assert "首次配置" in capsys.readouterr().out


def test_setup_asks_and_saves_new_keys(tmp_path):
    store = CredentialsStore(data_dir=str(tmp_path))
    # answers: deepseek url, deepseek key, gemini url, gemini key
    answers = ["my-url.example", "sk-new-1", "gem-url.example", "AIza-new-2"]
    out = interactive_setup(store, inp=_fake_input(*answers))
    assert out.deepseek_base_url == "my-url.example"
    assert out.deepseek_api_key == "sk-new-1"
    assert out.gemini_base_url == "gem-url.example"
    assert out.gemini_api_key == "AIza-new-2"
    # reload from disk
    s2 = CredentialsStore(data_dir=str(tmp_path))
    assert s2.deepseek_api_key == "sk-new-1"
    assert s2.gemini_api_key == "AIza-new-2"


def test_setup_empty_answers_keep_defaults(tmp_path):
    store = CredentialsStore(data_dir=str(tmp_path))
    out = interactive_setup(store, inp=_fake_input("", "", "", ""))
    assert out.deepseek_base_url == "https://api.deepseek.com/v1"
    assert out.deepseek_api_key == ""
    assert out.gemini_api_key == ""


def test_setup_force_overwrites(tmp_path):
    store = CredentialsStore(data_dir=str(tmp_path))
    store.deepseek_api_key = "old"
    store.gemini_api_key = "old-g"
    # force asks: ds-url, gem-url, ds-key, gem-key
    out = interactive_setup(store, inp=_fake_input("ds-url", "gem-url", "new-key", "g-key"), force=True)
    assert out.deepseek_api_key == "new-key"
    assert out.gemini_api_key == "g-key"
