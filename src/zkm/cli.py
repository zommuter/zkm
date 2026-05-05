"""zkm — ze knowledge manager CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from zkm import __version__
from zkm.store import init_store, store_path


@click.group()
@click.version_option(__version__)
def main() -> None:
    """ze knowledge manager — personal knowledge base CLI."""


# ---------------------------------------------------------------------------
# zkm init
# ---------------------------------------------------------------------------


@main.command("init")
@click.option(
    "--store",
    "store",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
@click.option(
    "--backend",
    type=click.Choice(["auto", "annex", "lfs", "none"]),
    default="auto",
    show_default=True,
    help="Binary backend for originals/",
)
def cmd_init(store: str | None, backend: str) -> None:
    """Initialize the knowledge store."""
    path = Path(store) if store else store_path()
    init_store(path, backend)


# ---------------------------------------------------------------------------
# zkm plugin
# ---------------------------------------------------------------------------


@main.group("plugin")
def cmd_plugin() -> None:
    """Manage converter plugins."""


@cmd_plugin.command("add")
@click.argument("source")
def cmd_plugin_add(source: str) -> None:
    """Install a plugin from a local PATH or git URL."""
    from zkm.convert import add_plugin

    try:
        plugin = add_plugin(source)
        click.echo(f"Installed plugin '{plugin.name}' {plugin.version} from {source}")
    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cmd_plugin.command("list")
def cmd_plugin_list() -> None:
    """List installed plugins."""
    from zkm.convert import list_plugins

    plugins = list_plugins()
    if not plugins:
        click.echo("No plugins installed. Run: zkm plugin add <path-or-url>")
        return
    for p in plugins:
        click.echo(f"  {p.name:<20} {p.version:<10} {p.path}")


@cmd_plugin.command("remove")
@click.argument("name")
def cmd_plugin_remove(name: str) -> None:
    """Remove an installed plugin by NAME."""
    from zkm.convert import remove_plugin

    try:
        remove_plugin(name)
        click.echo(f"Removed plugin '{name}'")
    except LookupError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# zkm convert
# ---------------------------------------------------------------------------


@main.command("convert")
@click.argument("plugin")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
@click.option("--no-commit", is_flag=True, help="Skip auto-commit after conversion")
@click.option(
    "--reprocess",
    "reprocess_mode",
    flag_value="outdated",
    default=None,
    help="Re-process files whose processor_version differs from the current plugin version",
)
@click.option(
    "--reprocess-all",
    "reprocess_mode",
    flag_value="all",
    help="Re-process all files managed by this plugin",
)
def cmd_convert(
    plugin: str, store_override: str | None, no_commit: bool, reprocess_mode: str | None
) -> None:
    """Run a plugin's converter against the store."""
    from zkm.convert import run_convert, run_reprocess

    sdir = Path(store_override) if store_override else store_path()
    if not (sdir / ".git").exists():
        click.echo(f"Error: {sdir} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)

    try:
        if reprocess_mode:
            created = run_reprocess(plugin, sdir, mode=reprocess_mode)
        else:
            created = run_convert(plugin, sdir)
    except (LookupError, ValueError, FileNotFoundError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    n = len(created)
    verb = "Reprocessed" if reprocess_mode else "Converted"
    click.echo(f"{verb} {n} file(s) via plugin '{plugin}'")
    for p in created:
        click.echo(f"  + {p.relative_to(sdir)}")

    if n > 0 and not no_commit:
        subprocess.run(["git", "add", "-A"], cwd=sdir, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=sdir)
        if result.returncode != 0:
            if reprocess_mode:
                msg = f"refactor({plugin}): reprocess {n} file(s)"
            else:
                msg = f"chore({plugin}): ingest {n} file(s)"
            subprocess.run(["git", "commit", "-m", msg], cwd=sdir, check=True)
            click.echo(f"Committed: {msg}")


# ---------------------------------------------------------------------------
# zkm index
# ---------------------------------------------------------------------------


@main.command("index")
def cmd_index() -> None:
    """Build or refresh the BM25 search index."""
    raise NotImplementedError("zkm index — see TODO.md")


# ---------------------------------------------------------------------------
# zkm search
# ---------------------------------------------------------------------------


@main.command("search")
@click.argument("query")
@click.option("-k", "--top-k", default=10, show_default=True, help="Number of results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def cmd_search(query: str, top_k: int, as_json: bool) -> None:
    """Search the knowledge store with BM25."""
    raise NotImplementedError("zkm search — see TODO.md")


# ---------------------------------------------------------------------------
# zkm query
# ---------------------------------------------------------------------------


@main.command("query")
@click.argument("question")
@click.option("-k", "--top-k", default=5, show_default=True, help="Context documents")
def cmd_query(question: str, top_k: int) -> None:
    """Answer a question using BM25 context + LLM."""
    raise NotImplementedError("zkm query — see TODO.md")
