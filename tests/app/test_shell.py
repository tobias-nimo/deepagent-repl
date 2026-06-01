"""The `!` shell prefix: gating before the workspace is known, the middleware
hint, local execution, output rendering, and the plain-paste regression.
"""

from __future__ import annotations

from textual import events
from textual.containers import Container
from textual.widgets import Static

from deepagent_tui.tui.app import ChatTextArea, DeepAgentTUI


def _messages_text(app) -> str:
    msgs = app.query_one("#messages", Container)
    return "\n".join(str(w.content) for w in msgs.children if isinstance(w, Static))


async def test_shell_before_workspace_known_does_not_run() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = None
        app._run_shell_command("!echo should-not-run", "echo should-not-run")
        assert "Send a message first" in _messages_text(app)


async def test_shell_after_message_hints_at_middleware() -> None:
    # Once a message has been sent but the workspace never loaded, the hint
    # should point at the missing server middleware rather than ask the user to
    # send a message they already sent.
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.session.workspace_root = None
        app.session.messages = [{"role": "user", "content": "hi"}]
        app._run_shell_command("!echo nope", "echo nope")
        joined = _messages_text(app)
        assert "Send a message first" not in joined
        assert "docs/server-middleware.md" in joined


async def test_render_shell_output_mounts_widget() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._render_shell_output("hello\nworld", 0)
        joined = _messages_text(app)
        assert "hello" in joined and "world" in joined


async def test_exec_shell_runs_local_command() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        await app._exec_shell("echo hello-shell-marker")
        assert "hello-shell-marker" in _messages_text(app)


async def test_plain_paste_inserts_text_once() -> None:
    """Regression: pasting plain text must insert it exactly once. Textual's
    dispatcher walks the MRO and invokes both ChatTextArea._on_paste and the
    base TextArea._on_paste, so the override must not also call super() — doing
    so doubled the pasted text in the chat bar."""
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        prompt = app.query_one("#prompt", ChatTextArea)
        prompt.focus()
        await pilot.pause()
        prompt._forward_event(events.Paste(text="hello world"))
        await pilot.pause()
        assert prompt.text == "hello world"
