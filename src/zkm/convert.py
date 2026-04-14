"""Plugin registry and converter dispatch."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Plugin directory resolution
# ---------------------------------------------------------------------------


def plugins_dir() -> Path:
    """
    Return the directory where installed plugins live.

    Resolution order:
    1. $ZKM_PLUGINS_DIR (env override)
    2. <repo-root>/plugins/   (tool repo, detected via pyproject.toml)
    3. ~/.local/share/zkm/plugins/  (fallback for installed builds)
    """
    if p := os.environ.get("ZKM_PLUGINS_DIR"):
        return Path(p).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "plugins"
    return Path.home() / ".local" / "share" / "zkm" / "plugins"


# ---------------------------------------------------------------------------
# Plugin manifest
# ---------------------------------------------------------------------------


@dataclass
class Plugin:
    name: str
    version: str
    description: str
    path: Path
    config_keys: dict[str, dict] = field(default_factory=dict)
    creates_dirs: list[str] = field(default_factory=list)


def load_plugin_manifest(plugin_path: Path) -> Plugin:
    manifest = plugin_path / "plugin.yaml"
    if not manifest.exists():
        raise FileNotFoundError(f"Missing plugin.yaml at {manifest}")
    data = yaml.safe_load(manifest.read_text())
    return Plugin(
        name=data["name"],
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        path=plugin_path,
        config_keys=data.get("config") or {},
        creates_dirs=data.get("creates_dirs") or [],
    )


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------


def list_plugins() -> list[Plugin]:
    """Return all installed plugins, sorted by name."""
    pdir = plugins_dir()
    if not pdir.exists():
        return []
    plugins = []
    for entry in sorted(pdir.iterdir()):
        if not (entry.is_dir() or entry.is_symlink()):
            continue
        if not (entry / "plugin.yaml").exists():
            continue
        try:
            plugins.append(load_plugin_manifest(entry))
        except Exception as e:
            print(f"WARN: skipping {entry.name}: {e}")
    return plugins


def find_plugin(name: str) -> Plugin | None:
    return next((p for p in list_plugins() if p.name == name), None)


def add_plugin(source: str) -> Plugin:
    """
    Install a plugin from a local directory path or git URL.

    Local path  → symlink into plugins/zkm-<name>/
    Git URL     → git clone into plugins/<repo-name>/
    """
    pdir = plugins_dir()
    pdir.mkdir(parents=True, exist_ok=True)

    src_path = Path(source).expanduser()
    is_local = src_path.exists() and src_path.is_dir()

    if is_local:
        src_path = src_path.resolve()
        manifest = src_path / "plugin.yaml"
        if not manifest.exists():
            raise FileNotFoundError(f"No plugin.yaml in {src_path}")
        name = yaml.safe_load(manifest.read_text())["name"]
        dest = pdir / f"zkm-{name}"
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(f"Plugin '{name}' already installed at {dest}")
        dest.symlink_to(src_path, target_is_directory=True)
        return load_plugin_manifest(dest)
    else:
        # Git URL: derive dir name from last path component
        repo_name = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        dest = pdir / repo_name
        if dest.exists():
            raise FileExistsError(f"Plugin directory already exists: {dest}")
        subprocess.run(["git", "clone", source, str(dest)], check=True)
        return load_plugin_manifest(dest)


def remove_plugin(name: str) -> None:
    """Remove an installed plugin by its manifest name."""
    plugin = find_plugin(name)
    if plugin is None:
        raise LookupError(f"Plugin not installed: {name}")
    if plugin.path.is_symlink():
        plugin.path.unlink()
    else:
        shutil.rmtree(plugin.path)


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------


def load_env(store_path: Path) -> dict[str, str]:
    """Parse $ZKM_STORE/.env into a flat dict (KEY=VALUE lines, no expansion)."""
    env_file = store_path / ".env"
    if not env_file.exists():
        return {}
    env: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip("\"'")
    return env


# ---------------------------------------------------------------------------
# Converter dispatch
# ---------------------------------------------------------------------------


def run_convert(
    name: str,
    store_path: Path,
    extra_env: dict[str, str] | None = None,
) -> list[Path]:
    """
    Load plugin by name, resolve config, and call its convert() function.

    extra_env: additional key/value pairs that supplement (not replace) .env.
    Returns the list of created/updated paths as reported by the plugin.
    """
    plugin = find_plugin(name)
    if plugin is None:
        raise LookupError(f"Plugin not installed: '{name}'. Run: zkm plugin list")

    # Build config: .env → extra_env → process env (fallback) → spec defaults
    env = load_env(store_path)
    if extra_env:
        env.update(extra_env)
    for k in plugin.config_keys:
        if k not in env and k in os.environ:
            env[k] = os.environ[k]

    config: dict[str, str] = {}
    missing = []
    for k, spec in plugin.config_keys.items():
        if k in env:
            config[k] = env[k]
        elif "default" in spec:
            config[k] = spec["default"]
        elif spec.get("required"):
            missing.append(k)

    if missing:
        raise ValueError(
            f"Plugin '{name}' requires missing config keys: {', '.join(missing)}\n"
            f"Add them to {store_path / '.env'}"
        )

    # Ensure declared dirs exist
    for d in plugin.creates_dirs:
        (store_path / d).mkdir(parents=True, exist_ok=True)

    # Dynamically load convert.py
    convert_py = plugin.path / "convert.py"
    if not convert_py.exists():
        raise FileNotFoundError(f"{convert_py} not found")

    spec_obj = importlib.util.spec_from_file_location(f"zkm_plugin_{name}", convert_py)
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"Could not load {convert_py}")
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)  # type: ignore[union-attr]

    if not hasattr(mod, "convert"):
        raise AttributeError(f"Plugin '{name}': convert.py has no convert() function")

    result = mod.convert(store_path, config)
    return [Path(p) for p in (result or [])]
