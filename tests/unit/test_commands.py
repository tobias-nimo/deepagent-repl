"""The slash-command registry/dispatcher, the shared renderer sink, and the
pure transcript builders behind /copy and /export.

The registry tests use `register_skill` / `clear_dynamic` for isolation so they
never mutate the built-in table. The renderer is exercised through its mount
sink (the contract the TUI relies on). The transcript builders are pure string
functions over a message list.
"""

from __future__ import annotations

import pytest
from rich.text import Text

from deepagent_tui import commands
from deepagent_tui.commands.copy import (
    _extract_text,
    _yaml_scalar,
    build_full_transcript,
    build_last_turn,
)
from deepagent_tui.ui import renderer

# ── registry ──────────────────────────────────────────────────────────────


def test_is_command():
    assert commands.is_command("/help") is True
    assert commands.is_command("hello") is False


def test_builtins_registered_at_import():
    names = commands.builtin_commands()
    # A representative slice of the built-ins side-effect-imported in __init__.
    for expected in ("help", "copy", "export", "resume", "new"):
        assert expected in names


def test_get_command_is_case_insensitive():
    assert commands.get_command("HELP") is not None
    assert commands.get_command("help")[2] == "help"  # canonical name preserved


@pytest.fixture
def temp_skill():
    """Register a dynamic skill that records its invocation, then clean up."""
    calls: list[str] = []

    async def handler(client, session, args: str) -> None:
        calls.append(args)

    commands.register_skill("MySkill", "a test skill", handler)
    yield calls
    commands.clear_dynamic()


def test_register_and_query_dynamic_skill(temp_skill):
    assert commands.is_dynamic("myskill") is True
    assert "MySkill" in commands.dynamic_commands()
    assert "/MySkill" in commands.all_command_names()
    # Built-in still wins precedence-wise, but both appear in all_commands().
    assert "MySkill" in commands.all_commands()


def test_clear_dynamic_removes_skills():
    async def handler(client, session, args: str) -> None:
        return None

    commands.register_skill("Temp", "x", handler)
    assert commands.is_dynamic("temp") is True
    commands.clear_dynamic()
    assert commands.is_dynamic("temp") is False


async def test_dispatch_routes_to_handler_with_args(temp_skill):
    handled = await commands.dispatch(None, None, "/myskill do the thing")
    assert handled is True
    assert temp_skill == ["do the thing"]


async def test_dispatch_unknown_command_returns_false():
    assert await commands.dispatch(None, None, "/definitely-not-a-command") is False


async def test_dispatch_non_command_returns_false():
    assert await commands.dispatch(None, None, "just a message") is False


# ── renderer sink ─────────────────────────────────────────────────────────


def test_renderer_routes_through_mount_sink():
    captured: list = []
    renderer.set_mount_sink(captured.append)
    try:
        renderer.render_info("all good")
        renderer.render_error("oh no")
    finally:
        renderer.set_mount_sink(None)

    assert len(captured) == 2
    info, err = captured
    assert isinstance(info, Text) and "all good" in info.plain
    assert "oh no" in err.plain


def test_render_error_body_is_red():
    captured: list = []
    renderer.set_mount_sink(captured.append)
    try:
        renderer.render_error("boom")
    finally:
        renderer.set_mount_sink(None)
    styles = "".join(str(span.style) for span in captured[0].spans)
    assert "red" in styles


# ── transcript builders ───────────────────────────────────────────────────


def test_extract_text_counts_image_blocks():
    content = [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "x"}},
        {"type": "image", "source": {}},
    ]
    out = _extract_text(content)
    assert "look" in out
    assert "(2 images attached)" in out


def test_yaml_scalar_single_and_multiline():
    assert _yaml_scalar("hi") == "'hi'"
    assert _yaml_scalar("it's") == "'it''s'"  # quote escaping
    multi = _yaml_scalar("a\nb", indent=4)
    assert multi.startswith("|\n")
    assert "      a" in multi  # body indented past the key


def test_build_full_transcript_includes_users_and_tools():
    messages = [
        {"role": "user", "content": "hello"},
        {
            "type": "ai",
            "content": "hi back",
            "tool_calls": [{"id": "t1", "name": "read_file", "args": {"path": "a.py"}}],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "file body"},
    ]
    out = build_full_transcript(messages)
    assert "❯  hello" in out
    assert "hi back" in out
    assert "tool: 'read_file'" in out
    assert "file body" in out


def test_build_last_turn_excludes_prior_turns_and_users():
    messages = [
        {"role": "user", "content": "first"},
        {"type": "ai", "content": "old answer"},
        {"role": "user", "content": "second"},
        {"type": "ai", "content": "new answer"},
    ]
    out = build_last_turn(messages)
    assert "new answer" in out
    assert "old answer" not in out
    assert "second" not in out  # user lines excluded from a last-turn copy
