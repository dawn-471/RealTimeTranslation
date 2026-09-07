# -*- coding: utf-8 -*-
"""WASAPI loopback capture for Windows (PyAudioWPatch).

Captures the system's output audio (whatever plays on the speakers —
Tencent Meeting, video players, etc.) via WASAPI loopback, resamples to
16kHz mono float32, and pushes chunks of ~100ms to a callback.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

log = logging.getLogger(__name__)

# 100 ms of samples at 16 kHz
DEFAULT_CHUNK_MS = 100


def _pyaudio():
    import pyaudiowpatch as pyaudio  # PyAudioWPatch exports the pyaudio module name
    return pyaudio.PyAudio()


def _wasapi_host_index(pa) -> int:
    """Return the WASAPI host API index (paWASAPI), or -1 if unavailable."""
    for i in range(pa.get_host_api_count()):
        if pa.get_host_api_info_by_index(i).get("type") == _pyaudio_module().paWASAPI:
            return i
    return -1


def _pyaudio_module():
    import pyaudiowpatch as pyaudio
    return pyaudio


def list_loopback_devices() -> list[tuple[int, str]]:
    """Return [(index, name), ...] for WASAPI loopback (system output) devices."""
    pa = _pyaudio()
    try:
        devices: list[tuple[int, str]] = []
        for info in pa.get_loopback_device_info_generator():
            idx = info.get("index")
            name = info.get("name", f"device {idx}")
            devices.append((idx, name))
        return devices
    except Exception as exc:
        log.warning("WASAPI loopback enumeration failed: %s", exc)
        return []
    finally:
        pa.terminate()


def list_input_devices() -> list[tuple[int, str]]:
    """Return [(index, name), ...] for physical input (microphone) devices."""
    pa = _pyaudio()
    try:
        loopback_idxs = {d.get("index") for d in pa.get_loopback_device_info_generator()}
    except Exception:
        loopback_idxs = set()
    try:
        devices: list[tuple[int, str]] = []
        for idx in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(idx)
            if info.get("maxInputChannels", 0) <= 0:
                continue
            if info.get("hostApi") != _wasapi_host_index(pa):
                continue
            if idx in loopback_idxs or "[Loopback]" in info.get("name", ""):
                continue
            devices.append((idx, info.get("name", f"device {idx}")))
        return devices
    except Exception as exc:
        log.warning("input device enumeration failed: %s", exc)
        return []
    finally:
        pa.terminate()


def validate_device_index(value) -> int:
    """Accept int (or numeric string); reject floats that aren't whole numbers."""
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return -1
        try:
            value = float(value)
        except ValueError:
            raise ValueError(f"invalid device index: {value!r}")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"device index must be an integer, got {value}")
        value = int(value)
    return int(value)


def resample_to_16k_mono(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Resample arbitrary (n, ch) float32 audio to 16kHz mono float32.

    Uses linear interpolation (adequate for ASR input; zero deps).
    """
    if samples.ndim == 2:
        samples = samples.mean(axis=1)  # mono mixdown
    samples = np.ascontiguousarray(samples, dtype=np.float32)
    if sample_rate != 16000:
        n_out = int(round(len(samples) * 16000 / sample_rate))
        x_in = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
        x_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        samples = np.interp(x_out, x_in, samples).astype(np.float32)
    return np.clip(samples, -1.0, 1.0)


class LoopbackCapture:
    """WASAPI loopback capture streaming 16kHz mono float32 chunks.

    Usage:
        cap = LoopbackCapture(index)
        cap.start(on_chunk=lambda chunk, frame: ...)
        ... later ...
        cap.stop()
    """

    def __init__(self, index: int, sample_rate: int = 16000, chunk_ms: int = DEFAULT_CHUNK_MS):
        self.index = validate_device_index(index)
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self._chunk_samples = 0  # set on start (native rate)
        self._pa = None
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_chunk: Optional[Callable[[np.ndarray, int], None]] = None

    def start(self, on_chunk: Callable[[np.ndarray, int], None]) -> None:
        """Open the loopback stream (blocking) and spawn the reader thread."""
        import pyaudiowpatch as _pa_mod
        pa = _pyaudio()
        self._pa = pa
        info = pa.get_device_info_by_index(self.index)
        native_rate = int(info.get("defaultSampleRate", 48000))
        in_ch = max(int(info.get("maxInputChannels", 1)), 1)
        self._chunk_samples = max(int(float(native_rate) * self.chunk_ms / 1000), 160)
        self._on_chunk = on_chunk
        self._stop.clear()
        stream = pa.open(
            format=_pa_mod.paFloat32,
            channels=in_ch,
            rate=native_rate,
            input=True,
            input_device_index=self.index,
            frames_per_buffer=self._chunk_samples,
        )
        self._stream = stream
        self._thread = threading.Thread(target=self._loop, name="loopback-capture", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        assert self._stream is not None
        frame = 0
        while not self._stop.is_set():
            try:
                raw = self._stream.read(self._chunk_samples, exception_on_overflow=False)
            except OSError:
                break
            if not raw:
                continue
            arr = np.frombuffer(raw, dtype=np.float32)
            arr = resample_to_16k_mono(arr, int(self._stream.get_sample_rate()))
            if self._on_chunk:
                self._on_chunk(arr, frame)
            frame += 1

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            finally:
                self._stream = None
