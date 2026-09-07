# -*- coding: utf-8 -*-
"""Tests for language direction detection and translator backends."""
import httpx
import pytest

from realtime_translation.lang_dir import detect_direction
from realtime_translation.translator import (
    DeepSeekTranslator,
    FakeTranslator,
    NoTranslator,
    OllamaTranslator,
    create_translator,
)


class TestDetectDirection:
    def test_chinese_sentence_zh2en(self):
        assert detect_direction("今天天气不错") == "zh2en"

    def test_english_sentence_en2zh(self):
        assert detect_direction("This is a great day") == "en2zh"

    def test_mixed_sentence_zh2en(self):
        # 中英混合但汉字占多数 → zh2en
        assert detect_direction("这个 model 的 performance 很好") == "zh2en"

    def test_english_with_chinese_name_en2zh(self):
        # 少量中文专名 → 仍 en2zh
        assert detect_direction("The meeting with 王明 ended") == "en2zh"

    def test_empty_text_returns_none(self):
        assert detect_direction("") == "none"

    def test_punctuation_only_returns_none(self):
        assert detect_direction("?!。.!") == "none"

    def test_boundary_chinese_ratio(self):
        # 汉字占比 0.3 → 仍 zh2en（0.15 阈值以下）
        text = "你好abcd"  # 2 汉字 / 6 = 0.33
        assert detect_direction(text) == "zh2en"
        # 少量中文专名（<0.15）→ en2zh
        text2 = "The meeting with 王明 ended successfully"  # 2/37 ≈ 0.05
        assert detect_direction(text2) == "en2zh"


class TestFakeTranslator:
    def test_returns_prefix(self):
        t = FakeTranslator()
        out = t.translate("你好", "zh2en")
        assert out == "译|你好"

    def test_none_on_empty(self):
        t = FakeTranslator()
        assert t.translate("", "zh2en") is None


class TestNoTranslator:
    def test_always_none(self):
        t = NoTranslator()
        assert t.translate("any", "zh2en") is None
        assert t.translate("", "zh2en") is None


class TestDeepSeekTranslator:
    def test_request_body_and_extract(self, monkeypatch):
        captured = {}

        def fake_post(url, *args, **kw):
            captured["url"] = url
            captured["json"] = kw.get("json") or (args[0] if args else None)
            req = httpx.Request("POST", url)
            return httpx.Response(200, json={"choices": [{"message": {"content": "今天是个好日子"}}]}, request=req)

        t = DeepSeekTranslator(api_key="sk-test")
        # mock the instance's bound method (monkeypatch on instance avoids the
        # unbound-method 'self' problem)
        monkeypatch.setattr(t._client, "post", fake_post, raising=False)
        out = t.translate("It is a good day", "en2zh")
        assert out == "今天是个好日子"
        assert "api.deepseek.com" in captured["url"]
        body = captured["json"]
        # system 提示词 + user 文本
        assert body["model"] == "deepseek-chat"
        assert body["messages"][0]["role"] == "system"
        assert "只输出译文" in body["messages"][0]["content"]
        assert body["messages"][-1]["role"] == "user"
        assert "It is a good day" in body["messages"][-1]["content"]

    def test_api_error_returns_none(self, monkeypatch):
        def fake_post(*a, **kw):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr("httpx.Client.post", fake_post, raising=False)
        t = DeepSeekTranslator(api_key="sk-test")
        assert t.translate("hi", "en2zh") is None

    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError):
            DeepSeekTranslator(api_key="")


class TestOllamaTranslator:
    def test_creates_client_with_cpu_option(self, monkeypatch):
        # OllamaTranslator 只是组装请求，不在此处发网络
        t = OllamaTranslator(model="mttranslate")
        assert t.model == "mttranslate"
        assert t.base_url == "http://127.0.0.1:11434"


class TestCreateTranslator:
    def test_off(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        t = create_translator("off")
        assert isinstance(t, NoTranslator)

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError):
            create_translator("nope")
