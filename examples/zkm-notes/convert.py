"""zkm-notes — sample zkm plugin.

Imports plain .txt/.md files from a directory into the store's notes/ subdir,
adding YAML frontmatter. Re-running is safe: files are deduped by sha256.

This file serves as the canonical example of the zkm plugin interface.
See docs/plugin-spec.md in the zkm repo for the full contract.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

SUFFIXES = {".txt", ".md", ".markdown"}


def convert(store_path: Path, config: dict) -> list[Path]:
    """
    Import notes from NOTES_SOURCE_DIR into store_path/notes/.

    Returns a list of paths to newly created .md files.
    """
    src = Path(config["NOTES_SOURCE_DIR"]).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"NOTES_SOURCE_DIR does not exist: {src}")

    notes_dir = store_path / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    default_tags = [
        t.strip() for t in config.get("NOTES_DEFAULT_TAGS", "").split(",") if t.strip()
    ]
    existing_shas = _scan_existing_shas(notes_dir)

    created: list[Path] = []
    for src_file in sorted(src.rglob("*")):
        if not src_file.is_file() or src_file.suffix.lower() not in SUFFIXES:
            continue

        raw = src_file.read_text(encoding="utf-8", errors="replace")
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if sha in existing_shas:
            continue

        mtime = datetime.fromtimestamp(src_file.stat().st_mtime, tz=timezone.utc).astimezone()
        date_str = mtime.isoformat(timespec="seconds")

        try:
            post = frontmatter.loads(raw)
            body = post.content
            meta = dict(post.metadata)
        except Exception:
            body = raw
            meta = {}

        meta.setdefault("source", "notes")
        meta.setdefault("date", date_str)
        existing_tags = list(meta.get("tags") or [])
        meta["tags"] = existing_tags + [t for t in default_tags if t not in existing_tags]
        meta["sha256"] = sha
        meta["original_path"] = str(src_file)

        slug = _slugify(src_file.stem)
        out = _unique_path(notes_dir, date_str[:10], slug)

        new_post = frontmatter.Post(body, **meta)
        out.write_text(frontmatter.dumps(new_post), encoding="utf-8")
        created.append(out)
        existing_shas.add(sha)

    return created


def _scan_existing_shas(directory: Path) -> set[str]:
    shas: set[str] = set()
    for md in directory.rglob("*.md"):
        try:
            post = frontmatter.load(md)
            sha = post.metadata.get("sha256")
            if isinstance(sha, str):
                shas.add(sha)
        except Exception:
            continue
    return shas


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "note"


def _unique_path(directory: Path, date_prefix: str, slug: str) -> Path:
    candidate = directory / f"{date_prefix}_{slug}.md"
    i = 1
    while candidate.exists():
        candidate = directory / f"{date_prefix}_{slug}_{i}.md"
        i += 1
    return candidate
