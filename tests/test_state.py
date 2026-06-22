"""Red-test spec for `zkm.state` — the shared source-watermark module (ROADMAP id:f399).

Behavior-preserving lift of zkm-whatsapp's `state.py` into core, generalized with a
`plugin` parameter so each plugin gets `.zkm-state/zkm-<plugin>.json`, keyed by a source
identifier (multi-account independence). RED until `src/zkm/state.py` exists.

Contract (mirrors plugins/zkm-whatsapp/state.py):
- state file at `<store>/.zkm-state/zkm-<plugin>.json`
- keyed by the resolved/absolute source identifier
- watermark is a speed optimisation only; deleting the file is always safe
- writes go through `zkm.atomic.write_atomic`
"""

from __future__ import annotations

from pathlib import Path

def test_round_trip(tmp_path: Path):  # roadmap:f399
    from zkm.state import load_state, save_state

    store = tmp_path / "store"
    store.mkdir()
    src = tmp_path / "msgstore.db"
    src.write_bytes(b"x")

    assert load_state(store, "whatsapp", src) == {}
    save_state(store, "whatsapp", src, {"watermark_ms": 1776083400000})
    assert load_state(store, "whatsapp", src) == {"watermark_ms": 1776083400000}


def test_keyed_by_source_multi_account(tmp_path: Path):  # roadmap:f399
    from zkm.state import load_state, save_state

    store = tmp_path / "store"
    store.mkdir()
    a = tmp_path / "acct-a.db"
    b = tmp_path / "acct-b.db"
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    save_state(store, "whatsapp", a, {"watermark_ms": 1})
    save_state(store, "whatsapp", b, {"watermark_ms": 2})
    # independent per source — saving one must not clobber the other
    assert load_state(store, "whatsapp", a) == {"watermark_ms": 1}
    assert load_state(store, "whatsapp", b) == {"watermark_ms": 2}


def test_per_plugin_file(tmp_path: Path):  # roadmap:f399
    from zkm.state import load_state, save_state

    store = tmp_path / "store"
    store.mkdir()
    src = tmp_path / "src.db"
    src.write_bytes(b"x")

    save_state(store, "whatsapp", src, {"watermark_ms": 1})
    save_state(store, "signal", src, {"watermark_ms": 2})
    assert (store / ".zkm-state" / "zkm-whatsapp.json").exists()
    assert (store / ".zkm-state" / "zkm-signal.json").exists()
    assert load_state(store, "whatsapp", src) == {"watermark_ms": 1}
    assert load_state(store, "signal", src) == {"watermark_ms": 2}
