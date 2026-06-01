"""Inline tool-call / tool-result renderers in ui/tool_widgets.py.

These renderers are pure functions of `FormattedToolCall` / `FormattedToolResult`
plus the module-level widget mode. We render to a rich renderable and flatten it
to plain text (`_plain`) to assert on the visible content, markers, and the
mode-dependent caps. The `reset_mode` fixture restores the default widget mode
after each test so cases that flip it don't bleed into the next.
"""

from __future__ import annotations

import pytest
from rich.console import Group
from rich.text import Text

from deepagent_tui.handlers.tools import FormattedToolCall, FormattedToolResult
from deepagent_tui.ui import tool_widgets as tw


@pytest.fixture(autouse=True)
def reset_mode():
    yield
    tw.set_widget_mode("default")


def _plain(renderable) -> str:
    """Flatten a Text/Group renderable tree to plain text."""
    if isinstance(renderable, Text):
        return renderable.plain
    if isinstance(renderable, Group):
        return "\n".join(_plain(r) for r in renderable.renderables)
    return str(renderable)


def _call(name: str, **args) -> FormattedToolCall:
    return FormattedToolCall(id="x", name=name, args=args)


def _result(content: str, *, name: str = "tool", is_error: bool = False) -> FormattedToolResult:
    return FormattedToolResult(tool_call_id="x", name=name, content=content, is_error=is_error)


# ── markers, aliases, arg formatting ──────────────────────────────────────


def test_state_marker_maps_states_to_glyph_and_colour():
    assert tw._state_marker("success") == (tw._MARKER, "#1a7f37")
    assert tw._state_marker("error") == (tw._MARKER, "#9a2a2a")
    assert tw._state_marker("rejected") == (tw._MARKER, "#a16207")
    assert tw._state_marker("pending") == (tw._PENDING_MARKER, "dim")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("edit_file", "edit"),
        ("str_replace_editor", "edit"),
        ("write_file", "write"),
        ("read_file", "read"),
        ("todo_write", "write_todos"),
        ("shell", "bash"),
        ("list_files", "ls"),
        ("unknown_tool", "unknown_tool"),
    ],
)
def test_tool_alias(raw, expected):
    assert tw._tool_alias(raw) == expected


def test_format_args_truncates_and_caps_total():
    out = tw._format_args({"a": "x" * 100, "b": "short"})
    assert "…" in out
    # The long value is truncated; both keys may appear but total is capped.
    assert out.startswith("a=")


# ── call renderers ────────────────────────────────────────────────────────


def test_render_unknown_call_uses_generic_header():
    out = _plain(tw.render_tool_call_widget(_call("frobnicate", x=1)))
    assert "frobnicate" in out
    assert "x=1" in out


def test_render_read_call_shows_path_and_range():
    out = _plain(tw.render_tool_call_widget(_call("read_file", path="a.py", offset=10, limit=5)))
    assert "Read" in out
    assert "a.py" in out
    assert "offset=10" in out and "limit=5" in out


def test_render_bash_call_shows_command_and_description():
    out = _plain(tw.render_tool_call_widget(_call("shell", command="ls -la", description="list")))
    assert "Bash" in out
    assert "ls -la" in out
    assert "list" in out


def test_render_edit_call_pending_shows_diff_body():
    call = _call("edit_file", file_path="a.py", old_string="one\n", new_string="two\n")
    out = _plain(tw.render_tool_call_widget(call, state="pending"))
    assert "Edit" in out
    assert "a.py" in out
    # Pending edit renders a reviewable diff.
    assert "two" in out


def test_render_edit_call_compacted_hides_diff():
    tw.set_widget_mode("compacted")
    call = _call("edit_file", file_path="a.py", old_string="one\n", new_string="two\n")
    out = _plain(tw.render_tool_call_widget(call, state="pending"))
    assert "Edit" in out
    assert "two" not in out  # body suppressed in compacted mode


def test_render_write_call_pending_shows_added_lines():
    call = _call("write_file", file_path="new.py", content="line1\nline2")
    out = _plain(tw.render_tool_call_widget(call, state="pending"))
    assert "Write" in out
    assert "Added 2 lines" in out
    assert "line1" in out


def test_render_grep_call_shows_pattern_path_glob():
    out = _plain(tw.render_tool_call_widget(_call("grep", pattern="foo", path="src", glob="*.py")))
    assert "Grep" in out
    assert "foo" in out and "src" in out and "*.py" in out


def test_render_glob_call_shows_pattern():
    out = _plain(tw.render_tool_call_widget(_call("glob", pattern="**/*.md", path="docs")))
    assert "Glob" in out
    assert "**/*.md" in out and "docs" in out


def test_render_ls_call_shows_path():
    assert "config" in _plain(tw.render_tool_call_widget(_call("list_files", path="config")))


def test_render_compact_call_pending_and_done():
    pending = _plain(tw.render_tool_call_widget(_call("compact_conversation"), state="pending"))
    assert "summarising" in pending
    done = _plain(tw.render_tool_call_widget(_call("compact_conversation"), state="success"))
    assert "Compact" in done


# ── todos / plan ──────────────────────────────────────────────────────────


def test_todos_progress_summary_variants():
    assert tw._todos_progress_summary([]) == ""
    assert tw._todos_progress_summary(["pending", "pending"]) == "2 todos"
    assert tw._todos_progress_summary(["completed", "completed"]) == "2/2 done"
    assert tw._todos_progress_summary(["completed", "in_progress", "pending"]) == (
        "1/3 · 1 in progress"
    )


def test_render_todos_widget_marks_each_status():
    todos = [
        {"status": "completed", "content": "done item"},
        {"status": "in_progress", "content": "active item"},
        {"status": "pending", "content": "todo item"},
    ]
    out = _plain(tw.render_todos_widget(todos))
    assert "Plan" in out
    assert "done item" in out and "active item" in out and "todo item" in out


def test_render_todos_widget_invalid_input():
    assert "invalid" in _plain(tw.render_todos_widget("nope"))


def test_todos_all_completed():
    assert tw.todos_all_completed([{"status": "completed"}, {"status": "skipped"}]) is True
    assert tw.todos_all_completed([{"status": "completed"}, {"status": "pending"}]) is False
    assert tw.todos_all_completed([]) is False


# ── subagent ──────────────────────────────────────────────────────────────


def test_subagent_call_renders_progress_lines():
    tc = FormattedToolCall(
        id="x", name="task", args={"subagent_type": "researcher"}, is_subagent=True
    )
    progress = [("Bash", "ls"), ("Read", "a.py")]
    out = _plain(tw.render_tool_call_widget(tc, progress=progress))
    assert "Subagent" in out
    assert "researcher" in out
    assert "Bash" in out and "Read" in out


def test_subagent_progress_capped_in_default_mode():
    tc = FormattedToolCall(id="x", name="task", args={}, is_subagent=True)
    progress = [("Bash", str(i)) for i in range(10)]
    out = _plain(tw.render_tool_call_widget(tc, progress=progress))
    # Default cap is the last 3 entries.
    assert out.count("Bash") == tw._SUBAGENT_PROGRESS_MAX


def test_progress_summary_per_tool():
    assert tw._progress_summary(_call("shell", command="ls -la")) == ("Bash", "ls -la")
    assert tw._progress_summary(_call("read_file", path="a.py")) == ("Read", "a.py")
    name, _ = tw._progress_summary(_call("write_todos", todos=[{"status": "completed"}]))
    assert name == "Plan"


# ── diff helpers ──────────────────────────────────────────────────────────


def test_build_diff_lines_classifies_additions_and_removals():
    diff = tw._build_diff_lines("a\nb\n", "a\nc\n")
    kinds = {k for k, _ in diff}
    assert "+" in kinds and "-" in kinds


def test_added_removed_summary():
    assert tw._added_removed_summary(0, 0) == "no changes"
    assert tw._added_removed_summary(2, 0) == "Added 2 lines"
    assert tw._added_removed_summary(1, 3) == "Added 1 line, removed 3 lines"


# ── result renderers ──────────────────────────────────────────────────────


def test_result_read_counts_lines():
    out = _plain(tw.render_tool_result_widget(_result("a\nb\nc", name="read_file")))
    assert "3 lines" in out


def test_result_grep_counts_matches_and_zero():
    out = _plain(tw.render_tool_result_widget(_result("hit1\nhit2", name="grep")))
    assert "2 matches" in out
    none = _plain(tw.render_tool_result_widget(_result("No matches found", name="grep")))
    assert "No matches found" in none


def test_result_glob_parses_list_literal():
    out = _plain(tw.render_tool_result_widget(_result("['a.py', 'b.py']", name="glob")))
    assert "2 matches" in out


def test_result_bash_strips_exit_trailer():
    content = "hello\n[Command succeeded with exit code 0]"
    out = _plain(tw.render_tool_result_widget(_result(content, name="bash")))
    assert "hello" in out
    assert "exit code" not in out


def test_result_bash_compacted_summarises_line_count():
    tw.set_widget_mode("compacted")
    out = _plain(tw.render_tool_result_widget(_result("l1\nl2\nl3", name="bash")))
    assert "3 lines" in out


def test_result_edit_renders_diff_from_call_args():
    call = _call("edit_file", old_string="x\n", new_string="y\n")
    res = _result("ok", name="edit_file")
    out = _plain(tw.render_tool_result_widget(res, call))
    assert "y" in out  # the new line shows in the diff body


def test_result_ls_lists_entries_and_caps():
    content = "['a', 'b', 'c', 'd', 'e', 'f', 'g']"
    out = _plain(tw.render_tool_result_widget(_result(content, name="list_files")))
    assert "a" in out
    assert "+2 lines" in out  # 7 entries, default cap is 5


def test_result_generic_inline_for_short_content():
    out = _plain(tw.render_tool_result_widget(_result("short answer", name="whatever")))
    assert "short answer" in out


def test_result_task_is_suppressed():
    assert tw.render_tool_result_widget(_result("subagent output", name="task")) is None


def test_result_write_todos_suppressed_unless_error():
    assert tw.render_tool_result_widget(_result("Updated todo list", name="todo_write")) is None
    err = tw.render_tool_result_widget(_result("boom", name="todo_write", is_error=True))
    assert err is not None


def test_result_compact_extracts_count():
    content = "Conversation compacted. Summarized 12 messages into a concise summary."
    out = _plain(tw.render_tool_result_widget(_result(content, name="compact_conversation")))
    assert "Summarised 12 messages" in out


def test_error_result_renders_error_marker():
    out = _plain(tw.render_tool_result_widget(_result("disk full", name="bash", is_error=True)))
    assert "disk full" in out


def test_result_write_renders_added_content_body():
    call = _call("write_file", file_path="n.py", content="a\nb\nc")
    out = _plain(tw.render_tool_result_widget(_result("saved", name="write_file"), call))
    assert "Added 3 lines" in out
    assert "a" in out and "c" in out


def test_result_ls_empty_listing():
    out = _plain(tw.render_tool_result_widget(_result("[]", name="list_files")))
    assert "(empty)" in out


def test_result_generic_multiline_uses_corner_block():
    content = "\n".join(f"line{i}" for i in range(20))
    out = _plain(tw.render_tool_result_widget(_result(content, name="weird_tool")))
    assert "line0" in out
    assert "+" in out  # overflow summary "… +N lines"


def test_result_compact_below_gate_shows_verbatim():
    msg = "Nothing to compact yet — conversation is within the token budget."
    out = _plain(tw.render_tool_result_widget(_result(msg, name="compact_conversation")))
    assert "Nothing to compact" in out


# ── expanded mode lifts caps ──────────────────────────────────────────────


def test_expanded_read_shows_body():
    tw.set_widget_mode("expanded")
    out = _plain(tw.render_tool_result_widget(_result("l1\nl2\nl3", name="read_file")))
    assert "3 lines" in out
    assert "l1" in out and "l3" in out  # body shown only in expanded mode


def test_expanded_grep_shows_matches():
    tw.set_widget_mode("expanded")
    out = _plain(tw.render_tool_result_widget(_result("hit-a\nhit-b", name="grep")))
    assert "2 matches" in out
    assert "hit-a" in out


def test_expanded_ls_lifts_entry_cap():
    tw.set_widget_mode("expanded")
    content = str([f"f{i}" for i in range(20)])
    out = _plain(tw.render_tool_result_widget(_result(content, name="list_files")))
    assert "f19" in out  # no "+N lines" truncation in expanded mode


# ── HITL rejection ────────────────────────────────────────────────────────


def test_rejected_result_detected_and_rendered_neutrally():
    rejected = _result(
        "User rejected the tool call for edit_file", name="edit_file", is_error=True
    )
    assert tw.is_rejected_result(rejected) is True
    out = _plain(tw.render_tool_result_widget(rejected))
    assert "Rejected by user" in out


# ── parsing helpers ───────────────────────────────────────────────────────


def test_parse_listing_handles_literal_and_newlines():
    assert tw._parse_listing("['a', 'b']") == ["a", "b"]
    assert tw._parse_listing("- a\n- b\n") == ["a", "b"]
    assert tw._parse_listing("") == []


def test_basename_preserves_trailing_slash_for_dirs():
    assert tw._basename("/a/b/c.py") == "c.py"
    assert tw._basename("/a/b/dir/") == "dir/"


def test_strip_bash_trailer_drops_status_and_blank_tail():
    assert tw._strip_bash_trailer("out\n\n[Command failed with exit code 1]") == "out"
