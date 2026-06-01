"""Conformant plugin with no conformance fixtures declared."""

from pathlib import Path


def convert(store_path: Path, config: dict, *, progress=None) -> list[Path]:
    return []
