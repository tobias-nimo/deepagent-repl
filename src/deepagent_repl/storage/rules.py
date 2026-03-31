"""Approval rules — persisted JSON file for auto-approve/deny/ask tool decisions."""

from __future__ import annotations

import json
from pathlib import Path

RULES_DIR = Path.home() / ".deepagent-repl"
RULES_FILE = RULES_DIR / "rules.json"

# Rule actions
ALLOW = "allow"
ASK = "ask"
DENY = "deny"


def _load_raw() -> dict:
    """Load rules from the JSON file."""
    if not RULES_FILE.exists():
        return {"allow": [], "ask": [], "deny": []}
    try:
        data = json.loads(RULES_FILE.read_text())
        return {
            "allow": data.get("allow", []),
            "ask": data.get("ask", []),
            "deny": data.get("deny", []),
        }
    except (json.JSONDecodeError, OSError):
        return {"allow": [], "ask": [], "deny": []}


def _save_raw(data: dict) -> None:
    """Save rules to the JSON file."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(data, indent=2) + "\n")


def load_rules() -> dict[str, list[str]]:
    """Load all rules. Returns {"allow": [...], "ask": [...], "deny": [...]}."""
    return _load_raw()


def add_rule(action: str, tool_name: str) -> None:
    """Add a rule. Removes the tool from other lists first to avoid conflicts."""
    data = _load_raw()
    # Remove from all lists
    for key in ("allow", "ask", "deny"):
        data[key] = [t for t in data[key] if t != tool_name]
    # Add to the target list
    if action in data:
        data[action].append(tool_name)
    _save_raw(data)


def remove_rule(tool_name: str) -> bool:
    """Remove a tool from all rule lists. Returns True if found."""
    data = _load_raw()
    found = False
    for key in ("allow", "ask", "deny"):
        if tool_name in data[key]:
            data[key] = [t for t in data[key] if t != tool_name]
            found = True
    if found:
        _save_raw(data)
    return found


def match_rule(tool_name: str) -> str | None:
    """Check if a tool matches any rule.

    Returns "allow", "ask", "deny", or None if no rule matches.
    Supports exact match and glob-style prefix matching (e.g., "edit_*").
    """
    data = _load_raw()

    for action in ("deny", "allow", "ask"):
        for pattern in data[action]:
            if _matches(pattern, tool_name):
                return action

    return None


def _matches(pattern: str, tool_name: str) -> bool:
    """Check if a pattern matches a tool name.

    Supports:
    - Exact match: "edit_file" matches "edit_file"
    - Wildcard suffix: "edit_*" matches "edit_file", "edit_code"
    - Wildcard: "*" matches everything
    """
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return tool_name.startswith(pattern[:-1])
    return pattern == tool_name
