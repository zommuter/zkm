"""Shared utilities for AI session import plugins (zkm-claude-ai, zkm-claude-code).

D3 block rendering rules (deliberate privacy posture):
  text          → verbatim
  thinking      → included, prefixed with "> [thinking]"
  tool_use      → stub "[→ <name>: <short input>]"
  tool_result   → stub "[← result: <N bytes>]" (name+size only, NO payload)
  token_budget  → skipped

Participants model (per messaging-spec per-conversation transcript doc-type):
  address: human     role: human
  address: assistant role: assistant

Conceptual per-message ID formats (not in file-level frontmatter):
  claude-ai:   claude-ai:<conv_uuid>:<msg_uuid>
  claude-code: claude-code:<session_uuid>:<msg_uuid>
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

MAX_TOOL_INPUT_LEN = 80

PARTICIPANTS: list[dict] = [
    {"address": "human", "role": "human"},
    {"address": "assistant", "role": "assistant"},
]


def render_block(blk: dict) -> str | None:
    """Render a single content block per D3 privacy posture.

    Returns None for blocks that should be skipped entirely.
    """
    btype = blk.get("type", "")

    if btype == "text":
        text = blk.get("text") or ""
        return text.strip() if text.strip() else None

    if btype == "thinking":
        thinking = blk.get("thinking") or ""
        if not thinking.strip():
            return None
        quoted = "\n".join(
            f"> {line}" if line.strip() else ">"
            for line in thinking.splitlines()
        )
        return f"> [thinking]\n{quoted}"

    if btype == "tool_use":
        name = blk.get("name", "unknown")
        inp = blk.get("input", {})
        short = json.dumps(inp, ensure_ascii=False)
        if len(short) > MAX_TOOL_INPUT_LEN:
            short = short[: MAX_TOOL_INPUT_LEN - 1] + "…"
        return f"[→ {name}: {short}]"

    if btype == "tool_result":
        content = blk.get("content", "")
        raw = (
            json.dumps(content, ensure_ascii=False)
            if not isinstance(content, str)
            else content
        )
        size = len(raw.encode())
        name = blk.get("name", "")
        label = f" ({name})" if name else ""
        return f"[← result{label}: {size} bytes]"

    # token_budget and unknown types → skip
    return None


def parse_iso_date(ts: str) -> str | None:
    """Parse an ISO 8601 / Z-suffixed timestamp; return with timezone info."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.rstrip("Z"))
        if ts.endswith("Z"):
            dt = dt.replace(tzinfo=UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat(timespec="seconds")
    except ValueError:
        return ts


def format_ts(ts: str) -> str:
    """Return a human-readable timestamp like '2026-04-13 14:30 UTC'."""
    if not ts:
        return ts
    try:
        dt = datetime.fromisoformat(ts.rstrip("Z"))
        if ts.endswith("Z"):
            dt = dt.replace(tzinfo=UTC)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return ts


def slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    s = name.strip().lower()
    s = re.sub(r"[^\w\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or ""
