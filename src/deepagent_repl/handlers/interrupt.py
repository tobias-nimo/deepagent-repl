from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterruptInfo:
    """Parsed interrupt from thread state."""

    interrupt_id: str
    value: Any
    task_id: str | None = None
    options: list[str] = field(default_factory=list)
    description: str = ""
    detail: str = ""

    @property
    def has_options(self) -> bool:
        return len(self.options) > 0


def extract_interrupts(thread_state: dict) -> list[InterruptInfo]:
    """Extract pending interrupts from a thread state response.

    The thread state may expose interrupts at:
    - state["interrupts"] — top-level list
    - state["tasks"][*]["interrupts"] — per-task interrupts
    """
    interrupts: list[InterruptInfo] = []

    # Per-task interrupts (more common in Deep Agents)
    for task in thread_state.get("tasks", []):
        task_id = task.get("id")
        for raw in task.get("interrupts", []):
            interrupts.append(_parse_interrupt(raw, task_id))

    # Top-level interrupts fallback
    if not interrupts:
        for raw in thread_state.get("interrupts", []):
            interrupts.append(_parse_interrupt(raw, None))

    return interrupts


def _parse_interrupt(raw: dict, task_id: str | None) -> InterruptInfo:
    """Parse a single interrupt dict into an InterruptInfo."""
    interrupt_id = raw.get("id", "")
    value = raw.get("value", {})

    description = ""
    detail = ""
    options: list[str] = []

    if isinstance(value, dict):
        # Common HITL interrupt shapes:
        # {"action": "edit_file", "path": "...", "diff": "...", "options": [...]}
        # {"question": "...", "options": [...]}
        # {"type": "approve", "tool_name": "...", "args": {...}}
        description = (
            value.get("question")
            or value.get("description")
            or value.get("message")
            or value.get("action")
            or value.get("type")
            or ""
        )
        detail = (
            value.get("diff")
            or value.get("detail")
            or value.get("content")
            or value.get("path")
            or ""
        )
        if isinstance(detail, dict):
            import json

            detail = json.dumps(detail, indent=2, ensure_ascii=False)

        raw_options = value.get("options", [])
        if isinstance(raw_options, list):
            options = [str(o) for o in raw_options]
    elif isinstance(value, str):
        description = value
    else:
        description = str(value)

    # Default options if none provided
    if not options:
        options = ["approve", "reject"]

    return InterruptInfo(
        interrupt_id=interrupt_id,
        value=value,
        task_id=task_id,
        options=options,
        description=description,
        detail=detail,
    )


def build_resume_value(interrupt: InterruptInfo, choice: str, edited_content: str | None = None):
    """Build the resume value to send back to the server.

    The resume value format depends on the interrupt's original value structure.
    """
    if edited_content is not None:
        # User edited the content — send it back
        if isinstance(interrupt.value, dict):
            return {**interrupt.value, "action": choice, "content": edited_content}
        return edited_content

    # Simple choice — return the choice string directly
    # Many HITL implementations just expect the option string
    return choice


def open_in_editor(content: str, suffix: str = ".txt") -> str | None:
    """Open content in the user's $EDITOR for editing.

    Returns the edited content, or None if the user cancelled (empty file).
    """
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path], check=False)
        if result.returncode != 0:
            return None
        with open(tmp_path) as f:
            edited = f.read()
        return edited if edited.strip() else None
    finally:
        os.unlink(tmp_path)
