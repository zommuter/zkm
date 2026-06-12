# roadmap:dd89
"""Spec tests for skipping the amender pass on zero-created converts
(ROADMAP id:dd89, currently RED).

Contract: after a non-amender `zkm convert <plugin>` that created zero files
(and was not cancelled), the CLI does NOT invoke any amender and prints
"Skipping amenders (0 files created)" to stderr. Amenders still run when at
least one file was created; the cancelled path keeps skipping them.

Tests marked GUARD pass pre-implementation; they pin behaviour the green
implementation must not break (i.e. don't skip amenders unconditionally).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

MARKER = ".amender-ran"


def _write_plugin(pdir: Path, name: str, kind: str, convert_body: str) -> None:
    d = pdir / f"zkm-{name}"
    d.mkdir(parents=True)
    kind_line = f"kind: {kind}\n" if kind else ""
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: test fixture\n"
        f"{kind_line}creates_dirs: [notes]\n"
    )
    (d / "convert.py").write_text(convert_body)


@pytest.fixture()
def plugin_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated plugins dir with one amender (writes a marker file when run)."""
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))

    _write_plugin(
        pdir,
        "amark",
        "amender",
        textwrap.dedent(
            """\
            from pathlib import Path

            def convert(store_path, config, *, created=None):
                (Path(store_path) / ".amender-ran").write_text(
                    "none" if created is None else str(len(created))
                )
                return []
            """
        ),
    )
    return pdir


def _add_primary(pdir: Path, name: str, n_files: int) -> None:
    """Primary converter creating n_files notes (0 → empty created list)."""
    _write_plugin(
        pdir,
        name,
        "",
        textwrap.dedent(
            f"""\
            from pathlib import Path

            def convert(store_path, config):
                out = []
                for i in range({n_files}):
                    p = Path(store_path) / "notes" / f"{name}-{{i}}.md"
                    p.write_text("---\\nsource: {name}\\n---\\nbody\\n")
                    out.append(p)
                return out
            """
        ),
    )


def _invoke_convert(store: Path, plugin: str):
    from zkm.cli import main

    runner = CliRunner()
    return runner.invoke(main, ["convert", plugin, "--store", str(store), "--no-commit"])


def _all_output(result) -> str:
    """stdout + stderr regardless of click version (8.1 mixes, 8.2+ separates)."""
    try:
        return result.output + result.stderr
    except (AttributeError, ValueError):
        return result.output


# ---------------------------------------------------------------------------
# RED spec
# ---------------------------------------------------------------------------


def test_zero_created_skips_amenders(store: Path, plugin_env: Path) -> None:
    _add_primary(plugin_env, "prim0", 0)
    result = _invoke_convert(store, "prim0")
    assert result.exit_code == 0, result.output
    assert not (store / MARKER).exists(), (
        "amender ran despite the primary convert creating zero files"
    )


def test_zero_created_prints_skip_notice(store: Path, plugin_env: Path) -> None:
    _add_primary(plugin_env, "prim0", 0)
    result = _invoke_convert(store, "prim0")
    assert "Skipping amenders (0 files created)" in _all_output(result)


# ---------------------------------------------------------------------------
# GUARDs (green pre-implementation — protect against over-implementation)
# ---------------------------------------------------------------------------


def test_nonzero_created_still_runs_amenders(store: Path, plugin_env: Path) -> None:
    """GUARD: a convert that created files must still trigger the amender pass."""
    _add_primary(plugin_env, "prim1", 1)
    result = _invoke_convert(store, "prim1")
    assert result.exit_code == 0, result.output
    marker = store / MARKER
    assert marker.exists()
    assert marker.read_text() == "1"  # created list forwarded, scoped to 1 file


def test_cancelled_convert_skips_amenders(store: Path, plugin_env: Path) -> None:
    """GUARD: the cancelled path already skips amenders; keep it that way."""
    _write_plugin(
        plugin_env,
        "primc",
        "",
        "def convert(store_path, config):\n    raise KeyboardInterrupt()\n",
    )
    result = _invoke_convert(store, "primc")
    assert result.exit_code == 130
    assert not (store / MARKER).exists()
