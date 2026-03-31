"""The /export command — save conversation to a markdown file."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import render_error, render_info


@command("export", "Export conversation to markdown: /export [filename]")
async def cmd_export(client, session, args: str) -> None:
    if not session.thread_id:
        render_error("No active thread.")
        return

    # Fetch thread state
    try:
        state = await client.get_thread_state(session.thread_id)
    except Exception as e:
        render_error(f"Failed to fetch thread state: {e}")
        return

    messages = state.get("values", {}).get("messages", [])
    if not messages:
        render_info("No messages to export.")
        return

    # Determine output filename
    filename = args.strip()
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tid_short = session.thread_id[:8] if session.thread_id else "thread"
        filename = f"conversation_{tid_short}_{ts}.md"

    if not filename.endswith(".md"):
        filename += ".md"

    # Build markdown
    lines: list[str] = []
    lines.append("# Conversation Export")
    lines.append("")
    lines.append(f"- **Thread:** {session.thread_id}")
    lines.append(f"- **Graph:** {session.graph_id}")
    lines.append(f"- **Exported:** {datetime.now().isoformat()}")
    lines.append(f"- **Messages:** {len(messages)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in messages:
        role = msg.get("role") or msg.get("type", "unknown")
        content = msg.get("content", "")

        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts)

        if role in ("user", "human"):
            lines.append("## User")
        elif role in ("ai", "assistant"):
            lines.append("## Assistant")
        elif role == "tool":
            tool_name = msg.get("name", "tool")
            lines.append(f"## Tool: {tool_name}")
        else:
            lines.append(f"## {role}")

        lines.append("")
        lines.append(content)
        lines.append("")

        # Include tool calls if present
        for tc in msg.get("tool_calls", []):
            lines.append(f"> **Tool call:** {tc.get('name', 'unknown')}")
            args_str = tc.get("args", "")
            if isinstance(args_str, dict):
                import json

                args_str = json.dumps(args_str, indent=2, ensure_ascii=False)
            if args_str:
                lines.append(f"> ```\n> {args_str}\n> ```")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Write file
    path = Path(filename)
    path.write_text("\n".join(lines))
    render_info(f"Exported {len(messages)} messages to {path.resolve()}")
