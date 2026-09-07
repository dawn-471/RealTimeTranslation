# -*- coding: utf-8 -*-
"""Terminal UI: rich Live subtitle panel.

Displays a rolling list of final entries (original + translation), a
live partial line at the bottom, and a status header. Keyboard:
    T  - toggle translation display
    Q / Ctrl+C - quit
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from .pipeline import TranscriptEntry

log = logging.getLogger(__name__)

MAX_ROWS = 20


def format_timestamp(ts: str) -> str:
    return ts


def format_original_line(ts: str, channel: str, text: str) -> str:
    tag = "loopback" if channel == "loopback" else "mic"
    return f"{ts} │ [{tag}] {text}"


def format_translation_line(source: str, translated: str) -> Optional[str]:
    if not translated:
        return None
    return f"      ↳ {translated}"


@dataclass
class StatusLine:
    total: int = 0
    finals: int = 0
    failed: int = 0
    backend: str = "off"

    def __str__(self) -> str:
        return (
            f"进 {self.total} 段 | final {self.finals} | 失败 {self.failed}"
            f" | 后端 {self.backend}"
        )


class SubtitlePanel:
    """Subscribes to a Pipeline and renders a live rich panel.

    run() owns the Live context. Keyboard handling belongs to the caller:
    call toggle_translation() from any thread (a hotkey listener or the
    main loop), and stop by raising KeyboardInterrupt or calling stop().
    """

    def __init__(self, backend_name: str = "off", max_rows: int = MAX_ROWS):
        self.backend_name = backend_name
        self.max_rows = max_rows
        self._entries: list[TranscriptEntry] = []
        self._partial_texts: dict[str, str] = {}  # channel -> latest partial
        self._status = StatusLine(backend=backend_name)
        self._show_translation = True
        self._lock = threading.Lock()
        self._console = Console()
        self._stop_event = threading.Event()
        self._live: Optional[Live] = None

    # ---- pipeline subscription (thread-safe) ----
    def on_entry(self, entry: TranscriptEntry) -> None:
        with self._lock:
            if entry.partial:
                self._partial_texts[entry.channel] = entry.text
                return
            if entry.channel in self._partial_texts:
                del self._partial_texts[entry.channel]
            self._entries.append(entry)
            if len(self._entries) > self.max_rows:
                self._entries = self._entries[-self.max_rows:]
            self._status.total += 1
            self._status.finals += 1
            if entry.translate_failed:
                self._status.failed += 1

    def toggle_translation(self) -> None:
        with self._lock:
            self._show_translation = not self._show_translation

    def request_stop(self) -> None:
        self._stop_event.set()

    # ---- rendering ----
    def _render(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style="white")
        with self._lock:
            entries = list(self._entries)
            partials = dict(self._partial_texts)
            show_trans = self._show_translation
        for e in entries:
            line = Text()
            line.append(format_timestamp(e.ts.strftime("%H:%M:%S")), style="dim")
            line.append(" │ ")
            line.append(e.text, style="bold white")
            table.add_row(line)
            if show_trans and e.translated:
                tline = Text()
                tline.append("      ↳ ", style="dim blue")
                tline.append(e.translated, style="blue")
                table.add_row(tline)
        for channel, text in partials.items():
            pline = Text()
            pline.append("  … ", style="dim")
            pline.append(text, style="italic grey70")
            table.add_row(pline)
        return table

    def _header(self) -> Table:
        header = Table.grid(padding=(0, 2))
        header.add_column(style="bold cyan")
        header.add_column(style="dim")
        header.add_row("MeetingTranscriber", str(self._status))
        header.add_row("热键", "T 译文开关 | Q 退出")
        return header

    def _render_full(self) -> Table:
        outer = Table.grid(padding=(0, 1))
        outer.add_column()
        outer.add_row(self._header())
        outer.add_row(self._render())
        return outer

    def run(self) -> None:
        """Render loop until request_stop() or KeyboardInterrupt."""
        with Live(self._render_full(), console=self._console,
                  refresh_per_second=10, screen=False) as live:
            self._live = live
            while not self._stop_event.is_set():
                live.update(self._render_full())
                time.sleep(0.25)
