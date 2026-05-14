"""Per-store YAML configuration loader.

Two-file layout:
  <store>/zkm-config.yaml     — non-secrets, committed to git
  <store>/.zkm-secrets.yaml   — credentials, chmod 0600, gitignored

Both files share the same YAML structure; secrets are merged on top.
Core values live under 'core:'; plugin values live under '<bare-plugin-name>:'.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

import click
import yaml

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigError(click.ClickException):
    """Raised when the store configuration is invalid or migration is required."""


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------

_SECRET_RE = re.compile(r"PASS(WORD)?|TOKEN|KEY|SECRET", re.IGNORECASE)


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_RE.search(key))


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_CORE_DEFAULTS: dict[str, Any] = {
    "binary_backend": "none",
    "llm": {
        "endpoint": "http://localhost:8080",
        "model": "gemma4-e4b",
        "key": "",
    },
    "embed": {
        "endpoint": "http://localhost:8080",
        "model": "bge-m3",
        "chunk_chars": 2000,
        "chunk_overlap": 200,
        "key": "",
    },
    "expand": {
        "timeout": 30.0,
        "cold_timeout": 180.0,
        "key": "",
    },
    "query": {
        "low_dense_threshold": 0.5,
        "low_bm25_threshold": 1.0,
        "max_doc_chars": 500,
    },
}


# ---------------------------------------------------------------------------
# StoreConfig
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge *overlay* into a copy of *base*."""
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class StoreConfig:
    """Merged view of zkm-config.yaml + .zkm-secrets.yaml."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def core_value(self, *path: str) -> Any:
        """
        Return core.<path[0]>.<path[1]>... or None if the path is absent.

        Example: cfg.core_value("llm", "endpoint")  → "http://localhost:8080"
        """
        node: Any = self._data.get("core", {})
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    def for_plugin(self, name: str) -> dict[str, Any]:
        """
        Return the plugin's config section (bare snake_case keys).

        Strips 'zkm-' prefix if present.  Returns {} when no section exists.
        """
        bare = name.removeprefix("zkm-")
        section = self._data.get(bare)
        return dict(section) if isinstance(section, dict) else {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(store: Path) -> StoreConfig:
    """
    Load and merge zkm-config.yaml + .zkm-secrets.yaml from *store*.

    Raises ConfigError if .env is present and contains non-secret keys
    (migration required: run 'zkm config migrate --apply').
    """
    _assert_env_cutover(store)

    # Start from built-in defaults
    merged: dict[str, Any] = {"core": _deep_merge({}, _CORE_DEFAULTS)}

    # Layer in zkm-config.yaml
    cfg_path = store / "zkm-config.yaml"
    if cfg_path.exists():
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Cannot parse {cfg_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigError(f"{cfg_path} must be a YAML mapping, got {type(loaded).__name__}")
        merged = _deep_merge(merged, loaded)

    # Layer in .zkm-secrets.yaml (highest priority)
    sec_path = store / ".zkm-secrets.yaml"
    if sec_path.exists():
        try:
            secrets = yaml.safe_load(sec_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Cannot parse {sec_path}: {exc}") from exc
        if isinstance(secrets, dict):
            merged = _deep_merge(merged, secrets)

    return StoreConfig(merged)


def _assert_env_cutover(store: Path) -> None:
    """
    Raise ConfigError if .env exists and contains non-secret keys.

    Silent when .env is absent, empty, or contains only secrets / comments.
    """
    env_path = store / ".env"
    if not env_path.exists():
        return
    non_secret: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.partition("=")[0].strip()
        if not _is_secret_key(key):
            non_secret.append(key)
    if non_secret:
        shown = ", ".join(non_secret[:5])
        ellipsis = "…" if len(non_secret) > 5 else ""
        raise ConfigError(
            f"Store {store} has a .env with non-secret keys: {shown}{ellipsis}.\n"
            "Run 'zkm config migrate --apply' to migrate to zkm-config.yaml."
        )


# ---------------------------------------------------------------------------
# Migration helpers (used by `zkm config migrate`)
# ---------------------------------------------------------------------------

# Mapping of legacy .env keys → (yaml_section, yaml_key)
# Keys not in this table that are non-secret go into 'unknown' with a warning.
_ENV_KEY_MAP: dict[str, tuple[str, str]] = {
    # core
    "ZKM_LLM_ENDPOINT": ("core.llm", "endpoint"),
    "ZKM_LLM_MODEL": ("core.llm", "model"),
    "ZKM_LLM_KEY": ("core.llm", "key"),
    "ZKM_EMBED_ENDPOINT": ("core.embed", "endpoint"),
    "ZKM_EMBED_MODEL": ("core.embed", "model"),
    "ZKM_EMBED_KEY": ("core.embed", "key"),
    "ZKM_EMBED_CHUNK_CHARS": ("core.embed", "chunk_chars"),
    "ZKM_EMBED_CHUNK_OVERLAP": ("core.embed", "chunk_overlap"),
    "ZKM_LLM_EXPAND_ENDPOINT": ("core.expand", "endpoint"),
    "ZKM_LLM_EXPAND_MODEL": ("core.expand", "model"),
    "ZKM_LLM_EXPAND_KEY": ("core.expand", "key"),
    "ZKM_LLM_EXPAND_TIMEOUT": ("core.expand", "timeout"),
    "ZKM_LLM_EXPAND_COLD_TIMEOUT": ("core.expand", "cold_timeout"),
    # eml plugin
    "EML_SOURCE_DIR": ("eml", "source_dir"),
    "EML_FOLDERS_EXCLUDE": ("eml", "folders_exclude"),
    "EML_KEEP_ORIGINALS": ("eml", "keep_originals"),
    "EML_OWNER_ADDRESSES": ("eml", "owner_addresses"),
    "EML_ATTACHMENT_INBOX": ("eml", "attachment_inbox"),
    "EML_QUOTE_STRIP": ("eml", "quote_strip"),
    "EML_SLUG_ASCII": ("eml", "slug_ascii"),
    # notmuch plugin
    "NOTMUCH_CONFIG": ("notmuch", "config_file"),
    "NOTMUCH_TAGS_EXCLUDE": ("notmuch", "tags_exclude"),
    # pdf plugin
    "PDF_SOURCE_DIR": ("pdf", "source_dir"),
    "PDF_MIN_TEXT_CHARS": ("pdf", "min_text_chars"),
    # photo plugin
    "PHOTO_SOURCE_DIR": ("photo", "source_dir"),
    # scan plugin
    "SCAN_SOURCE_DIR": ("scan", "source_dir"),
    "SCAN_LANG": ("scan", "lang"),
    "SCAN_MIN_TEXT_CHARS": ("scan", "min_text_chars"),
    # ner plugin
    "ZKM_NER_MODEL": ("ner", "model"),
    "ZKM_NER_LANG": ("ner", "lang"),
    "ZKM_NER_GAZETTEER": ("ner", "gazetteer"),
    # notes example plugin
    "NOTES_SOURCE_DIR": ("notes", "source_dir"),
    "NOTES_DEFAULT_TAGS": ("notes", "default_tags"),
}

_SECRET_ENV_KEYS = {"ZKM_LLM_KEY", "ZKM_EMBED_KEY", "ZKM_LLM_EXPAND_KEY"}


def migrate_env(store: Path, *, apply: bool = False) -> dict[str, Any]:
    """
    Convert .env to zkm-config.yaml + .zkm-secrets.yaml.

    Returns a dict with keys 'config' and 'secrets' showing what would be written.
    When apply=True: writes the YAML files and renames .env → .env.migrated.
    """
    env_path = store / ".env"
    if not env_path.exists():
        return {"config": {}, "secrets": {}}

    config_out: dict[str, Any] = {}
    secrets_out: dict[str, Any] = {}

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw_val = line.partition("=")
        key = key.strip()
        val: Any = raw_val.strip().strip("\"'")

        if key in _SECRET_ENV_KEYS:
            # Core secrets → secrets file
            _nested_set(secrets_out, f"core.{_secret_subpath(key)}", val)
            continue

        if key in _ENV_KEY_MAP:
            section_path, yaml_key = _ENV_KEY_MAP[key]
            typed_val = _coerce(val)
            if _is_secret_key(yaml_key):
                _nested_set(secrets_out, f"{section_path}.{yaml_key}", typed_val)
            else:
                _nested_set(config_out, f"{section_path}.{yaml_key}", typed_val)
        else:
            warnings.warn(f"Unknown .env key {key!r} — skipped during migration", stacklevel=2)

    if apply:
        cfg_path = store / "zkm-config.yaml"
        sec_path = store / ".zkm-secrets.yaml"
        if config_out:
            existing = {}
            if cfg_path.exists():
                existing = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            merged_cfg = _deep_merge(existing, config_out)
            cfg_path.write_text(yaml.dump(merged_cfg, default_flow_style=False, allow_unicode=True))
        if secrets_out:
            existing_sec = {}
            if sec_path.exists():
                existing_sec = yaml.safe_load(sec_path.read_text(encoding="utf-8")) or {}
            merged_sec = _deep_merge(existing_sec, secrets_out)
            sec_path.write_text(yaml.dump(merged_sec, default_flow_style=False, allow_unicode=True))
            sec_path.chmod(0o600)
        env_path.rename(store / ".env.migrated")

    return {"config": config_out, "secrets": secrets_out}


def _secret_subpath(env_key: str) -> str:
    table = {
        "ZKM_LLM_KEY": "llm.key",
        "ZKM_EMBED_KEY": "embed.key",
        "ZKM_LLM_EXPAND_KEY": "expand.key",
    }
    return table.get(env_key, env_key.lower())


def _nested_set(d: dict, path: str, value: Any) -> None:
    """Set d[a][b][c] = value for path 'a.b.c', creating dicts as needed."""
    parts = path.split(".")
    node = d
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _coerce(val: str) -> Any:
    """Convert string values from .env to typed Python values for YAML."""
    if val.lower() in {"true", "yes", "1"}:
        return True
    if val.lower() in {"false", "no", "0"}:
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val
