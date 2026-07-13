"""Shared test-contract helpers for zkm plugins.

Provides `assert_reemit_identical` — the byte-identical-reemit contract helper
every messaging plugin uses to assert deterministic emission.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path


def assert_reemit_identical(emit: Callable[[], Iterable[Path]]) -> None:
    """Assert that calling *emit* twice produces byte-identical output files.

    *emit* is a zero-arg callable that writes files and returns an iterable of
    the written `Path`s. This helper calls `emit()`, snapshots the bytes of the
    returned paths, calls `emit()` again, and asserts every path's bytes are
    unchanged.

    Raises `AssertionError` naming the first offending path if any file differs
    between the two runs.

    This is the contract every messaging plugin (whatsapp, telegram, signal,
    threema) must satisfy — see docs/messaging-spec.md §Deterministic emission.
    """
    first_paths = list(emit())
    snapshot: dict[Path, bytes] = {p: p.read_bytes() for p in first_paths}

    second_paths = list(emit())

    # Check paths returned by second emit match first
    for p in second_paths:
        first_bytes = snapshot.get(p)
        if first_bytes is None:
            # New path only appeared in second run — that's also non-deterministic
            raise AssertionError(
                f"assert_reemit_identical: path {p!r} appeared only in second emit"
            )
        second_bytes = p.read_bytes()
        if first_bytes != second_bytes:
            raise AssertionError(
                f"assert_reemit_identical: file is not byte-identical between runs: {p!r}"
            )

    # Check that no paths from the first run disappeared in the second
    second_set = set(second_paths)
    for p in first_paths:
        if p not in second_set:
            raise AssertionError(
                f"assert_reemit_identical: path {p!r} disappeared in second emit"
            )
