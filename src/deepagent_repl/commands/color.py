"""The /color command — change the REPL accent color."""

from __future__ import annotations

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import render_error, render_info
from deepagent_repl.ui.theme import SUGGESTED_COLORS, current_accent, set_accent_color


@command("color", "Set accent color: /color [color|#rrggbb]")
async def cmd_color(client, session, args: str) -> None:
    color = args.strip()

    if not color:
        render_info(f"Current accent: {current_accent()}")
        render_info(f"Suggestions: {', '.join(SUGGESTED_COLORS)}")
        render_info("Also accepts hex codes, e.g. /color #ff6600")
        return

    if set_accent_color(color):
        render_info(f"Accent color set to: {color}")
    else:
        render_error(f"Invalid color: {color}")
        render_info(f"Suggestions: {', '.join(SUGGESTED_COLORS)}")
        render_info("Also accepts hex codes, e.g. /color #ff6600")
