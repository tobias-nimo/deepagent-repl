"""Parsing raw tool-call / tool-result payloads in handlers/tools.py.

`format_tool_call` normalises id/name/args (parsing JSON-string args), detects
subagent delegation, and produces a one-line `summary`. `format_tool_result`
flattens content and flags errors.
"""

from __future__ import annotations

from deepagent_tui.handlers.tools import (
    FormattedToolCall,
    format_tool_call,
    format_tool_result,
)


def test_format_tool_call_basic_fields_and_summary():
    tc = format_tool_call({"id": "1", "name": "read_file", "args": {"path": "a.py"}})
    assert tc.id == "1"
    assert tc.name == "read_file"
    assert tc.args == {"path": "a.py"}
    assert tc.is_subagent is False
    assert tc.summary == "read_file(path=a.py)"


def test_format_tool_call_no_args_summary_is_bare_name():
    assert format_tool_call({"name": "ping"}).summary == "ping"


def test_format_tool_call_parses_json_string_args():
    tc = format_tool_call({"name": "edit", "args": '{"file_path": "x.py"}'})
    assert tc.args == {"file_path": "x.py"}


def test_format_tool_call_non_json_string_args_become_input():
    tc = format_tool_call({"name": "shell", "args": "ls -la"})
    assert tc.args == {"input": "ls -la"}


def test_format_tool_call_empty_string_args_become_empty_dict():
    assert format_tool_call({"name": "noop", "args": ""}).args == {}


def test_format_tool_call_defaults_for_missing_fields():
    tc = format_tool_call({})
    assert tc.id == ""
    assert tc.name == "unknown"
    assert tc.args == {}


def test_subagent_call_detected_and_summarised():
    tc = format_tool_call(
        {"name": "task", "args": {"agent_name": "researcher", "input": "go find X"}}
    )
    assert tc.is_subagent is True
    assert tc.subagent_name == "researcher"
    assert tc.subagent_input == "go find X"
    assert tc.summary == "[subagent] researcher: go find X"


def test_subagent_dict_input_is_json_encoded():
    tc = format_tool_call({"name": "delegate", "args": {"name": "w", "task": {"k": "v"}}})
    assert tc.subagent_input == '{"k": "v"}'


def test_subagent_summary_truncates_long_input():
    long_input = "x" * 100
    tc = format_tool_call({"name": "task", "args": {"agent": "a", "message": long_input}})
    # _truncate caps at 60 chars including the trailing ellipsis.
    assert tc.summary.endswith("...")
    assert len(tc.summary) < len(long_input) + 30


def test_format_tool_result_flattens_content_and_flags_error():
    ok = format_tool_result({"name": "bash", "content": "hi", "tool_call_id": "1"})
    assert ok.content == "hi"
    assert ok.is_error is False
    assert ok.tool_call_id == "1"

    err = format_tool_result({"name": "bash", "content": "boom", "status": "error"})
    assert err.is_error is True


def test_format_tool_result_summary_truncates():
    long = "y" * 500
    res = format_tool_result({"name": "bash", "content": long})
    assert res.summary.endswith("...")
    assert len(res.summary) <= 200


def test_tool_call_summary_truncates_long_arg_values():
    tc = FormattedToolCall(id="1", name="grep", args={"pattern": "z" * 100})
    # Each arg value is truncated to 40 chars (with ellipsis) by `summary`.
    assert "..." in tc.summary
