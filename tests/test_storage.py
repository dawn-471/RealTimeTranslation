# -*- coding: utf-8 -*-
"""Tests for storage: JSONL appends + Markdown export."""
import json
import os
from datetime import datetime

import pytest

from realtime_translation.pipeline import TranscriptEntry
from realtime_translation.storage import TranscriptStorage


def test_jsonl_append_and_read(tmp_path):
    s = TranscriptStorage(output_dir=str(tmp_path))
    e1 = TranscriptEntry(ts=datetime(2026, 9, 7, 0, 0, 0), channel="loopback", text="你好")
    e2 = TranscriptEntry(ts=datetime(2026, 9, 7, 0, 0, 5), channel="loopback", text="hello",
                         translated="你好", translate_direction="en2zh")
    s.append(e1)
    s.append(e2)
    lines = s.path  # use the storage's own path
    content = open(lines, encoding="utf-8").read().strip().split("\n")
    assert len(content) == 2
    d1 = json.loads(content[0])
    assert d1["text"] == "你好"
    assert d1["channel"] == "loopback"
    assert d1["translated"] is None
    assert "partial" not in d1  # partial entries are never written
    d2 = json.loads(content[1])
    assert d2["translated"] == "你好"


def test_partial_not_stored(tmp_path):
    s = TranscriptStorage(output_dir=str(tmp_path))
    e = TranscriptEntry(ts=datetime(2026, 9, 7), channel="loopback", text="partial", partial=True)
    s.append(e)
    assert not (tmp_path / "transcript.jsonl").exists() or s._count == 0


def test_md_export_structure(tmp_path):
    s = TranscriptStorage(output_dir=str(tmp_path))
    s.append(TranscriptEntry(ts=datetime(2026, 9, 7, 0, 0, 0), channel="loopback",
                             text="今天天气不错"))
    s.append(TranscriptEntry(ts=datetime(2026, 9, 7, 0, 0, 5), channel="loopback",
                             text="Good weather today", translated="今天天气很好",
                             translate_direction="en2zh"))
    md = s.export_markdown()
    assert "# 会议转写" in md or "# Meeting" in md
    assert "今天天气不错" in md
    assert "今天天气很好" in md
    assert "00:00:00" in md


def test_multiple_sessions_same_output_dir(tmp_path):
    s1 = TranscriptStorage(output_dir=str(tmp_path))
    s1.append(TranscriptEntry(ts=datetime(2026, 9, 7, 1), channel="loopback", text="a"))
    s2 = TranscriptStorage(output_dir=str(tmp_path))
    s2.append(TranscriptEntry(ts=datetime(2026, 9, 7, 2), channel="loopback", text="b"))
    # distinct filenames per session
    assert os.path.exists(s1.path)
    assert os.path.exists(s2.path)
    assert s1.path != s2.path
