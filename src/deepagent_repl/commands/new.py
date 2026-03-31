"""The /new command — start a fresh thread."""

from __future__ import annotations

from deepagent_repl.commands import command
from deepagent_repl.storage.db import upsert_thread
from deepagent_repl.ui.renderer import render_info


@command("new", "Start a new conversation thread")
async def cmd_new(client, session, args: str) -> None:
    thread_id = await client.create_thread()
    session.thread_id = thread_id
    session.messages = []
    session.input_tokens = 0
    session.output_tokens = 0
    session.total_cost = 0.0

    await upsert_thread(thread_id, session.graph_id or "")

    render_info(f"New thread: {thread_id}")
