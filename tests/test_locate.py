"""Tests for `zkm locate` — inventory-scoped path search (id:7f90).

Repro (real store, 2026-07-18): `zkm search darwinia` ranked all 4 indexed
find-dump shards below 15 chat/mail docs about the *game*. `locate()` scopes
search to `inventory/find-dump/**` shards only and matches path components
(substring + separator split + camelCase), so it never interleaves prose.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner

from zkm.cli import main
from zkm.index import build_index, save_index
from zkm.query import locate, path_tokenize


@pytest.fixture()
def indexed_store(store: Path, make_note: Callable[..., Path]) -> Path:
    make_note(
        "inventory/find-dump/Cee-834R/009x.md",
        "src/introversion/darwiniaandmultiwinia/darwinia/code/app.cpp\n"
        "movies/MediathekView.exe\n"
        "games/futurama/season1/ep01.mkv\n",
        "source: find-dump",
    )
    make_note(
        "chat/whatsapp/2026-07-18.md",
        "did you finish darwinia the game last night? so good.",
        "date: 2026-07-18\nsource: whatsapp",
    )
    idx = build_index(store)
    save_index(store, idx)
    return store


def test_locate_returns_shard_path_not_prose_doc(indexed_store: Path) -> None:
    hits = locate(indexed_store, "darwinia")
    paths = [h.path for h in hits]
    assert any("darwinia" in p for p in paths)
    assert all("whatsapp" not in h.drive_id and "chat" not in h.drive_id for h in hits)
    # the prose chat doc's own rel_path must never appear as a locate hit
    assert "chat/whatsapp/2026-07-18.md" not in paths


def test_locate_finds_concatenated_component(indexed_store: Path) -> None:
    hits = locate(indexed_store, "darwinia")
    assert any(
        "darwiniaandmultiwinia" in h.path or h.path.endswith("darwinia/code/app.cpp")
        for h in hits
    )


def test_locate_finds_camel_case_component(indexed_store: Path) -> None:
    hits = locate(indexed_store, "mediathek")
    paths = [h.path for h in hits]
    assert any("MediathekView" in p for p in paths)


def test_locate_reports_drive_id(indexed_store: Path) -> None:
    hits = locate(indexed_store, "futurama")
    assert hits
    assert all(h.drive_id == "Cee-834R" for h in hits)


def test_locate_no_match_returns_empty(indexed_store: Path) -> None:
    assert locate(indexed_store, "zzznomatchzzz") == []


def test_locate_raises_when_no_index(store: Path) -> None:
    with pytest.raises(FileNotFoundError, match="zkm index"):
        locate(store, "anything")


def test_locate_empty_term_returns_empty(indexed_store: Path) -> None:
    assert locate(indexed_store, "   ") == []


# ---------------------------------------------------------------------------
# path_tokenize
# ---------------------------------------------------------------------------


def test_path_tokenize_splits_separators() -> None:
    toks = path_tokenize("src/introversion/darwinia/code/app.cpp")
    assert "src" in toks
    assert "introversion" in toks
    assert "darwinia" in toks
    assert "app" in toks
    assert "cpp" in toks


def test_path_tokenize_splits_camel_case() -> None:
    toks = path_tokenize("MediathekView.exe")
    assert "mediathek" in toks
    assert "view" in toks


def test_path_tokenize_keeps_concatenated_word_whole() -> None:
    toks = path_tokenize("darwiniaandmultiwinia")
    assert toks == ["darwiniaandmultiwinia"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_locate_prints_drive_id_and_path(indexed_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["locate", "darwinia", "--store", str(indexed_store)])
    assert result.exit_code == 0
    assert "Cee-834R" in result.output
    assert "whatsapp" not in result.output


def test_cli_locate_json(indexed_store: Path) -> None:
    import json

    runner = CliRunner()
    result = runner.invoke(
        main, ["locate", "futurama", "--json", "--store", str(indexed_store)]
    )
    assert result.exit_code == 0
    records = json.loads(result.output)
    assert records
    assert records[0]["drive_id"] == "Cee-834R"


def test_cli_locate_no_results(indexed_store: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main, ["locate", "zzznomatchzzz", "--store", str(indexed_store)]
    )
    assert result.exit_code == 0
    assert "No results." in result.output
