"""The /compress command — summarize conversation history to reduce token usage."""

from __future__ import annotations

from deepagent_repl.commands import command
from deepagent_repl.storage.db import upsert_thread
from deepagent_repl.ui.prompt import read_input
from deepagent_repl.ui.renderer import render_error, render_info
from deepagent_repl.utils.cost import format_tokens

# Summarization prompt sent to the agent
_SUMMARIZE_PROMPT = (
    "Please provide a concise summary of our entire conversation so far. "
    "Include all key decisions, important context, code changes discussed, "
    "and any pending tasks or open questions. This summary will be used to "
    "continue the conversation in a new thread with reduced token usage. "
    "Be thorough but compact."
)


@command("compress", "Summarize conversation to reduce token usage")
async def cmd_compress(client, session, args: str) -> None:
    if not session.thread_id or not session.assistant_id:
        render_error("No active thread to compress.")
        return

    total = session.input_tokens + session.output_tokens
    if total == 0:
        render_info("Nothing to compress — no tokens used yet.")
        return

    render_info(f"Current usage: {format_tokens(total)} tokens")
    render_info("This will create a new thread with a summary of the conversation.")

    # Confirm
    choice = await read_input(session.prompt_session, prompt_text="Compress? [y/N]>")
    if not choice or choice.strip().lower() not in ("y", "yes"):
        render_info("Cancelled.")
        return

    render_info("Summarizing conversation...")

    try:
        # Fetch current thread state to get messages
        state = await client.get_thread_state(session.thread_id)
        messages = state.get("values", {}).get("messages", [])

        if not messages:
            render_error("No messages found in current thread.")
            return

        # Send summarization request to the agent on the CURRENT thread
        # so the agent has full context to summarize
        result = await client.send_message(
            session.thread_id, session.assistant_id, _SUMMARIZE_PROMPT
        )

        # Extract the summary from the response
        result_messages = result.get("messages", [])
        summary = ""
        for msg in reversed(result_messages):
            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, list):
                    summary = " ".join(
                        c.get("text", "") for c in content if isinstance(c, dict)
                    )
                else:
                    summary = str(content)
                break

        if not summary:
            render_error("Failed to get summary from agent.")
            return

        # Create a new thread with the summary as context
        context_msg = {
            "role": "user",
            "content": (
                f"[Compressed conversation context]\n\n"
                f"The following is a summary of our previous conversation. "
                f"Please use this context to continue assisting me:\n\n{summary}"
            ),
        }
        summary_reply = {
            "role": "assistant",
            "content": (
                "I've reviewed the conversation summary and have the full context. "
                "I'm ready to continue where we left off. How can I help?"
            ),
        }

        new_thread_id = await client.copy_thread_with_messages(
            [context_msg, summary_reply]
        )

        # Switch session to new thread
        old_tokens = total
        session.thread_id = new_thread_id
        session.messages = []
        session.input_tokens = 0
        session.output_tokens = 0
        session.total_cost = 0.0

        await upsert_thread(new_thread_id, session.graph_id or "")

        render_info(f"Compressed: {format_tokens(old_tokens)} -> new thread")
        render_info(f"New thread: {new_thread_id}")
        render_info("Conversation context preserved via summary.")

    except Exception as e:
        render_error(f"Compression failed: {e}")
