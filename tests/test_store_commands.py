"""Tests for zkm.store: read_zkm_config, push/pull dispatch, remote management, clone."""

from __future__ import annotations

from pathlib import Path

import pytest

from zkm.store import (
    clone_store,
    init_store,
    pull_store,
    push_store,
    read_zkm_config,
    remote_add,
    remote_list,
)


# ---------------------------------------------------------------------------
# read_zkm_config
# ---------------------------------------------------------------------------


def test_read_zkm_config_basic(tmp_path: Path) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=annex\n")
    assert read_zkm_config(tmp_path) == {"binary_backend": "annex"}


def test_read_zkm_config_missing(tmp_path: Path) -> None:
    assert read_zkm_config(tmp_path) == {}


def test_read_zkm_config_ignores_comments(tmp_path: Path) -> None:
    (tmp_path / ".zkm-config").write_text("# this is a comment\nbinary_backend=lfs\n")
    assert read_zkm_config(tmp_path) == {"binary_backend": "lfs"}


def test_read_zkm_config_ignores_blank_lines(tmp_path: Path) -> None:
    (tmp_path / ".zkm-config").write_text("\nbinary_backend=none\n\n")
    assert read_zkm_config(tmp_path) == {"binary_backend": "none"}


def test_read_zkm_config_multiple_keys(tmp_path: Path) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=none\nextra=value\n")
    cfg = read_zkm_config(tmp_path)
    assert cfg["binary_backend"] == "none"
    assert cfg["extra"] == "value"


# ---------------------------------------------------------------------------
# remote_add / remote_list
# ---------------------------------------------------------------------------


def test_remote_add_and_list(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")
    remote_add(tmp_path, "origin", "https://example.com/store.git")
    output = remote_list(tmp_path)
    assert "origin" in output
    assert "https://example.com/store.git" in output


def test_remote_list_empty(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")
    output = remote_list(tmp_path)
    assert output.strip() == ""


# ---------------------------------------------------------------------------
# push_store dispatch
# ---------------------------------------------------------------------------


def test_push_dispatch_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=none\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path)
    assert calls == [["push"]]


def test_push_dispatch_none_with_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=none\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path, "origin")
    assert calls == [["push", "origin"]]


def test_push_dispatch_annex_no_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=annex\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path, "origin")
    assert calls == [["annex", "sync", "origin"]]


def test_push_dispatch_annex_with_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=annex\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path, "origin", content=True)
    assert calls == [["annex", "sync", "--content", "origin"]]


def test_push_dispatch_annex_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=annex\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path, content=True)
    assert calls == [["annex", "sync", "--content"]]


def test_push_dispatch_lfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=lfs\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path, "origin")
    assert calls == [["lfs", "push", "--all", "origin"]]


def test_push_dispatch_lfs_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=lfs\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path)
    assert calls == [["lfs", "push", "--all"]]


def test_push_missing_config_defaults_to_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    push_store(tmp_path)
    assert calls == [["push"]]


# ---------------------------------------------------------------------------
# pull_store dispatch
# ---------------------------------------------------------------------------


def test_pull_dispatch_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=none\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    pull_store(tmp_path)
    assert calls == [["pull", "--rebase"]]


def test_pull_dispatch_none_with_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=none\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    pull_store(tmp_path, "upstream")
    assert calls == [["pull", "--rebase", "upstream"]]


def test_pull_dispatch_annex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=annex\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    pull_store(tmp_path, "origin", content=True)
    assert calls == [["annex", "sync", "--content", "origin"]]


def test_pull_dispatch_lfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=lfs\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    pull_store(tmp_path, "upstream")
    assert calls == [["lfs", "pull", "upstream"]]


def test_pull_dispatch_lfs_no_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".zkm-config").write_text("binary_backend=lfs\n")
    calls: list[list[str]] = []
    monkeypatch.setattr("zkm.store._git", lambda args, _cwd: calls.append(list(args)))
    pull_store(tmp_path)
    assert calls == [["lfs", "pull"]]


# ---------------------------------------------------------------------------
# clone_store
# ---------------------------------------------------------------------------


def test_clone_store_none_backend(tmp_path: Path) -> None:
    src = tmp_path / "source"
    init_store(src, backend="none")

    dest = tmp_path / "cloned"
    backend = clone_store(str(src), dest)

    assert backend == "none"
    assert (dest / ".git").exists()
    assert (dest / ".zkm-config").exists()
    assert read_zkm_config(dest)["binary_backend"] == "none"


def test_clone_store_preserves_config(tmp_path: Path) -> None:
    src = tmp_path / "source"
    init_store(src, backend="none")
    # Manually write a different config value to simulate a multi-key config
    (src / ".zkm-config").write_text("binary_backend=none\ncustom=hello\n")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "commit", "-m", "add custom config"], cwd=src, check=True)

    dest = tmp_path / "cloned"
    clone_store(str(src), dest)

    cfg = read_zkm_config(dest)
    assert cfg.get("custom") == "hello"
