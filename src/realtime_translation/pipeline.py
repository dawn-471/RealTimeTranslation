# -*- coding: utf-8 -*-
"""Pipeline: capture -> ASR -> (translate) -> subscriber events.

Threading: the capture thread calls on_chunk; the ASR feed and translation
run synchronously in that thread (simple, adequate for 100ms chunks where
translation is fast). Subscribers get TranscriptEntry objects.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    ts: datetime
    channel: str        # "loopback" | "mic"
    text: str
    partial: bool = False
    translated: Optional[str] = None
    translate_failed: bool = False
    translate_direction: Optional[str] = None


@dataclass
class Pipeline:
    capture: object
    asr: object
    translator: object = None
    min_translate_len: int = 2
    _subscribers: list = field(default_factory=list)
    _running: bool = False

    def subscribe(self, cb: Callable[[TranscriptEntry], None]) -> None:
        self._subscribers.append(cb)

    def start(self) -> None:
        self._running = True
        self.capture.start(self._on_chunk)

    def stop(self) -> None:
        self._running = False
        self.capture.stop()
        self.asr.close()

    def _on_chunk(self, samples, frame) -> None:
        try:
            events = self.asr.feed(samples)
        except Exception as exc:
            log.warning("ASR feed failed: %s", exc)
            return
        for ev in events:
            entry = TranscriptEntry(
                ts=datetime.now(),
                channel=ev.channel,
                text=ev.text,
                partial=(ev.kind == "partial"),
            )
            if ev.kind == "final" and self.translator is not None:
                self._maybe_translate(entry)
            for cb in self._subscribers:
                try:
                    cb(entry)
                except Exception as exc:
                    log.warning("subscriber failed: %s", exc)

    def _maybe_translate(self, entry: TranscriptEntry) -> None:
        text = entry.text
        if len(text) < self.min_translate_len:
            return
        from .lang_dir import detect_direction
        direction = detect_direction(text)
        if direction == "none":
            return
        try:
            out = self.translator.translate(text, direction)
        except Exception as exc:
            log.warning("translate raised: %s", exc)
            entry.translate_failed = True
            return
        if out is None:
            # None means the backend is off (NoTranslator) or it errored.
            # Distinguish: NoTranslator returns None without attempting.
            if getattr(self.translator, "name", None) == "off":
                return
            entry.translate_failed = True
        else:
            entry.translated = out
            entry.translate_direction = direction
