# -*- coding: utf-8 -*-
"""Tests for the TUI formatting helpers (pure functions; no rich rendering)."""
from realtime_translation.ui import (
    format_timestamp,
    format_original_line,
    format_translation_line,
    StatusLine,
)


def test_format_timestamp():
    assert format_timestamp("12:34:56") == "12:34:56"
    assert format_timestamp("09:05:07") == "09:05:07"
    assert len(format_timestamp("00:00:01")) == 8


def test_format_original_line_with_loopback():
    line = format_original_line("12:00:00", "loopback", "今天天气不错")
    assert "今天天气不错" in line
    assert "loopback" in line  # channel tag
    assert "12:00:00" in line


def test_format_original_line_mic():
    line = format_original_line("12:00:01", "mic", "我自己说的")
    assert "mic" in line
    assert "我自己说的" in line


def test_format_translation_line_present():
    line = format_translation_line("今天天气不错", "It's sunny today")
    assert "It's sunny today" in line
    assert "今天天气不错" not in line  # translation line is standalone
    assert line.startswith("↳") or "↳" in line


def test_format_translation_line_none_returns_empty():
    assert format_translation_line("x", None) is None or format_translation_line("x", None) == ""


def test_status_line_counts():
    s = StatusLine(total=10, finals=5, failed=1, backend="deepseek")
    text = str(s)
    assert "10" in text and "5" in text and "deepseek" in text
