# -*- coding: utf-8 -*-
"""Overlay smoke test: start window, push entries, stop."""
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")
from realtime_translation.overlay import SubtitleOverlay
from realtime_translation.pipeline import TranscriptEntry

ov = SubtitleOverlay()
ov.start()
print("overlay started, ready =", ov._ready.is_set(), flush=True)

ov.on_entry(TranscriptEntry(ts=datetime.now(), channel="loopback", text="昨天是 monday 今天天气不错", partial=False))
ov.on_entry(TranscriptEntry(
    ts=datetime.now(), channel="loopback",
    text="今天 project 的 performance 很好",
    translated="Today the project's performance is excellent",
    translate_direction="zh2en", partial=False,
))
time.sleep(0.8)
ov.toggle_translation()  # hide translation
time.sleep(0.5)
ov.toggle_translation()  # show again
time.sleep(0.5)
ov.on_entry(TranscriptEntry(ts=datetime.now(), channel="loopback", text="hello world", partial=True))
time.sleep(0.8)
ov.request_stop()
time.sleep(1.0)
print("overlay stopped cleanly", flush=True)
