"""The /replay command — browse conversation history and fork from an earlier point."""

from __future__ import annotations

from rich.table import Table

from deepagent_repl.commands import command
from deepagent_repl.storage.db import upsert_thread
from deepagent_repl.ui.prompt import read_input
from deepagent_repl.ui.renderer import console, render_error, render_info


def _extract_text(content) -> str:
    """Extract plain text from message content (str or list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return str(content)


@command("replay", "Browse history and fork from an earlier message")
async def cmd_replay(client, session, args: str) -> None:
    if not session.thread_id:
        render_error("No active thread.")
        return

    render_info("Fetching conversation history...")

    try:
        history = await client.get_thread_history(session.thread_id)
    except Exception as e:
        render_error(f"Failed to fetch history: {e}")
        return

    if not history:
        render_info("No history found for this thread.")
        return

    # Extract checkpoints that contain user messages.
    # Each history entry is a state snapshot — we look for ones where the last
    # message is from the user (these are the "before agent replied" checkpoints).
    user_checkpoints: list[tuple[int, str, dict]] = []

    for entry in history:
        values = entry.get("values", {})
        messages = values.get("messages", [])
        if not messages:
            continue

        # Find all user messages in this checkpoint
        for i, msg in enumerate(messages):
            role = msg.get("role") or msg.get("type", "")
            if role in ("user", "human"):
                text = _extract_text(msg.get("content", ""))
                if text.strip():
                    # Use (message_index_in_thread, text, checkpoint_entry) as key
                    # Deduplicate by message index
                    key = len(messages) - 1 - (len(messages) - 1 - i)
                    already = any(uc[0] == i and uc[1] == text for uc in user_checkpoints)
                    if not already:
                        user_checkpoints.append((i, text, entry))

    # Deduplicate — keep the earliest checkpoint for each unique user message text
    seen_texts: set[str] = set()
    unique_checkpoints: list[tuple[int, str, dict]] = []
    for idx, text, entry in user_checkpoints:
        key = f"{idx}:{text[:100]}"
        if key not in seen_texts:
            seen_texts.add(key)
            unique_checkpoints.append((idx, text, entry))

    if not unique_checkpoints:
        render_info("No user messages found in history.")
        return

    # Sort by message position in thread
    unique_checkpoints.sort(key=lambda x: x[0])

    # Display numbered list
    table = Table(show_header=True, header_style="bold", expand=False, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Message", max_width=70)

    for i, (idx, text, _entry) in enumerate(unique_checkpoints, 1):
        preview = text.replace("\n", " ").strip()
        if len(preview) > 70:
            preview = preview[:67] + "..."
        table.add_row(str(i), preview)

    console.print()
    console.print(table)
    console.print()
    render_info("Select a message to fork the conversation from that point.")
    render_info("A new thread will be created with history up to that message.")

    # Prompt for selection
    raw = await read_input(session.prompt_session, prompt_text="fork from #>")
    if not raw or not raw.strip():
        render_info("Cancelled.")
        return

    try:
        choice = int(raw.strip()) - 1
        if not (0 <= choice < len(unique_checkpoints)):
            render_error(f"Choose 1-{len(unique_checkpoints)}")
            return
    except ValueError:
        render_error("Enter a number.")
        return

    idx, text, checkpoint_entry = unique_checkpoints[choice]

    render_info(f"Forking from message #{choice + 1}: {text[:60]}...")

    try:
        # Get the messages up to and including the selected user message
        values = checkpoint_entry.get("values", {})
        messages = values.get("messages", [])
        # Truncate messages to include up to the selected user message
        fork_messages = messages[: idx + 1]

        new_thread_id = await client.copy_thread_with_messages(fork_messages)

        # Switch session
        session.thread_id = new_thread_id
        session.messages = []
        session.input_tokens = 0
        session.output_tokens = 0
        session.total_cost = 0.0

        await upsert_thread(new_thread_id, session.graph_id or "")

        render_info(f"Forked to new thread: {new_thread_id}")
        render_info(f"  {len(fork_messages)} message(s) preserved.")
        render_info("You can now continue the conversation from this point.")

    except Exception as e:
        render_error(f"Fork failed: {e}")
