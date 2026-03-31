"""The /theme command — switch terminal color themes."""

from __future__ import annotations

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import render_error, render_info
from deepagent_repl.ui.theme import available_themes, current_theme, set_theme


@command("theme", "Switch color theme: /theme [name]")
async def cmd_theme(client, session, args: str) -> None:
    name = args.strip()

    if not name:
        render_info(f"Current theme: {current_theme()}")
        render_info(f"Available: {', '.join(available_themes())}")
        return

    if set_theme(name):
        render_info(f"Switched to theme: {name}")
    else:
        render_error(f"Unknown theme: {name}")
        render_info(f"Available: {', '.join(available_themes())}")
