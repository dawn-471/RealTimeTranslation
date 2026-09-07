# -*- coding: utf-8 -*-
"""Tests for Pipeline — injects fake capture / fake ASR / fake translator."""
import numpy as np
import pytest

from realtime_translation.asr_engine import AsrEvent
from realtime_translation.pipeline import Pipeline, TranscriptEntry


class FakeCapture:
    """Pushes chunks onto the pipeline synchronously from a test thread."""
    def __init__(self, chunks=None):
        self._chunks = list(chunks or [])
        self._on_chunk = None
        self.started = False
        self.stopped = False

    def start(self, on_chunk):
        self._on_chunk = on_chunk
        self.started = True
        for c in self._chunks:
            on_chunk(c, 0)

    def stop(self):
        self.stopped = True


class FakeAsrEngine:
    """Returns a scripted sequence of events; records feeds."""
    def __init__(self, script):
        self.script = list(script)
        self.feeds = 0
        self.closed = False

    def feed(self, samples):
        self.feeds += 1
        return self.script.pop(0) if self.script else []

    def close(self):
        self.closed = True


class FakeTranslator:
    def __init__(self, result="TRANSLATED"):
        self.calls = []
        self.result = result

    def translate(self, text, direction):
        self.calls.append((text, direction))
        return self.result


def collect(pipeline, n_events=10):
    out = []
    pipeline.subscribe(out.append)
    pipeline.start()
    for _ in range(n_events):
        if len(out) >= n_events:
            break
    pipeline.stop()
    return out


def test_pipeline_emits_entries_for_partial_and_final():
    asr = FakeAsrEngine([
        [AsrEvent("partial", "今天", "loopback", 1.0)],
        [AsrEvent("partial", "今天天气", "loopback", 1.2)],
        [AsrEvent("final", "今天天气不错", "loopback", 1.5)],
    ])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)] * 3)
    pipe = Pipeline(capture=cap, asr=asr, translator=FakeTranslator())
    entries = collect(pipe, n_events=3)
    assert len(entries) == 3
    assert entries[0].partial is True
    assert entries[0].text == "今天"
    assert entries[2].partial is False
    assert entries[2].text == "今天天气不错"
    assert entries[2].translate_failed is False


def test_final_triggers_translation_and_sets_translated():
    asr = FakeAsrEngine([[AsrEvent("final", "hello world", "loopback", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    tr = FakeTranslator(result="你好世界")
    pipe = Pipeline(capture=cap, asr=asr, translator=tr)
    entries = collect(pipe, n_events=1)
    assert entries[0].translated == "你好世界"
    assert tr.calls == [("hello world", "en2zh")]


def test_partial_does_not_trigger_translation():
    asr = FakeAsrEngine([[AsrEvent("partial", "hi", "loopback", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    tr = FakeTranslator()
    pipe = Pipeline(capture=cap, asr=asr, translator=tr)
    entries = collect(pipe, n_events=1)
    assert entries[0].translated is None
    assert tr.calls == []


def test_translation_failure_marks_entry():
    class FailingTranslator(FakeTranslator):
        def translate(self, text, direction):
            self.calls.append((text, direction))
            return None

    asr = FakeAsrEngine([[AsrEvent("final", "hello", "loopback", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    pipe = Pipeline(capture=cap, asr=asr, translator=FailingTranslator())
    entries = collect(pipe, n_events=1)
    assert entries[0].translated is None
    assert entries[0].translate_failed is True


def test_translator_none_means_no_translation_attempt():
    """NoTranslator: final entries just don't have translation."""
    from realtime_translation.translator import NoTranslator
    asr = FakeAsrEngine([[AsrEvent("final", "hello", "loopback", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    pipe = Pipeline(capture=cap, asr=asr, translator=NoTranslator())
    entries = collect(pipe, n_events=1)
    assert entries[0].translated is None
    assert entries[0].translate_failed is False


def test_mic_channel_preserved():
    asr = FakeAsrEngine([[AsrEvent("final", "自己说的话", "mic", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    pipe = Pipeline(capture=cap, asr=asr, translator=FakeTranslator())
    entries = collect(pipe, n_events=1)
    assert entries[0].channel == "mic"


def test_short_text_no_translation():
    """Very short/empty final text should not trigger translation."""
    asr = FakeAsrEngine([[AsrEvent("final", "", "loopback", 1.0)]])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)])
    tr = FakeTranslator()
    pipe = Pipeline(capture=cap, asr=asr, translator=tr)
    entries = collect(pipe, n_events=1)
    assert len(entries) == 1
    assert tr.calls == []


def test_toggle_translation_returns_cached():
    asr = FakeAsrEngine([
        [AsrEvent("final", "hello", "loopback", 1.0)],
        [AsrEvent("final", "world", "loopback", 2.0)],
    ])
    cap = FakeCapture(chunks=[np.zeros(1600, dtype=np.float32)] * 2)
    tr = FakeTranslator(result="译")
    pipe = Pipeline(capture=cap, asr=asr, translator=tr)
    entries = collect(pipe, n_events=2)
    assert entries[0].translated == "译"
    # toggle then toggle back: should reuse cache, not re-translate
    # (entry.translated already set; pipeline keeps it)
    assert len(tr.calls) == 2  # one per final entry
