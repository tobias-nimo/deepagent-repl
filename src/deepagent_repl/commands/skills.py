"""The /skills command — list discovered skills from the connected agent."""

from __future__ import annotations

from rich.table import Table

from deepagent_repl.commands import command, dynamic_commands
from deepagent_repl.ui.renderer import console, render_info


@command("skills", "List available skills from the connected agent")
async def cmd_skills(client, session, args: str) -> None:
    skills = dynamic_commands()
    if not skills:
        render_info("No skills discovered from the connected agent.")
        render_info("Skills are auto-detected on connect if the agent exposes them.")
        return

    table = Table(show_header=True, header_style="bold", expand=False, padding=(0, 1))
    table.add_column("Command", style="bold cyan", min_width=16)
    table.add_column("Description", style="dim")

    for name, desc in sorted(skills.items()):
        table.add_row(f"/{name}", desc or "—")

    console.print()
    console.print(table)
    console.print()
    render_info(f"{len(skills)} skill(s) available. Use /<skill-name> [args] to invoke.")
