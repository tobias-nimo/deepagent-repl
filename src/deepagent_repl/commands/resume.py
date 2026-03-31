"""The /resume command — interactive thread picker to resume a past conversation."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from deepagent_repl.commands import command
from deepagent_repl.storage.db import get_thread, list_threads
from deepagent_repl.ui.prompt import read_input
from deepagent_repl.ui.renderer import console, render_error, render_info


@command("resume", "Resume a past conversation thread")
async def cmd_resume(client, session, args: str) -> None:
    # If a thread ID was passed directly, try to resume it
    if args.strip():
        await _resume_by_id(client, session, args.strip())
        return

    threads = await list_threads(limit=20)
    if not threads:
        render_info("No saved threads to resume.")
        return

    # Display numbered list
    table = Table(show_header=True, header_style="bold", expand=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Thread ID", width=12)
    table.add_column("Graph", width=16)
    table.add_column("Msgs", justify="right", width=5)
    table.add_column("Last Message", max_width=50)
    table.add_column("Updated", width=19)

    for i, t in enumerate(threads, 1):
        is_current = t["id"] == session.thread_id
        tid_display = t["id"][:12] + "..."
        last_msg = t["last_message"]
        if len(last_msg) > 50:
            last_msg = last_msg[:47] + "..."
        style = "bold green" if is_current else ""
        table.add_row(
            str(i),
            Text(tid_display, style=style),
            t["graph_id"],
            str(t["message_count"]),
            last_msg,
            t["updated_at"] or "",
        )

    console.print()
    console.print(table)
    console.print()

    # Prompt for selection
    raw = await read_input(session.prompt_session, prompt_text="thread #>")
    if not raw or not raw.strip():
        render_info("Cancelled.")
        return

    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(threads)):
            render_error(f"Choose 1-{len(threads)}")
            return
    except ValueError:
        render_error("Enter a number.")
        return

    selected = threads[idx]
    await _switch_thread(client, session, selected["id"])


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
