# -*- coding: utf-8 -*-
"""Download the sherpa-onnx streaming paraformer bilingual zh-en model.

Idempotent: skips files that already exist and pass size check.
Mirrors: hf-mirror.com (CN) — set HF_ENDPOINT env var for other mirrors.

    uv run python scripts/download_models.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
HF_REPO = "csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en"
BASE = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
FILES = ["encoder.int8.onnx", "decoder.int8.onnx", "tokens.txt"]


def _fetch(url: str, dest: Path) -> None:
    import urllib.request
    print(f"  downloading {url} -> {dest.name}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    if dest.exists() and dest.stat().st_size != tmp.stat().st_size:
        # keep the previous successful file
        tmp.unlink()
        return
    tmp.replace(dest)


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        dest = MODEL_DIR / f
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  {f} already present ({dest.stat().st_size // 1024} KB)")
            continue
        _fetch(f"{BASE}/{HF_REPO}/resolve/main/{f}", dest)
    # sanity
    required = [MODEL_DIR / f for f in FILES]
    missing = [f for f in required if not f.exists() or f.stat().st_size == 0]
    if missing:
        print(f"[error] missing: {[m.name for m in missing]}")
        return 1
    print(f"model ready in {MODEL_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
