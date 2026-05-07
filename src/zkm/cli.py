"""zkm — ze knowledge manager CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from zkm import __version__
from zkm.store import (
    clone_store,
    init_store,
    pull_store,
    push_store,
    remote_add,
    remote_list,
    store_path,
)


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


def _require_store(path: Path) -> None:
    if not (path / ".git").exists():
        click.echo(f"Error: {path} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# zkm remote
# ---------------------------------------------------------------------------


@main.group("remote")
def cmd_remote() -> None:
    """Manage store remotes."""


@cmd_remote.command("add")
@click.argument("name")
@click.argument("url")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_remote_add(name: str, url: str, store_override: str | None) -> None:
    """Add a remote named NAME pointing to URL."""
    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    try:
        remote_add(sdir, name, url)
        click.echo(f"Added remote '{name}' → {url}")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cmd_remote.command("list")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_remote_list(store_override: str | None) -> None:
    """List store remotes."""
    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    output = remote_list(sdir)
    if output.strip():
        click.echo(output, nl=False)
    else:
        click.echo("No remotes configured.")


# ---------------------------------------------------------------------------
# zkm clone
# ---------------------------------------------------------------------------


@main.command("clone")
@click.argument("url")
@click.argument("path", required=False, default=None, metavar="[PATH]")
def cmd_clone(url: str, path: str | None) -> None:
    """Clone a store from URL, re-initialising its binary backend automatically."""
    if path:
        dest = Path(path)
    else:
        name = url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        dest = Path.cwd() / name
    try:
        backend = clone_store(url, dest)
        click.echo(f"Cloned store to {dest} (backend: {backend})")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# zkm push / pull
# ---------------------------------------------------------------------------


@main.command("push")
@click.argument("remote", required=False, default=None, metavar="[REMOTE]")
@click.option("--content", is_flag=True, help="Sync file content to remote (annex only)")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_push(remote: str | None, content: bool, store_override: str | None) -> None:
    """Push store commits to REMOTE."""
    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    try:
        push_store(sdir, remote, content=content)
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command("pull")
@click.argument("remote", required=False, default=None, metavar="[REMOTE]")
@click.option("--content", is_flag=True, help="Sync file content from remote (annex only)")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_pull(remote: str | None, content: bool, store_override: str | None) -> None:
    """Pull store commits from REMOTE."""
    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    try:
        pull_store(sdir, remote, content=content)
    except subprocess.CalledProcessError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# zkm plugin
# ---------------------------------------------------------------------------


@main.group("plugin")
def cmd_plugin() -> None:
    """Manage converter plugins."""


@cmd_plugin.command("add")
@click.argument("source")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
@click.option("--no-prompt", is_flag=True, help="Skip interactive .env prompting")
def cmd_plugin_add(source: str, store_override: str | None, no_prompt: bool) -> None:
    """Install a plugin from a local PATH or git URL."""
    from zkm.convert import add_plugin, prompt_required_config
    from zkm.store import store_path

    try:
        plugin = add_plugin(source)
        click.echo(f"Installed plugin '{plugin.name}' {plugin.version} from {source}")
    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    sdir = Path(store_override) if store_override else store_path()
    interactive = not no_prompt and sys.stdin.isatty()
    if not (sdir / ".git").exists():
        # Store not yet initialised — just list the keys the user will need.
        needed = [
            k for k, spec in plugin.config_keys.items()
            if spec.get("required") and "default" not in spec
        ]
        if needed:
            click.echo(
                f"Note: plugin '{plugin.name}' requires {', '.join(needed)};"
                f" set them in {sdir / '.env'} after running `zkm init`."
            )
        return

    missing = prompt_required_config(plugin, sdir, interactive=interactive)
    if missing:
        click.echo(
            f"Note: plugin '{plugin.name}' requires {', '.join(missing)};"
            f" set them in {sdir / '.env'}."
        )


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
@click.option(
    "--no-embed",
    is_flag=True,
    default=False,
    help="Skip dense embedding index (BM25 only).",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Force full re-scan, ignoring git-commit watermark.",
)
def cmd_index(store_override: str | None, no_progress: bool, no_embed: bool, full: bool) -> None:
    """Build or refresh the BM25 search index (and dense embedding index if configured)."""
    import time

    from tqdm import tqdm

    from zkm.index import build_index, save_index, write_watermark

    sdir = Path(store_override) if store_override else store_path()
    if not (sdir / ".git").exists():
        click.echo(f"Error: {sdir} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)

    # Snapshot the current HEAD before indexing; written as watermark after success.
    try:
        _head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=sdir, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        _head_sha = None

    show_progress = not no_progress and sys.stdout.isatty()
    bar: tqdm | None = None

    _BAR_FORMAT = (
        "{desc:<14}{percentage:3.0f}%|{bar:30}| "
        "{n_fmt:>6}/{total_fmt:<6} "
        "[{elapsed}<{remaining}, {rate_fmt:>10}] "
        "{postfix}"
    )

    def _make_bar(desc: str, total: int | None) -> tqdm:
        return tqdm(
            total=total, desc=desc, unit="file", leave=False,
            file=sys.stderr, bar_format=_BAR_FORMAT,
        )

    def progress_cb(current: int, total: int | None, message: str = "") -> None:
        nonlocal bar
        if not show_progress:
            return
        if bar is None:
            bar = _make_bar("BM25", total)
        if total is not None and bar.total != total:
            bar.total = total
            bar.refresh()
        delta = current - bar.n
        if delta > 0:
            bar.update(delta)
        if message:
            bar.set_postfix_str(message[:60])

    t0 = time.monotonic()
    idx = build_index(sdir, progress=progress_cb if show_progress else None, full=full)
    if bar is not None:
        bar.close()
        bar = None
    save_index(sdir, idx)
    if _head_sha:
        write_watermark(sdir, _head_sha)

    # Dense embedding pass
    if not no_embed:
        from zkm.embed import (
            EmbedUnavailable,
            build_embed_store,
            load_embed_store,
            resolve_embed_config,
            save_embed_store,
        )

        ep, mdl, key = resolve_embed_config(sdir)
        if not ep:
            click.echo(
                "Dense index skipped (set ZKM_EMBED_ENDPOINT to enable).", err=True
            )
        else:
            embed_bar: tqdm | None = None

            def embed_progress(current: int, total: int | None, message: str = "") -> None:
                nonlocal embed_bar
                if not show_progress:
                    return
                if embed_bar is None:
                    embed_bar = _make_bar("Embedding", total)
                if total is not None and embed_bar.total != total:
                    embed_bar.total = total
                    embed_bar.refresh()
                delta = current - embed_bar.n
                if delta > 0:
                    embed_bar.update(delta)
                if message:
                    embed_bar.set_postfix_str(message[:60])

            try:
                prev_es = load_embed_store(sdir)
                es = build_embed_store(
                    sdir,
                    idx.docs,
                    prev_es=prev_es,
                    endpoint=ep,
                    model=mdl,
                    api_key=key,
                    progress=embed_progress if show_progress else None,
                )
                if embed_bar is not None:
                    embed_bar.close()
                save_embed_store(sdir, es)
                click.echo(f"Embedded {len(es.paths)} document(s) with {mdl}.")
            except EmbedUnavailable as exc:
                if embed_bar is not None:
                    embed_bar.close()
                click.echo(f"Dense index failed: {exc}", err=True)

    elapsed = time.monotonic() - t0
    click.echo(f"Indexed {len(idx.docs)} document(s) in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# zkm doctor
# ---------------------------------------------------------------------------


@main.command("doctor")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_doctor(store_override: str | None) -> None:
    """Diagnose the knowledge store: index counts and endpoint reachability."""
    import json as _json

    import httpx

    from zkm.embed import resolve_embed_config
    from zkm.index import load_index
    from zkm.query import _chat_url, _resolve_expand_config, _resolve_llm_config

    sdir = Path(store_override) if store_override else store_path()
    col = 16
    ok = True

    md_count = sum(
        1 for p in sdir.rglob("*.md")
        if ".zkm-index" not in p.parts and ".git" not in p.parts
    )
    click.echo(f"{'store':<{col}}{sdir}")
    click.echo(f"{'md files':<{col}}{md_count}")

    idx = load_index(sdir)
    bm25_docs = len(idx.docs) if idx else 0
    if not idx:
        click.echo(f"{'bm25 docs':<{col}}0  (not built — run: zkm index)")
    else:
        stale = md_count - bm25_docs
        stale_str = f"  (stale: {stale} unindexed)" if stale > 0 else ""
        click.echo(f"{'bm25 docs':<{col}}{bm25_docs}{stale_str}")

    meta_path = sdir / ".zkm-index" / "embeddings-meta.json"
    if meta_path.exists():
        meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        embed_docs = meta.get("n_docs", 0)
        embed_model = meta.get("model", "?")
        embed_dim = meta.get("dim", 0)
        stale = md_count - embed_docs
        stale_str = f"  (stale: {stale} unindexed)" if stale > 0 else ""
        click.echo(
            f"{'embed docs':<{col}}{embed_docs}  (model={embed_model}, dim={embed_dim}){stale_str}"
        )
    else:
        click.echo(f"{'embed docs':<{col}}0  (not built — run: zkm index)")

    ep, mdl, key = resolve_embed_config(sdir)
    if ep:
        try:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            resp = httpx.post(
                ep.rstrip("/") + "/v1/embeddings",
                headers=headers,
                json={"model": mdl, "input": ["test"]},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            actual_dim = len(data["data"][0]["embedding"])
            actual_model = data.get("model", mdl)
            click.echo(
                f"{'embed endpoint':<{col}}{ep}  OK (model={actual_model}, dim={actual_dim})"
            )
        except Exception as exc:
            click.echo(f"{'embed endpoint':<{col}}{ep}  FAIL ({exc})")
            ok = False
    else:
        click.echo(f"{'embed endpoint':<{col}}(not configured)")

    l_ep, l_mdl, l_key = _resolve_llm_config(sdir, None, None, None)
    if l_ep:
        try:
            headers = {"Content-Type": "application/json"}
            if l_key:
                headers["Authorization"] = f"Bearer {l_key}"
            resp = httpx.post(
                _chat_url(l_ep),
                headers=headers,
                json={"model": l_mdl, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=30.0,
            )
            resp.raise_for_status()
            actual_model = resp.json().get("model", l_mdl)
            click.echo(f"{'llm endpoint':<{col}}{l_ep}  OK (model={actual_model})")
        except Exception as exc:
            click.echo(f"{'llm endpoint':<{col}}{l_ep}  FAIL ({exc})")
            ok = False
    else:
        click.echo(f"{'llm endpoint':<{col}}(not configured)")

    x_ep, x_mdl, x_key = _resolve_expand_config(sdir)
    from zkm.expand import _probe_model_loaded
    if x_ep:
        loaded = _probe_model_loaded(x_ep, x_mdl)
        if loaded is True:
            load_tag = "  (loaded)"
        elif loaded is False:
            load_tag = "  (not loaded — first query may take ~180s)"
        else:
            load_tag = ""
        click.echo(f"{'expand model':<{col}}{x_mdl}{load_tag}")
        if (x_ep, x_mdl) != (l_ep, l_mdl):
            # Only probe expand endpoint separately when it differs from main LLM
            try:
                headers = {"Content-Type": "application/json"}
                if x_key:
                    headers["Authorization"] = f"Bearer {x_key}"
                resp = httpx.post(
                    _chat_url(x_ep),
                    headers=headers,
                    json={"model": x_mdl, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    timeout=30.0,
                )
                resp.raise_for_status()
                actual_model = resp.json().get("model", x_mdl)
                click.echo(f"{'expand endpoint':<{col}}{x_ep}  OK (model={actual_model})")
            except Exception as exc:
                click.echo(f"{'expand endpoint':<{col}}{x_ep}  FAIL ({exc})")
                ok = False
    else:
        click.echo(f"{'expand model':<{col}}(not configured)")

    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# zkm search
# ---------------------------------------------------------------------------


@main.command("search")
@click.argument("query")
@click.option("-k", "--top-k", default=10, show_default=True, help="Number of results")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option(
    "--no-dense",
    is_flag=True,
    default=False,
    help="Disable dense retrieval; use BM25 only.",
)
@click.option(
    "--expand",
    is_flag=True,
    default=False,
    help="Use LLM query expansion (slower, better cross-lingual recall).",
)
@click.option(
    "--allow-fallback",
    is_flag=True,
    default=False,
    help="With --expand: fall back silently to raw BM25 if expansion fails (default: exit 2).",
)
@click.option(
    "--show-expansion",
    is_flag=True,
    default=False,
    help="Print expansion keywords and hypothetical answer to stderr (implies --expand was used).",
)
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_search(
    query: str, top_k: int, as_json: bool, no_dense: bool, expand: bool,
    allow_fallback: bool, show_expansion: bool, store_override: str | None,
) -> None:
    """Search the knowledge store (BM25 + dense hybrid when embedding index is available)."""
    import json as _json

    from zkm.query import search_hybrid_traced, search_with_expansion_traced

    sdir = Path(store_override) if store_override else store_path()
    try:
        if expand:
            hits, trace = search_with_expansion_traced(sdir, query, top_k=top_k, dense=not no_dense)
        else:
            hits, trace = search_hybrid_traced(sdir, query, top_k=top_k, dense=not no_dense)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if expand and trace.expand_skipped_reason:
        if allow_fallback:
            click.echo(
                f"zkm: query expansion failed ({trace.expand_skipped_reason}) — using raw BM25",
                err=True,
            )
        else:
            click.echo(
                f"zkm: query expansion failed ({trace.expand_skipped_reason}); "
                f"pass --allow-fallback to use raw BM25 instead",
                err=True,
            )
            sys.exit(2)

    if trace.dense_skipped_reason:
        click.echo(
            f"zkm: dense leg skipped ({trace.dense_skipped_reason}) — results are BM25-only",
            err=True,
        )

    if show_expansion:
        if trace.keywords or trace.hyp_text:
            click.echo("zkm: query expansion", err=True)
            if trace.keywords:
                click.echo(f"  keywords: {', '.join(trace.keywords)}", err=True)
            if trace.hyp_text:
                click.echo(f"  hypothetical: {trace.hyp_text}", err=True)
        if trace.expand_skipped_reason:
            click.echo(f"  expansion failed: {trace.expand_skipped_reason}", err=True)

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
    help="Skip LLM query expansion; use BM25 on raw question tokens.",
)
@click.option(
    "--no-dense",
    is_flag=True,
    default=False,
    help="Disable dense retrieval; use BM25 only (or BM25 + expansion).",
)
@click.option(
    "--allow-fallback",
    is_flag=True,
    default=False,
    help="Fall back silently to raw BM25 if expansion fails (default: exit 2).",
)
@click.option(
    "--show-expansion",
    is_flag=True,
    default=False,
    help="Print expansion keywords and hypothetical answer to stderr.",
)
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_query(
    question: str, top_k: int, no_expand: bool, no_dense: bool,
    allow_fallback: bool, show_expansion: bool, store_override: str | None
) -> None:
    """Answer a question using hybrid retrieval (BM25 + dense) + LLM."""
    import httpx

    from zkm.query import llm_stream, search_hybrid_traced, search_with_expansion_traced

    sdir = Path(store_override) if store_override else store_path()
    try:
        if no_expand:
            hits, trace = search_hybrid_traced(sdir, question, top_k=top_k, dense=not no_dense)
        else:
            hits, trace = search_with_expansion_traced(
                sdir, question, top_k=top_k, dense=not no_dense
            )
        if not no_expand and trace.expand_skipped_reason:
            if allow_fallback:
                click.echo(
                    f"zkm: query expansion failed ({trace.expand_skipped_reason}) — using raw BM25",
                    err=True,
                )
            else:
                click.echo(
                    f"zkm: query expansion failed ({trace.expand_skipped_reason}); "
                    f"pass --allow-fallback to use raw BM25 instead",
                    err=True,
                )
                sys.exit(2)
        if trace.dense_skipped_reason:
            click.echo(
                f"zkm: dense leg skipped ({trace.dense_skipped_reason}) — results are BM25-only",
                err=True,
            )
        if show_expansion:
            if trace.keywords or trace.hyp_text:
                click.echo("zkm: query expansion", err=True)
                if trace.keywords:
                    click.echo(f"  keywords: {', '.join(trace.keywords)}", err=True)
                if trace.hyp_text:
                    click.echo(f"  hypothetical: {trace.hyp_text}", err=True)
            if trace.expand_skipped_reason:
                click.echo(f"  expansion failed: {trace.expand_skipped_reason}", err=True)
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
