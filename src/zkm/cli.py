"""zkm — ze knowledge manager CLI."""

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
    from pathlib import Path

    path = Path(store) if store else store_path()
    init_store(path, backend)


# ---------------------------------------------------------------------------
# zkm plugin
# ---------------------------------------------------------------------------


@main.group("plugin")
def cmd_plugin() -> None:
    """Manage converter plugins."""


@cmd_plugin.command("add")
@click.argument("git_url")
def cmd_plugin_add(git_url: str) -> None:
    """Clone and register a plugin from GIT_URL."""
    raise NotImplementedError("zkm plugin add — see TODO.md")


@cmd_plugin.command("list")
def cmd_plugin_list() -> None:
    """List installed plugins."""
    raise NotImplementedError("zkm plugin list — see TODO.md")


@cmd_plugin.command("remove")
@click.argument("name")
def cmd_plugin_remove(name: str) -> None:
    """Remove an installed plugin by NAME."""
    raise NotImplementedError("zkm plugin remove — see TODO.md")


# ---------------------------------------------------------------------------
# zkm convert
# ---------------------------------------------------------------------------


@main.command("convert")
@click.argument("plugin")
@click.option("--no-commit", is_flag=True, help="Skip auto-commit after conversion")
def cmd_convert(plugin: str, no_commit: bool) -> None:
    """Run a plugin's converter against the store."""
    raise NotImplementedError("zkm convert — see TODO.md")


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
