"""Plugin that emits frontmatter missing sha256 and processor."""

from __future__ import annotations

from pathlib import Path


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    notes_dir = store_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    out = notes_dir / "note.md"
    # Intentionally omit sha256 and processor
    out.write_text(
        "---\nsource: bad-frontmatter\ndate: 2026-01-01T10:00:00+01:00\ntags: []\nprocessor_version: 0.1.0\n---\nHello.\n",
        encoding="utf-8",
    )
    return [out]
