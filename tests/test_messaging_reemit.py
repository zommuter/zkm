"""Red-test spec for `zkm.testing.assert_reemit_identical` (ROADMAP id:ab8b).

A shared contract-test helper every messaging plugin (whatsapp/telegram/signal/threema)
uses to assert deterministic emission: running an emit function twice over the same source
produces byte-identical files. RED until `src/zkm/testing.py` exists.

Contract:
- `assert_reemit_identical(emit)` where `emit` is a zero-arg callable that writes files and
  returns the iterable of written `Path`s.
- It calls `emit()`, snapshots the bytes of the returned paths, calls `emit()` again, and
  asserts every path's bytes are unchanged. On any difference it raises `AssertionError`
  naming the offending path.
"""

from __future__ import annotations

from pathlib import Path


def test_deterministic_emit_passes(tmp_path: Path):  # roadmap:ab8b
    from zkm.testing import assert_reemit_identical

    target = tmp_path / "day.md"

    def emit():
        target.write_text("[14:30] Alice: hello\n", encoding="utf-8")
        return [target]

    # must NOT raise for a deterministic emitter
    assert_reemit_identical(emit)


def test_nondeterministic_emit_raises(tmp_path: Path):  # roadmap:ab8b
    import pytest

    from zkm.testing import assert_reemit_identical

    target = tmp_path / "day.md"
    counter = {"n": 0}

    def emit():
        counter["n"] += 1
        target.write_text(f"run {counter['n']}\n", encoding="utf-8")
        return [target]

    with pytest.raises(AssertionError):
        assert_reemit_identical(emit)
