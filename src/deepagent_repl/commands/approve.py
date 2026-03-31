"""The /approve command — manage approval rules for tool calls."""

from __future__ import annotations

from rich.table import Table

from deepagent_repl.commands import command
from deepagent_repl.storage.rules import (
    ALLOW,
    ASK,
    DENY,
    add_rule,
    load_rules,
    remove_rule,
)
from deepagent_repl.ui.renderer import console, render_error, render_info


@command("approve", "Manage tool approval rules: /approve [allow|ask|deny|remove] [tool]")
async def cmd_approve(client, session, args: str) -> None:
    parts = args.strip().split(None, 1)

    # No args: show current rules
    if not parts or not parts[0]:
        _show_rules()
        return

    action = parts[0].lower()
    tool_name = parts[1].strip() if len(parts) > 1 else ""

    if action == "remove":
        if not tool_name:
            render_error("Usage: /approve remove <tool_name>")
            return
        if remove_rule(tool_name):
            render_info(f"Removed rule for '{tool_name}'.")
        else:
            render_info(f"No rule found for '{tool_name}'.")
        return

    if action not in (ALLOW, ASK, DENY):
        render_error(f"Unknown action: {action}. Use allow, ask, deny, or remove.")
        return

    if not tool_name:
        render_error(f"Usage: /approve {action} <tool_name>")
        return

    add_rule(action, tool_name)
    render_info(f"Rule added: {action} '{tool_name}'.")


def _show_rules() -> None:
    """Display all current approval rules."""
    rules = load_rules()

    has_rules = any(rules[k] for k in ("allow", "ask", "deny"))
    if not has_rules:
        render_info("No approval rules configured.")
        render_info("")
        render_info("Usage:")
        render_info("  /approve allow <tool>   Auto-approve this tool")
        render_info("  /approve ask <tool>     Always prompt for this tool")
        render_info("  /approve deny <tool>    Auto-reject this tool")
        render_info("  /approve remove <tool>  Remove rule for this tool")
        render_info("")
        render_info("Supports wildcards: /approve allow edit_*")
        return

    table = Table(show_header=True, header_style="bold", expand=False, padding=(0, 1))
    table.add_column("Action", style="bold", width=8)
    table.add_column("Tool Pattern")

    for tool in sorted(rules["allow"]):
        table.add_row("[green]allow[/]", tool)
    for tool in sorted(rules["ask"]):
        table.add_row("[yellow]ask[/]", tool)
    for tool in sorted(rules["deny"]):
        table.add_row("[red]deny[/]", tool)

    console.print()
    console.print(table)
    console.print()
