"""Plugin with non-conformant convert() signature (missing progress)."""

from pathlib import Path


def convert(store_path: Path, config: dict) -> list[Path]:  # missing progress kwarg
    return []
