# -*- coding: utf-8 -*-
"""Chinese characters ratio based source-language detection."""
from __future__ import annotations

import re

_CJK = re.compile(r"[\u4e00-\u9fff]")


def detect_direction(text: str) -> str:
    """Return "zh2en" | "en2zh" | "none".

    Rule: if the CJK ratio (CJK chars / non-space chars) >= 0.3, the text is
    treated as Chinese (translate to English); otherwise as English (translate
    to Chinese). Short texts with no CJK or empty text -> "none".
    """
    if not text or not text.strip():
        return "none"
    compact = re.sub(r"\s", "", text)
    if not compact:
        return "none"
    total = 0
    cjk = 0
    for ch in compact:
        # only count letters/numbers (skip punctuation) for the ratio
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            total += 1
            if _CJK.match(ch):
                cjk += 1
    if total == 0:
        return "none"
    ratio = cjk / total
    if ratio >= 0.15:
        return "zh2en"
    return "en2zh"
