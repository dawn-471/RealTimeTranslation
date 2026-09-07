# -*- coding: utf-8 -*-
"""Streaming ASR engine wrapper around sherpa-onnx OnlineRecognizer.

Feeds 16kHz mono float32 chunks, emits AsrEvent("partial"|"final") per
recognizer state. Endpoint detection (built into sherpa-onnx) drives
finalization: on endpoint the stream is reset so the next utterance starts
fresh.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class AsrEvent:
    kind: str          # "partial" | "final"
    text: str
    channel: str       # "loopback" | "mic"
    ts: float


class StreamAsrEngine:
    """Streaming ASR engine. Pass either model_dir or fake_recognizer (tests)."""

    def __init__(
        self,
        model_dir: Optional[str] = None,
        sample_rate: int = 16000,
        num_threads: int = 4,
        channel: str = "loopback",
        fake_recognizer=None,
    ):
        if model_dir is None and fake_recognizer is None:
            raise ValueError("StreamAsrEngine requires model_dir or fake_recognizer")
        self.sample_rate = sample_rate
        self.channel = channel
        self._fake = fake_recognizer
        if fake_recognizer is not None:
            self._recognizer = fake_recognizer
            self._owns = False
        else:
            import sherpa_onnx
            self._recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
                tokens=model_dir + "/tokens.txt",
                encoder=model_dir + "/encoder.int8.onnx",
                decoder=model_dir + "/decoder.int8.onnx",
                num_threads=num_threads,
                enable_endpoint_detection=True,
                # 实测调参(2026-09-06): 默认 2.4/1.2/20 在短句(3-10s)下永不切段;
                # rule1=1.2 静音即切, rule2 为长句快速切, rule3=8 让 >8s 的大段用 rule2
                rule1_min_trailing_silence=1.2,
                rule2_min_trailing_silence=1.0,
                rule3_min_utterance_length=8.0,
            )
            self._owns = True
        self._stream = self._recognizer.create_stream()
        self._last_partial: Optional[str] = None

    def feed(self, samples: np.ndarray) -> list[AsrEvent]:
        """Feed one chunk of 16kHz mono float32; return events for this chunk."""
        events: list[AsrEvent] = []
        self._stream.accept_waveform(self.sample_rate, np.ascontiguousarray(samples, dtype=np.float32))
        if self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)

        result = self._recognizer.get_result_all(self._stream)
        text = (result.text or "").strip() if result else ""

        if self._recognizer.is_endpoint(self._stream):
            if text:
                events.append(AsrEvent(kind="final", text=text, channel=self.channel, ts=time.time()))
            self._recognizer.reset(self._stream)
            self._last_partial = None
        elif text and text != self._last_partial:
            self._last_partial = text
            events.append(AsrEvent(kind="partial", text=text, channel=self.channel, ts=time.time()))
        return events

    def close(self) -> None:
        self._stream = None
        if self._owns and hasattr(self._recognizer, "close"):
            self._recognizer.close()
