"""HITL interrupt parsing and resume-value building in handlers/interrupt.py.

`extract_interrupts` pulls interrupts from per-task or top-level state.
`_parse_interrupt` handles three shapes: HumanInTheLoopMiddleware requests,
generic `{question, options}` dicts, and bare strings. `build_resume_value`
turns a user choice into the structured payload the server expects, which
differs for HITL-middleware interrupts vs legacy ones.
"""

from __future__ import annotations

from deepagent_tui.handlers.interrupt import (
    InterruptInfo,
    build_resume_value,
    extract_interrupts,
)


def _hitl_value(*names: str, allowed=("approve", "reject", "edit")) -> dict:
    return {
        "action_requests": [{"name": n, "args": {"path": f"{n}.py"}} for n in names],
        "review_configs": [{"action_name": names[0], "allowed_decisions": list(allowed)}],
    }


# ── extract_interrupts ────────────────────────────────────────────────────


def test_extract_prefers_per_task_interrupts():
    state = {
        "tasks": [{"id": "task-1", "interrupts": [{"id": "i1", "value": "stop here"}]}],
        "interrupts": [{"id": "ignored", "value": "x"}],
    }
    got = extract_interrupts(state)
    assert len(got) == 1
    assert got[0].interrupt_id == "i1"
    assert got[0].task_id == "task-1"
    assert got[0].description == "stop here"


def test_extract_falls_back_to_top_level_interrupts():
    state = {"interrupts": [{"id": "i9", "value": "top"}]}
    got = extract_interrupts(state)
    assert [i.interrupt_id for i in got] == ["i9"]
    assert got[0].task_id is None


def test_extract_returns_empty_when_none():
    assert extract_interrupts({}) == []


# ── generic interrupt shapes ──────────────────────────────────────────────


def test_parse_generic_question_with_options():
    state = {"interrupts": [{"id": "i1", "value": {"question": "Env?", "options": ["a", "b"]}}]}
    info = extract_interrupts(state)[0]
    assert info.description == "Env?"
    assert info.options == ["a", "b"]
    assert info.has_options is True


def test_parse_generic_dict_detail_is_json_encoded():
    state = {"interrupts": [{"id": "i1", "value": {"action": "write", "detail": {"k": "v"}}}]}
    info = extract_interrupts(state)[0]
    assert info.description == "write"
    assert '"k": "v"' in info.detail
    # No options provided → defaults to approve/reject.
    assert info.options == ["approve", "reject"]


def test_parse_bare_string_value():
    state = {"interrupts": [{"id": "i1", "value": "just text"}]}
    info = extract_interrupts(state)[0]
    assert info.description == "just text"
    assert info.options == ["approve", "reject"]


# ── HITL-middleware shape ─────────────────────────────────────────────────


def test_parse_hitl_middleware_interrupt():
    state = {"interrupts": [{"id": "i1", "value": _hitl_value("edit_file")}]}
    info = extract_interrupts(state)[0]
    assert info.description == "edit_file"
    assert info.options == ["approve", "reject", "edit"]
    assert "edit_file:" in info.detail
    assert "path" in info.detail


def test_parse_hitl_multiple_actions_join_names():
    state = {"interrupts": [{"id": "i1", "value": _hitl_value("edit_file", "write_file")}]}
    info = extract_interrupts(state)[0]
    assert info.description == "edit_file, write_file"


# ── build_resume_value ────────────────────────────────────────────────────


def test_resume_hitl_approve_one_decision_per_action():
    value = _hitl_value("edit_file", "write_file")
    interrupt = InterruptInfo(interrupt_id="i1", value=value)
    resume = build_resume_value(interrupt, "approve")
    assert resume == {"decisions": [{"type": "approve"}, {"type": "approve"}]}


def test_resume_hitl_reject_carries_optional_message():
    value = _hitl_value("edit_file")
    interrupt = InterruptInfo(interrupt_id="i1", value=value)
    resume = build_resume_value(interrupt, "reject", edited_content="too risky")
    assert resume["decisions"][0]["type"] == "reject"
    assert resume["decisions"][0]["message"] == "too risky"


def test_resume_hitl_edit_rebuilds_action_args():
    value = _hitl_value("edit_file")
    interrupt = InterruptInfo(interrupt_id="i1", value=value)
    resume = build_resume_value(interrupt, "edit", edited_content="new body")
    decision = resume["decisions"][0]
    assert decision["type"] == "edit"
    assert decision["edited_action"]["name"] == "edit_file"
    assert decision["edited_action"]["args"]["content"] == "new body"
    # Original args are preserved alongside the injected content.
    assert decision["edited_action"]["args"]["path"] == "edit_file.py"


def test_resume_legacy_dict_merges_action_and_content():
    interrupt = InterruptInfo(interrupt_id="i1", value={"question": "go?"})
    resume = build_resume_value(interrupt, "approve", edited_content="yes")
    assert resume == {"question": "go?", "action": "approve", "content": "yes"}


def test_resume_legacy_plain_choice():
    interrupt = InterruptInfo(interrupt_id="i1", value="text")
    assert build_resume_value(interrupt, "approve") == "approve"


def test_resume_legacy_edited_content_without_dict_returns_content():
    interrupt = InterruptInfo(interrupt_id="i1", value="text")
    assert build_resume_value(interrupt, "edit", edited_content="payload") == "payload"
