# roadmap:83c7
"""Spec tests for amendment-queue visibility (ROADMAP id:83c7, currently RED).

Contract: `zkm doctor` prints an informational `amendment queue` row (total
pending records + per-emitter breakdown) when `<store>/.zkm-state/amendments/`
holds at least one record; the id:dd89 zero-created skip notice appends the
pending count when the queue is non-empty. Queue-empty behaviour stays
byte-identical to today's (no row, unchanged notice).

Tests marked GUARD pass pre-implementation; they pin behaviour the green
implementation must not break.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic doctor runs: endpoint probes fail fast either way."""

    def _refuse(*args, **kwargs):
        raise httpx.ConnectError("test: no network")

    monkeypatch.setattr(httpx, "post", _refuse)
    monkeypatch.setattr(httpx, "get", _refuse, raising=False)


def _emit_records(store: Path, n: int, emitter: str = "ner") -> None:
    from zkm.amendments import emit

    for i in range(n):
        emit(
            store,
            key={"sha256": f"{i:064x}"},
            fields={"tags": [f"{emitter}-tag-{i}"]},
            emitted_by=emitter,
        )


def _doctor(store: Path):
    from zkm.cli import main

    return CliRunner().invoke(main, ["doctor", "--store", str(store)])


def _write_zero_primary(pdir: Path) -> None:
    """A primary converter plugin that always creates zero files."""
    d = pdir / "zkm-prim0"
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(
        "name: prim0\nversion: 0.1.0\ndescription: test fixture\ncreates_dirs: [notes]\n"
    )
    (d / "convert.py").write_text("def convert(store_path, config):\n    return []\n")


def _convert_prim0(store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))
    _write_zero_primary(pdir)
    from zkm.cli import main

    runner = CliRunner()
    return runner.invoke(main, ["convert", "prim0", "--store", str(store), "--no-commit"])


def _all_output(result) -> str:
    """stdout + stderr regardless of click version (8.1 mixes, 8.2+ separates)."""
    try:
        return result.output + result.stderr
    except (AttributeError, ValueError):
        return result.output


# ---------------------------------------------------------------------------
# RED spec
# ---------------------------------------------------------------------------


def test_doctor_reports_pending_amendment_queue(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _block_network(monkeypatch)
    _emit_records(store, 2, emitter="ner")
    _emit_records(store, 1, emitter="notmuch")

    result = _doctor(store)
    rows = [ln for ln in result.output.splitlines() if "amendment queue" in ln.lower()]
    assert rows, f"no 'amendment queue' row in doctor output:\n{result.output}"
    row = rows[0]
    assert "3" in row  # total pending records
    assert "ner: 2" in row
    assert "notmuch: 1" in row


def test_doctor_queue_row_keeps_exit_code(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Informational only: pending records must not change doctor's exit code.

    RED via the row-presence assertion; the exit-code comparison is the spec.
    """
    _block_network(monkeypatch)
    baseline = _doctor(store)

    _emit_records(store, 1)
    result = _doctor(store)
    assert "amendment queue" in result.output.lower()
    assert result.exit_code == baseline.exit_code


def test_zero_created_notice_mentions_queued_amendments(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _emit_records(store, 2)
    result = _convert_prim0(store, tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "Skipping amenders (0 files created; 2 queued amendment(s) pending)" in (
        _all_output(result)
    )


# ---------------------------------------------------------------------------
# GUARDs (green pre-implementation — protect against over-implementation)
# ---------------------------------------------------------------------------


def test_doctor_no_queue_row_when_queue_empty(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: an empty/absent queue prints no row at all (not a zero row)."""
    _block_network(monkeypatch)
    result = _doctor(store)
    assert "amendment queue" not in result.output.lower()


def test_skip_notice_unchanged_when_queue_empty(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: with nothing queued, the id:dd89 notice stays byte-identical."""
    result = _convert_prim0(store, tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    out = _all_output(result)
    assert "Skipping amenders (0 files created)" in out
    assert "pending" not in out
