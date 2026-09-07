# -*- coding: utf-8 -*-
"""Floating subtitle overlay (tkinter, always-on-top, semi-transparent).

Displayed above everything else like a video subtitle: original line
(white, big) + translation line (grey, smaller). Toggle translation with
'T' (global hotkey handled by caller), drag with mouse, quit with 'Q'.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)


class SubtitleOverlay:
    """Runs a tkinter window in its own thread (tkinter must be main-thread
    only per-OS rules, so we isolate it; the pipeline pushes text in)."""

    def __init__(self, font_size: int = 20, max_lines: int = 3):
        self.font_size = font_size
        self.max_lines = max_lines
        self._show_translation = True
        self._lines: list[tuple[str, Optional[str]]] = []  # (original, translated)
        self._partial: Optional[str] = None
        self._lock = threading.Lock()
        self._root = None
        self._text_widget = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._drag = {"x": 0, "y": 0}

    # ---- pipeline feed (any thread) ----
    def on_entry(self, entry) -> None:
        with self._lock:
            if entry.partial:
                self._partial = entry.text
            else:
                self._partial = None
                self._lines.append((entry.text, entry.translated))
                if len(self._lines) > self.max_lines:
                    self._lines = self._lines[-self.max_lines:]
        self._schedule_refresh()

    def toggle_translation(self) -> None:
        with self._lock:
            self._show_translation = not self._show_translation
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        root = self._root
        if root is not None:
            try:
                root.after(0, self._refresh)
            except Exception:
                pass

    def request_stop(self) -> None:
        self._stop.set()
        if self._root is not None:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    # ---- tkinter thread ----
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="overlay-tk")
        self._thread.start()
        self._ready.wait(timeout=10.0)

    def _run(self) -> None:
        import tkinter as tk

        self._root = tk.Tk()
        self._root.overrideredirect(True)          # borderless
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.88)
        except Exception:
            pass
        # bottom-right position
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"+{sw - 620}+{sh - 180}")
        self._root.configure(bg="#111111")
        self._text_widget = tk.Label(
            self._root,
            justify="left",
            anchor="w",
            fg="#ffffff",
            bg="#111111",
            font=("Microsoft YaHei UI", self.font_size),
            wraplength=600,
        )
        self._text_widget.pack(padx=12, pady=8)

        # draggable
        def on_press(e):
            self._drag["x"], self._drag["y"] = e.x, e.y

        def on_drag(e):
            x = self._root.winfo_x() + e.x - self._drag["x"]
            y = self._root.winfo_y() + e.y - self._drag["y"]
            self._root.geometry(f"+{x}+{y}")

        self._root.bind("<ButtonPress-1>", on_press)
        self._root.bind("<B1-Motion>", on_drag)

        self._refresh()
        self._ready.set()
        self._root.mainloop()

    def _refresh(self) -> None:
        if self._text_widget is None:
            return
        with self._lock:
            lines = list(self._lines)
            partial = self._partial
            show_trans = self._show_translation
        text_parts = []
        for orig, trans in lines:
            text_parts.append(orig)
            if show_trans and trans:
                text_parts.append(f" ↳ {trans}")
        if partial:
            text_parts.append(f"… {partial}")
        content = "\n".join(text_parts) if text_parts else "MeetingTranscriber"
        try:
            self._text_widget.configure(text=content)
        except Exception:
            pass
