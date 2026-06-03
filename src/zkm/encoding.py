"""Charset detection and text hardening utilities.

Shared by plugins that decode raw bytes from heterogeneous sources
(vCard, email, scan OCR, etc.) where the declared encoding may be absent
or wrong.
"""
from __future__ import annotations

import ftfy
from charset_normalizer import from_bytes as _cn_from_bytes


def post_decode(text: str) -> str:
    """Strip BOM, repair mojibake with ftfy, NFC-normalise."""
    text = text.lstrip("﻿")  # UTF-8 / UTF-16 BOM
    return ftfy.fix_text(
        text,
        uncurl_quotes=False,
        fix_line_breaks=False,
        fix_latin_ligatures=False,
        fix_character_width=False,
        normalization="NFC",
    )


def decode_bytes(raw: bytes, *, hint: str | None = None) -> str:
    """Decode raw bytes to str with charset detection fallback.

    Chain: hint → utf-8 strict → charset-normalizer detection → errors=replace.
    ``post_decode`` (BOM strip + ftfy) is applied to whichever path succeeds.

    Args:
        raw: Raw bytes to decode.
        hint: Optional declared encoding (e.g. from a CHARSET= property param).
              Skipped if it raises; the chain continues from utf-8.
    """
    if hint:
        try:
            return post_decode(raw.decode(hint))
        except (UnicodeDecodeError, LookupError):
            pass

    try:
        return post_decode(raw.decode("utf-8"))
    except UnicodeDecodeError:
        pass

    result = _cn_from_bytes(raw).best()
    if result is not None:
        return post_decode(str(result))

    return post_decode(raw.decode("utf-8", errors="replace"))
