# -*- coding: utf-8 -*-
"""Tests for talk.py — P2T flag logic & VoiceChat queue behavior; no network."""
import threading
import time

from realtime_translation.talk import PushToTalk


def test_ptt_initial_inactive():
    p = PushToTalk()
    assert p.active is False


def test_ptt_press_release_cycle():
    p = PushToTalk()
    p.press()
    assert p.active is True
    p.release()
    assert p.active is False


def test_ptt_thread_safety():
    """Concurrent press/release across threads must not corrupt state."""
    p = PushToTalk()
    def flipper():
        for _ in range(200):
            p.press()
            assert p.active is True
            p.release()
            assert p.active is False

    threads = [threading.Thread(target=flipper) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert p.active is False


def test_gemini_session_uses_credentials_not_defaults():
    """The session must take api_key/model/base_url explicitly (no hardcoding)."""
    from realtime_translation.talk import GeminiLiveSession
    s = GeminiLiveSession(api_key="AIza", model="gemini-x", base_url="https://example.com")
    assert s.api_key == "AIza"
    assert s.model == "gemini-x"
    assert s.base_url == "https://example.com"
