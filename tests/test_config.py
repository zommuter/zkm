"""Tests for zkm.config: load_config, StoreConfig, migration, env-cutover guard."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml

from zkm.config import (
    ConfigError,
    _assert_env_cutover,
    _coerce,
    _deep_merge,
    load_config,
    migrate_env,
)

# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_flat() -> None:
    assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_deep_merge_nested_overlay() -> None:
    base = {"core": {"llm": {"endpoint": "http://a", "model": "m1"}}}
    overlay = {"core": {"llm": {"model": "m2"}}}
    result = _deep_merge(base, overlay)
    assert result["core"]["llm"]["endpoint"] == "http://a"
    assert result["core"]["llm"]["model"] == "m2"


def test_deep_merge_non_dict_replaces() -> None:
    base = {"core": {"llm": {"model": "m1"}}}
    overlay = {"core": "override"}
    result = _deep_merge(base, overlay)
    assert result["core"] == "override"


def test_deep_merge_does_not_mutate_base() -> None:
    base = {"a": {"b": 1}}
    _deep_merge(base, {"a": {"c": 2}})
    assert base == {"a": {"b": 1}}


# ---------------------------------------------------------------------------
# _assert_env_cutover
# ---------------------------------------------------------------------------


def test_assert_env_cutover_absent(tmp_path: Path) -> None:
    _assert_env_cutover(tmp_path)  # no error when .env absent


def test_assert_env_cutover_empty(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("")
    _assert_env_cutover(tmp_path)  # no error for empty file


def test_assert_env_cutover_only_secrets(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ZKM_LLM_KEY=sk-abc\nZKM_EMBED_KEY=sk-xyz\n")
    _assert_env_cutover(tmp_path)  # secrets are allowed


def test_assert_env_cutover_non_secret_raises(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("EML_SOURCE_DIR=~/mail\n")
    with pytest.raises(ConfigError, match="non-secret keys"):
        _assert_env_cutover(tmp_path)


def test_assert_env_cutover_mixed_raises(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ZKM_LLM_KEY=sk-abc\nEML_SOURCE_DIR=~/mail\n")
    with pytest.raises(ConfigError, match="migrate"):
        _assert_env_cutover(tmp_path)


def test_assert_env_cutover_comments_ignored(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("# EML_SOURCE_DIR=~/mail\n")
    _assert_env_cutover(tmp_path)  # commented line is not a key


# ---------------------------------------------------------------------------
# load_config — basic
# ---------------------------------------------------------------------------


def test_load_config_no_files(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    # Should return defaults
    assert cfg.core_value("llm", "endpoint") == "http://localhost:8080"
    assert cfg.core_value("llm", "model") == "gemma4-e4b"
    assert cfg.core_value("embed", "chunk_chars") == 2000
    assert cfg.core_value("binary_backend") == "none"


def test_load_config_yaml_round_trip(tmp_path: Path) -> None:
    data = {
        "core": {"llm": {"endpoint": "http://myserver", "model": "llama"}},
        "eml": {"source_dir": "~/inbox"},
    }
    (tmp_path / "zkm-config.yaml").write_text(yaml.dump(data))
    cfg = load_config(tmp_path)
    assert cfg.core_value("llm", "endpoint") == "http://myserver"
    assert cfg.core_value("llm", "model") == "llama"
    assert cfg.for_plugin("eml")["source_dir"] == "~/inbox"


def test_load_config_secrets_override(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text(yaml.dump({"core": {"llm": {"model": "gemma"}}}))
    (tmp_path / ".zkm-secrets.yaml").write_text(yaml.dump({"core": {"llm": {"key": "sk-secret"}}}))
    cfg = load_config(tmp_path)
    assert cfg.core_value("llm", "model") == "gemma"
    assert cfg.core_value("llm", "key") == "sk-secret"


def test_load_config_env_cutover_guard(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("EML_SOURCE_DIR=~/mail\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_load_config_only_secret_env_ok(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ZKM_LLM_KEY=sk-abc\n")
    cfg = load_config(tmp_path)  # should not raise
    assert cfg.core_value("llm", "endpoint") == "http://localhost:8080"


def test_load_config_bad_yaml_raises(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text("core: [bad: yaml: structure")
    with pytest.raises(ConfigError, match="Cannot parse"):
        load_config(tmp_path)


# ---------------------------------------------------------------------------
# StoreConfig.core_value
# ---------------------------------------------------------------------------


def test_core_value_missing_path(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg.core_value("nonexistent") is None
    assert cfg.core_value("llm", "nonexistent") is None


def test_core_value_deep_path(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text(
        yaml.dump({"core": {"query": {"low_bm25_threshold": 2.0}}})
    )
    cfg = load_config(tmp_path)
    assert cfg.core_value("query", "low_bm25_threshold") == 2.0


# ---------------------------------------------------------------------------
# StoreConfig.for_plugin
# ---------------------------------------------------------------------------


def test_for_plugin_bare_name(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text(yaml.dump({"eml": {"source_dir": "~/mail"}}))
    cfg = load_config(tmp_path)
    assert cfg.for_plugin("eml") == {"source_dir": "~/mail"}


def test_for_plugin_zkm_prefix_stripped(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text(yaml.dump({"eml": {"source_dir": "~/mail"}}))
    cfg = load_config(tmp_path)
    assert cfg.for_plugin("zkm-eml") == {"source_dir": "~/mail"}


def test_for_plugin_missing_section(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg.for_plugin("unknown-plugin") == {}


def test_for_plugin_returns_copy(tmp_path: Path) -> None:
    (tmp_path / "zkm-config.yaml").write_text(yaml.dump({"eml": {"source_dir": "~/mail"}}))
    cfg = load_config(tmp_path)
    d = cfg.for_plugin("eml")
    d["source_dir"] = "modified"
    assert cfg.for_plugin("eml")["source_dir"] == "~/mail"


# ---------------------------------------------------------------------------
# migrate_env
# ---------------------------------------------------------------------------


def test_migrate_env_no_env_file(tmp_path: Path) -> None:
    result = migrate_env(tmp_path)
    assert result == {"config": {}, "secrets": {}}


def test_migrate_env_dry_run(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("EML_SOURCE_DIR=~/mail\nZKM_LLM_KEY=sk-abc\n")
    result = migrate_env(tmp_path, apply=False)
    assert result["config"]["eml"]["source_dir"] == "~/mail"
    assert result["secrets"]["core"]["llm"]["key"] == "sk-abc"
    assert (tmp_path / ".env").exists()  # not renamed in dry run


def test_migrate_env_apply(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("EML_SOURCE_DIR=~/mail\nZKM_LLM_KEY=sk-abc\n")
    migrate_env(tmp_path, apply=True)
    assert not (tmp_path / ".env").exists()
    assert (tmp_path / ".env.migrated").exists()
    assert (tmp_path / "zkm-config.yaml").exists()
    assert (tmp_path / ".zkm-secrets.yaml").exists()
    # Secrets file must be 0600
    mode = stat.S_IMODE((tmp_path / ".zkm-secrets.yaml").stat().st_mode)
    assert mode == 0o600


def test_migrate_env_apply_loads_correctly(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "EML_SOURCE_DIR=~/mail\n"
        "EML_KEEP_ORIGINALS=true\n"
        "NOTMUCH_TAGS_EXCLUDE=inbox,unread\n"
        "ZKM_LLM_KEY=sk-abc\n"
    )
    migrate_env(tmp_path, apply=True)
    cfg = load_config(tmp_path)
    assert cfg.for_plugin("eml")["source_dir"] == "~/mail"
    assert cfg.for_plugin("eml")["keep_originals"] is True
    assert cfg.for_plugin("notmuch")["tags_exclude"] == "inbox,unread"
    assert cfg.core_value("llm", "key") == "sk-abc"


def test_migrate_env_validate_unknown_key(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("UNKNOWN_KEY=value\n")
    with pytest.warns(UserWarning, match="Unknown .env key"):
        result = migrate_env(tmp_path, apply=False)
    assert result["config"] == {}


# ---------------------------------------------------------------------------
# _coerce
# ---------------------------------------------------------------------------


def test_coerce_bool_true() -> None:
    assert _coerce("true") is True
    assert _coerce("yes") is True
    assert _coerce("1") is True


def test_coerce_bool_false() -> None:
    assert _coerce("false") is False
    assert _coerce("no") is False
    assert _coerce("0") is False


def test_coerce_int() -> None:
    assert _coerce("42") == 42
    assert isinstance(_coerce("42"), int)


def test_coerce_float() -> None:
    assert _coerce("3.14") == 3.14


def test_coerce_string() -> None:
    assert _coerce("~/mail") == "~/mail"
    assert _coerce("") == ""
