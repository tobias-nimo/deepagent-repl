"""The /resume command — interactive thread picker to resume a past conversation."""

from __future__ import annotations

from deepagent_repl.commands import command
from deepagent_repl.storage.db import get_thread, list_threads
from deepagent_repl.ui.prompt import select_option_interactive
from deepagent_repl.ui.renderer import render_error, render_info


def _format_option(t: dict, is_current: bool) -> str:
    """Build a single-line label for a thread selector entry."""
    marker = "* " if is_current else "  "
    tid = t["id"][:10] + "…"
    graph = t["graph_id"] or ""
    msgs = str(t["message_count"])
    last = (t["last_message"] or "")[:30]
    updated = (t["updated_at"] or "")[:16]
    return f"{marker}{tid}  {graph:<12}  {msgs:>3} msgs  {last:<30}  {updated}"


@command("resume", "Resume a past conversation thread")
async def cmd_resume(client, session, args: str) -> None:
    # If a thread ID was passed directly, try to resume it
    if args.strip():
        await _resume_by_id(client, session, args.strip())
        return

    threads = await list_threads(limit=10)
    if not threads:
        render_info("No saved threads to resume.")
        return

    options = [_format_option(t, t["id"] == session.thread_id) for t in threads]
    chosen = await select_option_interactive(options)
    if chosen is None:
        render_info("Cancelled.")
        return

    idx = options.index(chosen)
    await _switch_thread(client, session, threads[idx]["id"])


async def _resume_by_id(client, session, thread_id: str) -> None:
    """Resume a thread by its full or partial ID."""
    # Try local DB first
    record = await get_thread(thread_id)
    if record:
        await _switch_thread(client, session, record["id"])
        return

    # Try partial match from local DB
    threads = await list_threads(limit=200)
    matches = [t for t in threads if t["id"].startswith(thread_id)]
    if len(matches) == 1:
        await _switch_thread(client, session, matches[0]["id"])
        return
    elif len(matches) > 1:
        render_error(f"Ambiguous thread ID prefix '{thread_id}' — {len(matches)} matches.")
        return

    # Try directly from server
    try:
        await client.get_thread(thread_id)
        await _switch_thread(client, session, thread_id)
    except Exception:
        render_error(f"Thread '{thread_id}' not found.")


async def _switch_thread(client, session, thread_id: str) -> None:
    """Switch the session to a different thread."""
    session.thread_id = thread_id
    session.messages = []
    session.input_tokens = 0
    session.output_tokens = 0
    session.total_cost = 0.0

    # Try to load conversation summary from server
    try:
        state = await client.get_thread_state(thread_id)
        messages = state.get("values", {}).get("messages", [])
        if messages:
            msg_count = len(messages)
            last_msg = messages[-1]
            last_content = last_msg.get("content", "")
            if isinstance(last_content, list):
                last_content = " ".join(
                    c.get("text", "") for c in last_content if isinstance(c, dict)
                )
            preview = last_content[:80] + "..." if len(last_content) > 80 else last_content
            render_info(f"Resumed thread: {thread_id}")
            render_info(f"  {msg_count} messages — last: {preview}")
        else:
            render_info(f"Resumed thread: {thread_id} (empty)")
    except Exception:
        render_info(f"Resumed thread: {thread_id}")
