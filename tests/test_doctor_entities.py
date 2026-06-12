# roadmap:1a6f
"""Spec tests for `zkm doctor --entities` (ROADMAP id:1a6f, currently RED).

Contract: `zkm doctor --entities` sweeps store frontmatter and prints a
`suspicious entities` row — total count of entities[] slots with
`valid: false` plus a per-type breakdown — informational only. Without the
flag, no frontmatter sweep happens and no such row is printed (the sweep is
O(store), opt-in by design). Serves the TODO.md deferral triggers that need a
`valid: false` counter (checksum-fail policy at >=50; 1-month forward-flag).

Tests marked GUARD pass pre-implementation; they pin behaviour the green
implementation must not break.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

_SUSPICIOUS_FM = textwrap.dedent(
    """\
    source: notes
    date: 2026-06-12T10:00:00+02:00
    entities:
      - {type: iban, value: "CH00 1234 BAD", valid: false}
      - {type: iban, value: "CH93 0076 2011 6238 5295 7", valid: true}
      - {type: date, value: "2026-13-40", valid: false}
      - {type: person, value: "Alice Example"}"""
)

_EXTRA_FM = textwrap.dedent(
    """\
    source: notes
    entities:
      - {type: iban, value: "DE00 0000 BAD", valid: false}"""
)


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic doctor runs: endpoint probes fail fast either way."""

    def _refuse(*args, **kwargs):
        raise httpx.ConnectError("test: no network")

    monkeypatch.setattr(httpx, "post", _refuse)
    monkeypatch.setattr(httpx, "get", _refuse, raising=False)


def _doctor(store: Path, *extra: str):
    from zkm.cli import main

    return CliRunner().invoke(main, ["doctor", "--store", str(store), *extra])


def _row(result, label: str) -> str:
    rows = [ln for ln in result.output.splitlines() if label in ln.lower()]
    assert rows, f"no '{label}' row in doctor output:\n{result.output}"
    return rows[0]


# ---------------------------------------------------------------------------
# RED spec
# ---------------------------------------------------------------------------


def test_doctor_entities_counts_valid_false(
    store: Path, make_note: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """valid: false slots are counted across files, with a per-type breakdown;
    valid: true and valid-less slots are not counted."""
    _block_network(monkeypatch)
    make_note("notes/a.md", "body a", _SUSPICIOUS_FM)
    make_note("notes/b.md", "body b", _EXTRA_FM)

    result = _doctor(store, "--entities")
    row = _row(result, "suspicious entities")
    assert "3" in row  # 2 iban + 1 date across both files
    assert "iban: 2" in row
    assert "date: 1" in row
    assert "person" not in row  # no valid key -> not suspicious


def test_doctor_entities_reports_zero_with_flag(
    store: Path, make_note: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the flag, the row prints even at 0 (explicit observation)."""
    _block_network(monkeypatch)
    make_note("notes/clean.md", "body", "source: notes\ntags: []")

    result = _doctor(store, "--entities")
    row = _row(result, "suspicious entities")
    assert "0" in row


def test_doctor_entities_keeps_exit_code(
    store: Path, make_note: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Informational only: suspicious entities must not flip doctor's exit code."""
    _block_network(monkeypatch)
    baseline = _doctor(store)

    make_note("notes/a.md", "body", _SUSPICIOUS_FM)
    result = _doctor(store, "--entities")
    assert "suspicious entities" in result.output.lower()
    assert result.exit_code == baseline.exit_code


# ---------------------------------------------------------------------------
# GUARDs (green pre-implementation — protect against over-implementation)
# ---------------------------------------------------------------------------


def test_doctor_default_has_no_entities_row(
    store: Path, make_note: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: without --entities, doctor stays sweep-free and row-free."""
    _block_network(monkeypatch)
    make_note("notes/a.md", "body", _SUSPICIOUS_FM)

    result = _doctor(store)
    assert "suspicious entities" not in result.output.lower()
