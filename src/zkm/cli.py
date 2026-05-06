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
@click.option("--no-progress", is_flag=True, help="Suppress progress bar")
def cmd_convert(
    plugin: str,
    store_override: str | None,
    no_commit: bool,
    reprocess_mode: str | None,
    no_progress: bool,
) -> None:
    """Run a plugin's converter against the store."""
    from tqdm import tqdm

    from zkm.cancel import CancelController, PluginInterrupt
    from zkm.convert import run_convert, run_reprocess

    sdir = Path(store_override) if store_override else store_path()
    if not (sdir / ".git").exists():
        click.echo(f"Error: {sdir} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)

    _BAR_FORMAT = (
        "{desc:<14}{percentage:3.0f}%|{bar:30}| "
        "{n_fmt:>6}/{total_fmt:<6} "
        "[{elapsed}<{remaining}, {rate_fmt:>10}] "
        "{postfix}"
    )
    show_progress = not no_progress and sys.stdout.isatty()
    bar: tqdm | None = None
    cancel_status: str | None = None

    def update_status(s: str) -> None:
        nonlocal cancel_status
        cancel_status = s
        if bar is not None:
            bar.set_description(s)
            bar.refresh()
        else:
            click.echo(f"\r{s}", err=True, nl=False)

    cancelled = False
    created: list[Path] = []

    with CancelController(on_status=update_status) as cancel:
        def progress_cb(current: int, total: int | None, message: str = "") -> None:
            nonlocal bar
            cancel.check()  # raises PluginInterrupt on soft cancel
            if bar is None:
                bar = tqdm(
                    total=total, unit="item", leave=False, file=sys.stderr, bar_format=_BAR_FORMAT
                )
                if cancel_status:
                    bar.set_description(cancel_status)
            elif total is not None and bar.total != total:
                bar.total = total
                bar.refresh()
            delta = current - bar.n
            if delta > 0:
                bar.update(delta)
            if message:
                bar.set_postfix_str(message[:60])

        progress = progress_cb if show_progress else None

        try:
            if reprocess_mode:
                created = run_reprocess(plugin, sdir, mode=reprocess_mode, progress=progress)
            else:
                created = run_convert(plugin, sdir, progress=progress)
        except (LookupError, ValueError, FileNotFoundError) as e:
            if bar is not None:
                bar.close()
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except PluginInterrupt:
            cancelled = True
        except KeyboardInterrupt:
            cancelled = True
        finally:
            if bar is not None:
                bar.close()

    if cancelled:
        click.echo("", err=True)  # ensure newline after any in-place status
        click.echo(
            f"Cancelled. Re-run `zkm convert {plugin}` to resume"
            " (already-processed items are skipped).",
            err=True,
        )

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
            if cancelled:
                msg += " (partial — cancelled)"
            subprocess.run(["git", "commit", "-m", msg], cwd=sdir, check=True)
            click.echo(f"Committed: {msg}")

    if cancelled:
        sys.exit(130)  # standard shell convention for SIGINT


# ---------------------------------------------------------------------------
# zkm index
# ---------------------------------------------------------------------------


@main.command("index")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
@click.option("--no-progress", is_flag=True, help="Suppress progress bar")
def cmd_index(store_override: str | None, no_progress: bool) -> None:
    """Build or refresh the BM25 search index."""
    import time

    from tqdm import tqdm

    from zkm.index import build_index, save_index

    sdir = Path(store_override) if store_override else store_path()
    if not (sdir / ".git").exists():
        click.echo(f"Error: {sdir} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)

    show_progress = not no_progress and sys.stdout.isatty()
    bar: tqdm | None = None

    _BAR_FORMAT = (
        "{desc:<14}{percentage:3.0f}%|{bar:30}| "
        "{n_fmt:>6}/{total_fmt:<6} "
        "[{elapsed}<{remaining}, {rate_fmt:>10}] "
        "{postfix}"
    )

    def progress_cb(current: int, total: int | None, message: str = "") -> None:
        nonlocal bar
        if not show_progress:
            return
        if bar is None:
            bar = tqdm(
                total=total, unit="file", leave=False, file=sys.stderr, bar_format=_BAR_FORMAT
            )
        if total is not None and bar.total != total:
            bar.total = total
            bar.refresh()
        delta = current - bar.n
        if delta > 0:
            bar.update(delta)
        if message:
            bar.set_postfix_str(message[:60])

    t0 = time.monotonic()
    idx = build_index(sdir, progress=progress_cb if show_progress else None)
    if bar is not None:
        bar.close()
    save_index(sdir, idx)
    elapsed = time.monotonic() - t0
    click.echo(f"Indexed {len(idx.docs)} document(s) in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# zkm search
# ---------------------------------------------------------------------------


@main.command("search")
@click.argument("query")
@click.option("-k", "--top-k", default=10, show_default=True, help="Number of results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_search(query: str, top_k: int, as_json: bool, store_override: str | None) -> None:
    """Search the knowledge store with BM25."""
    import json as _json

    from zkm.query import search

    sdir = Path(store_override) if store_override else store_path()
    try:
        hits = search(sdir, query, top_k=top_k)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if as_json:
        records = [
            {"path": h.path, "score": h.score, "date": h.date, "snippet": h.snippet} for h in hits
        ]
        click.echo(_json.dumps(records, ensure_ascii=False))
        return

    if not hits:
        click.echo("No results.")
        return

    for h in hits:
        date_str = f"  ({h.date})" if h.date else ""
        click.echo(f"{h.score:6.2f}  {h.path}{date_str}")
        if h.snippet:
            click.echo(f"       {h.snippet}")
        click.echo()


# ---------------------------------------------------------------------------
# zkm query
# ---------------------------------------------------------------------------


@main.command("query")
@click.argument("question")
@click.option("-k", "--top-k", default=20, show_default=True, help="Context documents")
@click.option(
    "--no-expand",
    is_flag=True,
    default=False,
    help="Skip LLM query expansion; use raw BM25 on the question tokens.",
)
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_query(question: str, top_k: int, no_expand: bool, store_override: str | None) -> None:
    """Answer a question using BM25 context + LLM (with query expansion by default)."""
    import httpx

    from zkm.query import llm_stream, search, search_with_expansion

    sdir = Path(store_override) if store_override else store_path()
    try:
        if no_expand:
            hits = search(sdir, question, top_k=top_k)
        else:
            hits = search_with_expansion(sdir, question, top_k=top_k)
        for chunk in llm_stream(sdir, hits, question):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
        click.echo()
        if hits:
            click.echo("\nSources:")
            for h in hits:
                click.echo(f"  - {h.path}")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.echo(f"Error: LLM request failed: {e}", err=True)
        sys.exit(1)
