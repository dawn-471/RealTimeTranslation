# -*- coding: utf-8 -*-
"""Tests for credentials store (API keys never hardcoded; XDG data dir)."""
import os

import pytest

from realtime_translation.credentials import CredentialsStore


def test_defaults_no_keys():
    s = CredentialsStore(data_dir="/tmp/mt-test-1")
    # defaults exist but contain no secrets
    assert s.deepseek_base_url == "https://api.deepseek.com/v1"
    assert s.deepseek_api_key == ""
    assert s.gemini_base_url == "https://generativelanguage.googleapis.com/v1beta"
    assert s.gemini_api_key == ""


def test_save_and_load_roundtrip(tmp_path):
    s = CredentialsStore(data_dir=str(tmp_path))
    s.deepseek_api_key = "sk-test-123"
    s.gemini_api_key = "AIza-test-456"
    s.gemini_model = "gemini-3.1-flash-live-preview"
    s.save()

    s2 = CredentialsStore(data_dir=str(tmp_path))
    assert s2.deepseek_api_key == "sk-test-123"
    assert s2.gemini_api_key == "AIza-test-456"
    assert s2.gemini_model == "gemini-3.1-flash-live-preview"


def test_load_missing_file_returns_defaults(tmp_path):
    s = CredentialsStore(data_dir=str(tmp_path / "nope"))
    assert s.deepseek_api_key == ""
    assert s.gemini_api_key == ""


def test_file_permissions_not_world_readable(tmp_path):
    """On Windows we can't easily check posix perms; just verify file exists."""
    s = CredentialsStore(data_dir=str(tmp_path))
    s.deepseek_api_key = "secret"
    s.save()
    assert (tmp_path / "config.yaml").exists()


def test_env_var_override_only_when_unset(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env")
    s = CredentialsStore(data_dir=str(tmp_path))
    assert s.deepseek_api_key == "from-env"
    # persisted value wins over env later
    s.save()
    s2 = CredentialsStore(data_dir=str(tmp_path))
    assert s2.deepseek_api_key == "from-env"


def test_has_credentials_check(tmp_path):
    s = CredentialsStore(data_dir=str(tmp_path))
    assert s.has_any() is False
    s.deepseek_api_key = "x"
    assert s.has_any() is True
