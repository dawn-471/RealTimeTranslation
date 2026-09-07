# -*- coding: utf-8 -*-
"""Tests for audio_capture: device enumeration and parameter validation.

These tests must not require real audio hardware — enumeration is wrapped in
try/except inside the module so CI machines without devices still pass.
"""
import numpy as np
import pytest

from realtime_translation.audio_capture import (
    list_loopback_devices,
    list_input_devices,
    validate_device_index,
    resample_to_16k_mono,
)


def test_list_loopback_devices_returns_unique_pairs():
    devs = list_loopback_devices()
    assert isinstance(devs, list)
    for idx, name in devs:
        assert isinstance(idx, int)
        assert isinstance(name, str)
        assert name


def test_list_input_devices_returns_unique_pairs():
    devs = list_input_devices()
    assert isinstance(devs, list)
    for idx, name in devs:
        assert isinstance(idx, int)
        assert isinstance(name, str)
        assert name


def test_validate_device_index_accepts_float_and_negative():
    # negative means "auto/default" in our CLI convention
    assert validate_device_index(-1) == -1
    assert validate_device_index(2) == 2
    assert validate_device_index(0) == 0


def test_validate_device_index_rejects_float():
    with pytest.raises(ValueError):
        validate_device_index(1.5)


def test_resample_48k_stereo_to_16k_mono():
    sr = 48000
    dur_s = 0.1
    t = np.arange(int(sr * dur_s)) / sr
    left = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    right = np.sin(2 * np.pi * 660 * t).astype(np.float32)
    stereo = np.stack([left, right], axis=1)
    mono = resample_to_16k_mono(stereo, sr)
    assert mono.dtype == np.float32
    # 16kHz mono for 100ms
    assert mono.shape[0] == 1600
    assert mono.ndim == 1
    assert np.abs(mono).max() <= 1.0


def test_resample_16k_mono_is_identity():
    sr = 16000
    t = np.arange(int(sr * 0.1)) / sr
    mono = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    out = resample_to_16k_mono(mono, sr)
    assert out.shape[0] == 1600
    np.testing.assert_allclose(out, mono, atol=1e-6)


def test_resample_44k_to_16k_length():
    sr = 44100
    n = sr  # 1 second
    data = np.zeros((n, 2), dtype=np.float32)
    mono = resample_to_16k_mono(data, sr)
    assert mono.shape[0] == 16000
