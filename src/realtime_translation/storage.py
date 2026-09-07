# -*- coding: utf-8 -*-
"""Persistent transcript storage: JSONL append + Markdown export."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from .pipeline import TranscriptEntry


class TranscriptStorage:
    def __init__(self, output_dir: str, session_prefix: str = "transcript"):
        os.makedirs(output_dir, exist_ok=True)
        self.output_dir = output_dir
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.path = os.path.join(output_dir, f"{session_prefix}-{stamp}.jsonl")
        self._count = 0

    def append(self, entry: TranscriptEntry) -> None:
        if entry.partial:
            return
        self._count += 1
        record = {
            "ts": entry.ts.isoformat(timespec="milliseconds"),
            "channel": entry.channel,
            "text": entry.text,
            "translated": entry.translated,
            "translate_failed": entry.translate_failed,
            "translate_direction": entry.translate_direction,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def export_markdown(self) -> str:
        """Return markdown of the whole transcript (with translations)."""
        lines = ["# 会议转写 / Meeting Transcript\n"]
        if not os.path.exists(self.path):
            return "\n".join(lines)
        with open(self.path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                d = json.loads(raw)
                ts = datetime.fromisoformat(d["ts"]).strftime("%H:%M:%S")
                lines.append(f"**{ts}** [{d['channel']}] {d['text']}")
                if d.get("translated"):
                    lines.append(f"  ↳ {d['translated']}")
                elif d.get("translate_failed"):
                    lines.append("  ↳ [translate failed]")
        return "\n".join(lines) + "\n"

    def save_markdown(self) -> str:
        """Write the markdown export to disk; return its path."""
        md_path = self.path.replace(".jsonl", ".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.export_markdown())
        return md_path
