"""Stub convert for bad_manifest fixture — interface is valid, manifest is not."""

from pathlib import Path


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    return []
