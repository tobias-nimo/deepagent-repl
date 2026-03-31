"""Built-in commands: /help, /clear, /exit, /status."""

from __future__ import annotations

import sys

from rich.table import Table

from deepagent_repl.commands import builtin_commands, command, dynamic_commands
from deepagent_repl.ui.renderer import console, render_info


@command("help", "Show available commands")
async def cmd_help(client, session, args: str) -> None:
    builtins = builtin_commands()
    dynamics = dynamic_commands()

    table = Table(show_header=False, expand=False, padding=(0, 2))
    table.add_column("Command", style="bold cyan", min_width=16)
    table.add_column("Description", style="dim")

    for name, desc in sorted(builtins.items()):
        table.add_row(f"/{name}", desc)

    if dynamics:
        table.add_row("", "")
        table.add_row("[bold magenta]Skills[/]", "[dim]from connected agent[/]")
        for name, desc in sorted(dynamics.items()):
            table.add_row(f"/{name}", desc or "—")

    console.print()
    console.print(table)
    console.print()


@command("clear", "Clear the terminal screen")
async def cmd_clear(client, session, args: str) -> None:
    console.clear()


@command("exit", "Exit the REPL")
async def cmd_exit(client, session, args: str) -> None:
    render_info("Goodbye!")
    sys.exit(0)


@command("status", "Show connection and session info")
async def cmd_status(client, session, args: str) -> None:
    from deepagent_repl.config import settings
    from deepagent_repl.utils.cost import format_cost, format_tokens

    render_info(f"Server:    {settings.langgraph_url}")
    render_info(f"Graph:     {session.graph_id or 'not connected'}")
    render_info(f"Assistant: {session.assistant_id or 'not connected'}")
    render_info(f"Thread:    {session.thread_id or 'none'}")
    render_info(f"Model:     {session.model or 'unknown'}")
    render_info(f"Status:    {session.status}")
    in_tok = format_tokens(session.input_tokens)
    out_tok = format_tokens(session.output_tokens)
    cost = format_cost(session.total_cost)
    render_info(f"Tokens:    {in_tok} in / {out_tok} out")
    render_info(f"Cost:      {cost}")
