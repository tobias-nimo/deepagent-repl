"""The /threads command — list saved threads."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text

from deepagent_repl.commands import command
from deepagent_repl.storage.db import list_threads
from deepagent_repl.ui.renderer import console, render_info


@command("threads", "List saved conversation threads")
async def cmd_threads(client, session, args: str) -> None:
    threads = await list_threads()
    if not threads:
        render_info("No saved threads.")
        return

    table = Table(show_header=True, header_style="bold", expand=False, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Thread ID", width=12)
    table.add_column("Graph", width=16)
    table.add_column("Messages", justify="right", width=8)
    table.add_column("Last Message", max_width=40)
    table.add_column("Updated", width=19)

    for i, t in enumerate(threads, 1):
        is_current = t["id"] == session.thread_id
        tid_display = t["id"][:12] + "..."
        if is_current:
            tid_display = f"* {tid_display}"

        last_msg = t["last_message"]
        if len(last_msg) > 40:
            last_msg = last_msg[:37] + "..."

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
