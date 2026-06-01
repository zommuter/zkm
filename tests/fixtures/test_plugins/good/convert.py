"""Minimal conformant test plugin."""

from __future__ import annotations

from pathlib import Path


def convert(
    store_path: Path,
    config: dict,
    *,
    progress=None,
) -> list[Path]:
    source_dir = Path(config.get("source_dir", store_path / "corpus"))
    notes_dir = store_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    produced = []
    for src in sorted(source_dir.rglob("*")):
        if not src.is_file():
            continue
        out = notes_dir / (src.stem + ".md")
        body = src.read_text(encoding="utf-8")
        out.write_text(
            f"""---
source: good
date: 2026-01-01T10:00:00+01:00
tags: []
sha256: deadbeef00000000000000000000000000000000000000000000000000000001
processor: good
processor_version: 0.1.0
---

{body}""",
            encoding="utf-8",
        )
        produced.append(out)
        if progress:
            progress(len(produced), None, src.name)
    return produced
