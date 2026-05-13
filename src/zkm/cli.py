"""zkm — ze knowledge manager CLI."""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import click

from zkm import __version__
from zkm.devcheck import assert_clean
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
# zkm rm / zkm gc
# ---------------------------------------------------------------------------


def _normalise_relpath(store: Path, path_arg: str) -> Path:
    """Return *path_arg* as a path relative to *store*.

    Accepts either an absolute path inside the store or a relative path
    (resolved against cwd). Raises ValueError when the result escapes the store.
    """
    p = Path(path_arg)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        return p.resolve().relative_to(store.resolve())
    except ValueError:
        raise ValueError(f"{path_arg!r} is outside the store at {store}")


def _git_run(store: Path, *args: str) -> None:
    subprocess.run(list(args), cwd=store, check=True)


@main.command("rm")
@click.argument("path")
@click.option("--apply", "do_apply", is_flag=True, help="Perform deletions (default: dry-run)")
@click.option("--no-commit", "no_commit", is_flag=True, help="Skip auto-commit after --apply")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_rm(path: str, do_apply: bool, no_commit: bool, store_override: str | None) -> None:
    """Remove a managed .md and its orphaned CAS objects."""
    from zkm.hygiene import apply_plan, format_plan, plan_rm

    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    assert_clean()
    try:
        md_relpath = _normalise_relpath(sdir, path)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    try:
        action = plan_rm(sdir, md_relpath)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(format_plan(action))
    if do_apply:
        apply_plan(action)
        if not no_commit:
            _git_run(sdir, "git", "add", "-A")
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"], cwd=sdir
            )
            if result.returncode != 0:
                msg = f"chore: rm {md_relpath}"
                _git_run(sdir, "git", "commit", "-m", msg)
                click.echo(f"Committed: {msg}")
        click.echo("Applied.")
    else:
        click.echo("Dry run — re-run with --apply to commit.")


@main.command("gc")
@click.option("--apply", "do_apply", is_flag=True, help="Remove orphans (default: dry-run)")
@click.option("--no-commit", "no_commit", is_flag=True, help="Skip auto-commit after --apply")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_gc(do_apply: bool, no_commit: bool, store_override: str | None) -> None:
    """Scan sidecars and remove CAS objects with no producers."""
    from zkm.hygiene import apply_plan, format_gc_plan, plan_gc

    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    assert_clean()
    actions = plan_gc(sdir)

    click.echo(format_gc_plan(actions))
    if not actions:
        return

    if do_apply:
        for action in actions:
            apply_plan(action)
        n = len(actions)
        if not no_commit:
            _git_run(sdir, "git", "add", "-A")
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"], cwd=sdir
            )
            if result.returncode != 0:
                msg = f"chore: gc {n} orphan(s)"
                _git_run(sdir, "git", "commit", "-m", msg)
                click.echo(f"Committed: {msg}")
        click.echo("Applied.")
    else:
        click.echo("Dry run — re-run with --apply to commit.")


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
@click.option("--no-amenders", is_flag=True, help="Skip auto-running amender plugins after conversion")
def cmd_convert(
    plugin: str,
    store_override: str | None,
    no_commit: bool,
    reprocess_mode: str | None,
    no_progress: bool,
    no_amenders: bool,
) -> None:
    """Run a plugin's converter against the store."""
    from tqdm import tqdm

    from zkm.cancel import CancelController, PluginInterrupt
    from zkm.convert import find_plugin, list_amenders, run_convert, run_reprocess
    from zkm.runstate import RunSession

    sdir = Path(store_override) if store_override else store_path()
    if not (sdir / ".git").exists():
        click.echo(f"Error: {sdir} is not an initialized store. Run: zkm init", err=True)
        sys.exit(1)
    assert_clean(plugin_name=plugin)

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

    with RunSession(sdir, "convert", args=[plugin]) as session:
        with CancelController(on_status=update_status) as cancel:
            def progress_cb(current: int, total: int | None, message: str = "") -> None:
                nonlocal bar
                cancel.check()  # raises PluginInterrupt on soft cancel
                session.tick(current, total, phase="convert", message=message)
                if not show_progress:
                    return
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

            try:
                if reprocess_mode:
                    created = run_reprocess(plugin, sdir, mode=reprocess_mode, progress=progress_cb)
                else:
                    created = run_convert(plugin, sdir, progress=progress_cb)
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

    # Run amenders after a body-producer plugin (default-on, skipped with --no-amenders).
    plugin_obj = find_plugin(plugin)
    is_amender = plugin_obj is not None and plugin_obj.kind == "amender"

    n = len(created)
    if not is_amender:
        verb = "Reprocessed" if reprocess_mode else "Converted"
        click.echo(f"{verb} {n} file(s) via plugin '{plugin}'")
        for p in created:
            click.echo(f"  + {p.relative_to(sdir)}")
    if not cancelled and not no_amenders and not is_amender:
        for amender in list_amenders():
            try:
                run_convert(amender.name, sdir)
                click.echo(f"Amended via '{amender.name}'")
            except Exception as e:
                click.echo(f"WARN: amender '{amender.name}' failed: {e}", err=True)

    if not no_commit:
        click.echo("Staging changes...", err=True)
        subprocess.run(["git", "add", "-A"], cwd=sdir, check=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=sdir)
        if result.returncode != 0:
            if reprocess_mode:
                msg = f"refactor({plugin}): reprocess {n} file(s)"
            elif is_amender:
                msg = f"chore({plugin}): amend frontmatter"
            else:
                msg = f"chore({plugin}): ingest {n} file(s)"
            if cancelled:
                msg += " (partial — cancelled)"
            subprocess.run(["git", "commit", "-m", msg], cwd=sdir, check=True)
            click.echo(f"Committed: {msg}")

    if cancelled:
        sys.exit(130)  # standard shell convention for SIGINT


# ---------------------------------------------------------------------------
# zkm scrub
# ---------------------------------------------------------------------------


@main.command("scrub")
@click.argument("plugin")
@click.option("--apply", "do_apply", is_flag=True, help="Write changes (default: dry-run)")
@click.option("--verbose", is_flag=True, help="Print each modified file path")
@click.option("--no-progress", is_flag=True, help="Suppress progress bar")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
@click.option(
    "--with-verifier",
    is_flag=True,
    default=False,
    help="Pass suspicious entities through an LLM verifier (plugin must support it).",
)
@click.option(
    "--with-verifier-control-pct",
    default=1.5,
    type=float,
    metavar="PCT",
    help="Percentage of non-suspicious entities to sample as a blind-spot tripwire (default: 1.5).",
)
@click.option(
    "--resume",
    "do_resume",
    is_flag=True,
    default=False,
    help="Resume an interrupted run from the last-processed file watermark.",
)
def cmd_scrub(
    plugin: str,
    do_apply: bool,
    verbose: bool,
    no_progress: bool,
    store_override: str | None,
    with_verifier: bool,
    with_verifier_control_pct: float,
    do_resume: bool,
) -> None:
    """Retroactively remove stale frontmatter entries via a plugin's scrub() function."""
    from tqdm import tqdm

    from zkm.runstate import RunSession
    from zkm.scrub import run_scrub

    sdir = Path(store_override) if store_override else store_path()
    _require_store(sdir)
    assert_clean(plugin_name=plugin)

    dry_run = not do_apply
    show_progress = not no_progress and sys.stdout.isatty()
    bar: tqdm | None = None

    with RunSession(sdir, "scrub", args=[plugin]) as session:
        def progress_cb(current: int, total: int | None, message: str = "") -> None:
            nonlocal bar
            session.tick(current, total, phase="scrub", message=message)
            if not show_progress:
                return
            if bar is None:
                bar = tqdm(total=total, unit="file", leave=False, file=sys.stderr)
            elif total is not None and bar.total != total:
                bar.total = total
                bar.refresh()
            delta = current - bar.n
            if delta > 0:
                bar.update(delta)
            if message:
                bar.set_postfix_str(message[:60])

        pilot_dump_path = None
        if with_verifier and dry_run:
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d-%H%M")
            pilot_dump_path = sdir / ".zkm-state" / f"ner-verifier-pilot-{ts}.jsonl"

        if do_resume:
            wm = sdir / ".zkm-state" / f"scrub-{plugin}-watermark.json"
            if wm.exists():
                click.echo(f"Resuming scrub from watermark: {wm}", err=True)
            else:
                click.echo("No watermark found — starting from scratch.", err=True)

        try:
            stats = run_scrub(
                plugin, sdir,
                dry_run=dry_run, verbose=verbose, progress=progress_cb,
                resume=do_resume,
                with_verifier=with_verifier,
                with_verifier_control_pct=with_verifier_control_pct,
                pilot_dump_path=pilot_dump_path,
            )
        except LookupError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except AttributeError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        finally:
            if bar is not None:
                bar.close()

    scanned = stats.get("files_scanned", 0)
    changed = stats.get("files_changed", 0)
    removed = stats.get("entities_removed", 0)

    verifier_dropped = stats.get("entities_dropped_by_verifier", 0)
    verifier_note = f" ({verifier_dropped} via verifier)" if with_verifier and verifier_dropped else ""
    click.echo(
        f"Scrubbed {removed}{verifier_note} entities across {changed}/{scanned} files"
        f" ({'dry run' if dry_run else 'applied'})."
    )
    if with_verifier:
        control_sampled = stats.get("control_sampled", 0)
        control_alerts = stats.get("control_alerts", 0)
        click.echo(
            f"Verifier: {verifier_dropped} dropped; "
            f"{control_sampled} control-sample checks, {control_alerts} alert(s).",
            err=True,
        )
    if pilot_dump_path is not None:
        pilot_records = stats.get("pilot_records", 0)
        if pilot_records:
            click.echo(f"Pilot dump: {pilot_dump_path} ({pilot_records} records)")
        else:
            click.echo("Pilot dump: no verifier calls made (all cache hits or no suspicious entities).")
    if dry_run and changed:
        click.echo("Re-run with --apply to write changes.")


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
    assert_clean()

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

    from zkm.runstate import RunSession

    t0 = time.monotonic()
    with RunSession(sdir, "index") as session:
        def progress_cb(current: int, total: int | None, message: str = "") -> None:
            nonlocal bar
            session.tick(current, total, phase="bm25", message=message)
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

        idx = build_index(sdir, progress=progress_cb, full=full)
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
                session.set_phase("embed")

                def embed_progress(current: int, total: int | None, message: str = "") -> None:
                    nonlocal embed_bar
                    session.tick(current, total, phase="embed", message=message)
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
                        progress=embed_progress,
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
# zkm status
# ---------------------------------------------------------------------------


def _take_status_snapshot(running_dir: Path, send_sigusr1: bool = True) -> list[dict]:
    import json as _json
    import os as _os
    import time as _time

    if not running_dir.exists():
        return []

    live_pids: set[int] = set()
    for pid_file in list(running_dir.glob("*.json")):
        try:
            pid = int(pid_file.stem)
        except ValueError:
            continue
        try:
            _os.kill(pid, 0)
            live_pids.add(pid)
            if send_sigusr1:
                _os.kill(pid, signal.SIGUSR1)
        except ProcessLookupError:
            try:
                pid_file.unlink(missing_ok=True)
            except OSError:
                pass
            click.echo(f"zkm: removed stale PID file for pid {pid}", err=True)
        except PermissionError:
            live_pids.add(pid)

    if live_pids:
        _time.sleep(0.05)

    rows = []
    for pid_file in sorted(running_dir.glob("*.json")):
        try:
            data = _json.loads(pid_file.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        rows.append(data)
    return rows


def _format_status_lines(rows: list[dict]) -> list[str]:
    from datetime import datetime as _dt

    header = f"{'PID':<8} {'CMD':<10} {'PHASE':<8} {'STARTED':<21} {'PROGRESS':<14} {'ETA':<8} MESSAGE"
    lines: list[str] = [header, "-" * len(header)]
    for row in rows:
        pid_s = str(row.get("pid", "?"))
        args = row.get("args") or []
        cmd_base = str(row.get("command", "?"))
        cmd = (f"{cmd_base}({args[0]})" if args else cmd_base)[:9]
        phase = str(row.get("phase", "?"))[:7]
        try:
            started = _dt.fromisoformat(str(row.get("started_at", ""))).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            started = str(row.get("started_at", ""))[:19].replace("T", " ")
        current = row.get("current", 0)
        total = row.get("total")
        progress = f"{current}/{total}" if total else str(current)
        eta_seconds = row.get("eta_seconds")
        if eta_seconds is not None and current > 0:
            mins, secs = divmod(int(eta_seconds), 60)
            eta_str = f"~{mins}m" if mins else f"~{secs}s"
        else:
            eta_str = ""
        message = str(row.get("message", ""))[:40]
        lines.append(f"{pid_s:<8} {cmd:<10} {phase:<8} {started:<21} {progress:<14} {eta_str:<8} {message}")
    return lines


@main.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON array")
@click.option("--follow", is_flag=True, help="Watch mode: redraw table every 2 s (Ctrl+C to stop)")
@click.option(
    "--leave-if-done",
    "leave_if_done",
    is_flag=True,
    help="With --follow: exit when no processes remain",
)
@click.option("--wait", "wait", is_flag=True, help="Wait until all processes finish (shorthand for --follow --leave-if-done)")
@click.option(
    "--store",
    "store_override",
    default=None,
    metavar="PATH",
    help="Store path (default: $ZKM_STORE or ~/knowledge)",
)
def cmd_status(as_json: bool, follow: bool, leave_if_done: bool, wait: bool, store_override: str | None) -> None:
    """Show running zkm processes and their progress."""
    import json as _json
    import sys as _sys
    import time as _time

    if wait:
        follow = True
        leave_if_done = True

    sdir = Path(store_override) if store_override else store_path()
    running_dir = sdir / ".zkm-state" / "running"
    use_ansi = follow and not as_json and _sys.stdout.isatty()
    prev_n = 0  # lines currently occupying the terminal block

    def _render(rows: list[dict]) -> int:
        nonlocal prev_n
        if as_json:
            click.echo(_json.dumps(rows, ensure_ascii=False))
            return len(rows)

        lines = _format_status_lines(rows) if rows else ["no running zkm processes"]

        if use_ansi and prev_n > 0:
            _sys.stdout.write(f"\033[{prev_n}A")
        for line in lines:
            if use_ansi:
                _sys.stdout.write(f"\r{line}\033[K\n")
            else:
                click.echo(line)
        # Erase leftover lines from a taller previous render
        for _ in range(max(0, prev_n - len(lines))):
            _sys.stdout.write(f"\r\033[K\n")
        if use_ansi:
            _sys.stdout.flush()
        # Track how many lines occupy the terminal block (always grows to max seen)
        prev_n = max(len(lines), prev_n)
        return len(rows)

    n_live = _render(_take_status_snapshot(running_dir))

    if not follow:
        return

    if leave_if_done and n_live == 0:
        return

    try:
        while True:
            _time.sleep(2.0)
            n_live = _render(_take_status_snapshot(running_dir, send_sigusr1=False))
            if leave_if_done and n_live == 0:
                break
    except KeyboardInterrupt:
        if use_ansi:
            _sys.stdout.write("\n")
            _sys.stdout.flush()


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
        if hits:
            import os
            if trace.dense_hits > 0:
                floor = float(os.environ.get("ZKM_QUERY_LOW_DENSE_THRESHOLD", "0.5"))
            else:
                floor = float(os.environ.get("ZKM_QUERY_LOW_BM25_THRESHOLD", "1.0"))
            if hits[0].score < floor:
                click.echo(
                    f"zkm: top-hit relevance is low (score={hits[0].score:.3f}); "
                    "the answer may not be grounded in directly matching documents — "
                    "consider rephrasing or checking the Sources list.",
                    err=True,
                )
        for chunk in llm_stream(sdir, hits, question):
            click.echo(chunk, nl=False)
            sys.stdout.flush()
        click.echo()
        if hits:
            click.echo("\nSources:")
            for i, h in enumerate(hits, 1):
                click.echo(f"  [{i}] {h.path}")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except httpx.HTTPError as e:
        click.echo(f"Error: LLM request failed: {e}", err=True)
        sys.exit(1)
