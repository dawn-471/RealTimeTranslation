# -*- coding: utf-8 -*-
"""Tests for StreamAsrEngine — uses a minimal fake recognizer (no model, no audio HW).

Fake semantics: each feed() consumes exactly one script item; get_result_all()
and is_endpoint() both reflect that item; index never exceeds the script (the
last item repeats). This mirrors sherpa-onnx's real per-chunk behavior closely
enough for the engine's event logic.
"""
import numpy as np
import pytest

from realtime_translation.asr_engine import AsrEvent, StreamAsrEngine


class FakeStream:
    def __init__(self):
        self.accepted = []

    def accept_waveform(self, sr, samples):
        self.accepted.append((sr, np.asarray(samples).copy()))


class FakeResult:
    def __init__(self, text):
        self.text = text
        self.is_final = False


class FakeRecognizer:
    def __init__(self, script):
        self._script = script
        self._pos = 0
        self._last_item = {}
        self.decoded = 0
        self.reset_count = 0

    def _item(self):
        return self._script[min(self._pos, len(self._script) - 1)]

    def create_stream(self):
        return FakeStream()

    def is_ready(self, stream):
        return True

    def decode_stream(self, stream):
        self.decoded += 1

    def get_result_all(self, stream):
        item = self._script[min(self._pos, len(self._script) - 1)]
        self._last_item = item
        self._pos += 1
        return FakeResult(item.get("text", ""))

    def is_endpoint(self, stream):
        return bool(getattr(self, "_last_item", {}).get("endpoint", False))

    def reset(self, stream):
        self.reset_count += 1


def make_engine(script, channel="loopback"):
    return StreamAsrEngine(fake_recognizer=FakeRecognizer(script), channel=channel)


def test_feed_emits_partial_then_final():
    engine = make_engine([
        {"text": "今天"},
        {"text": "今天天气"},
        {"text": "今天天气不错"},
        {"text": "今天天气不错", "endpoint": True},
    ])
    events: list[AsrEvent] = []
    for _ in range(4):
        events.extend(engine.feed(np.zeros(1600, dtype=np.float32)))
    partials = [e.text for e in events if e.kind == "partial"]
    final_events = [e for e in events if e.kind == "final"]
    assert partials == ["今天", "今天天气", "今天天气不错"], partials
    assert [e.text for e in final_events] == ["今天天气不错"]
    assert final_events[0].channel == "loopback"


def test_endpoint_emits_final_and_resets_stream():
    rec = FakeRecognizer([
        {"text": "hello world"},
        {"text": "hello world", "endpoint": True},
    ])
    engine = StreamAsrEngine(fake_recognizer=rec, channel="loopback")
    events = []
    events.extend(engine.feed(np.zeros(1600, dtype=np.float32)))
    events.extend(engine.feed(np.zeros(1600, dtype=np.float32)))
    assert any(e.kind == "final" for e in events)
    assert rec.reset_count == 1


def test_partial_events_deduplicated_by_text():
    """If the recognizer returns the same partial text twice, do not re-emit."""
    rec = FakeRecognizer([
        {"text": "same"},
        {"text": "same"},
        {"text": "same new"},
    ])
    engine = StreamAsrEngine(fake_recognizer=rec, channel="mic")
    events = []
    for _ in range(3):
        events.extend(engine.feed(np.zeros(1600, dtype=np.float32)))
    partials = [e.text for e in events if e.kind == "partial"]
    assert partials == ["same", "same new"], partials
    assert rec.reset_count == 0


def test_engine_raises_on_missing_model_or_fake():
    with pytest.raises(ValueError):
        StreamAsrEngine()


def test_asr_event_dataclass_fields():
    e = AsrEvent(kind="final", text="hi", channel="loopback", ts=123.4)
    assert e.kind == "final"
    assert e.text == "hi"
    assert e.channel == "loopback"
    assert e.ts == 123.4
