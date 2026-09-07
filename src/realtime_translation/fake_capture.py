# -*- coding: utf-8 -*-
"""Fake capture for --fake demo mode: generates synthetic tone chunks."""
from __future__ import annotations

import math
import threading
import time
from typing import Callable

import numpy as np


class FakeCapture:
    """Produces a synthetic 440Hz tone (with amplitude modulation) at 100ms."""
    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 100):
        self.sample_rate = sample_rate
        self._chunk_samples = int(sample_rate * chunk_ms / 1000)
        self._t = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_chunk: Callable[[np.ndarray, int], None] | None = None

    def start(self, on_chunk):
        self._on_chunk = on_chunk
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            t = np.arange(self._chunk_samples) / self.sample_rate
            # tone + envelope so VAD roughly sees "speech"
            sample = 0.3 * np.sin(2 * math.pi * 220 * (self._t + t))
            sample *= 0.6 + 0.4 * np.sin(2 * math.pi * 3 * (self._t + t))
            self._t += self._chunk_samples / self.sample_rate
            if self._on_chunk:
                self._on_chunk(sample.astype(np.float32), int(self._t * 10))
            time.sleep(0.1)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
