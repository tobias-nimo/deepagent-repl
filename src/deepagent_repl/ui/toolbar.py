"""Bottom toolbar for the REPL prompt — shows session info at a glance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import HTML

if TYPE_CHECKING:
    from deepagent_repl.session import Session

# Status indicator styles
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "idle": ("", "idle"),
    "streaming": ("ansicyan", "streaming..."),
    "interrupted": ("ansiyellow", "waiting for approval"),
}


def create_toolbar(session: "Session"):
    """Return a bottom_toolbar callback that reads live session state."""

    def _toolbar() -> HTML:
        # Left: graph + thread
        graph = session.graph_id or "—"
        tid = session.thread_id or "—"
        tid_short = tid[:8] if len(tid) > 8 else tid
        left = f" {graph} │ {tid_short}"

        # Center: status
        style, label = _STATUS_STYLE.get(session.status, ("", session.status))
        if style:
            center = f"<{style}>{label}</{style}>"
        else:
            center = label

        # Right: tokens + cost
        from deepagent_repl.utils.cost import format_cost, format_tokens

        in_tok = format_tokens(session.input_tokens)
        out_tok = format_tokens(session.output_tokens)
        cost = format_cost(session.total_cost)
        right = f"{in_tok}↑ {out_tok}↓ │ {cost} "

        return HTML(
            f"<style bg='#1a1a2e' fg='#aaaaaa'>"
            f"{left}"
            f"  │  {center}"
            f"  │  {right}"
            f"</style>"
        )

    return _toolbar
