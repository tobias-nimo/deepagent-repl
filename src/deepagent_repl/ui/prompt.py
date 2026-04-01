from __future__ import annotations

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input import ansi_escape_sequences as ansi
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

# Map Shift+Enter escape sequences to an unused function key so we can bind it.
# Terminals using the kitty keyboard protocol (kitty, WezTerm, Ghostty, etc.)
# send CSI 13;2u for Shift+Enter. prompt_toolkit 3.0.x lacks Keys.ShiftEnter,
# so we route the sequence through F24 which is otherwise unused.
_SHIFT_ENTER_KEY = Keys.F24
ansi.ANSI_SEQUENCES["\x1b[13;2u"] = _SHIFT_ENTER_KEY

# Persistent history file
HISTORY_DIR = Path.home() / ".deepagent-repl"
HISTORY_FILE = HISTORY_DIR / "history"


class CommandCompleter(Completer):
    """Dynamic completer that reads from the command registry on each invocation."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        from deepagent_repl.commands import all_command_names

        for cmd in all_command_names():
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))


def _create_key_bindings() -> KeyBindings:
    """Key bindings for multi-line input.

    - Enter: submit (when not in multi-line continuation)
    - Ctrl+J / Alt+Enter: insert newline
    - The prompt_toolkit multiline=True + these bindings give us the right behavior.
    """
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _alt_enter(event):
        """Alt+Enter inserts a newline."""
        event.current_buffer.insert_text("\n")

    @kb.add("c-j")
    def _ctrl_j(event):
        """Ctrl+J inserts a newline."""
        event.current_buffer.insert_text("\n")

    @kb.add(_SHIFT_ENTER_KEY)
    def _shift_enter(event):
        """Shift+Enter inserts a newline (kitty keyboard protocol)."""
        event.current_buffer.insert_text("\n")

    @kb.add("c-l")
    def _ctrl_l(event):
        """Ctrl+L clears the screen."""
        event.app.renderer.clear()

    @kb.add("enter")
    def _enter(event):
        """Enter submits unless the buffer has an unterminated code block or trailing backslash."""
        buf = event.current_buffer
        text = buf.text

        # If text ends with a backslash, treat as continuation
        if text.rstrip().endswith("\\"):
            buf.insert_text("\n")
            return

        # Submit
        buf.validate_and_handle()

    return kb


def _get_continuation(width: int, line_number: int, wrap_count: int) -> HTML:
    """Continuation prompt for multi-line input."""
    return HTML("<dim>. </dim>")


def create_prompt_session(bottom_toolbar=None) -> PromptSession:
    """Create a Prompt Toolkit session with multi-line, history, and completion."""
    # Ensure history directory exists
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    return PromptSession(
        message=HTML("<b>> </b>"),
        multiline=True,
        prompt_continuation=_get_continuation,
        key_bindings=_create_key_bindings(),
        history=FileHistory(str(HISTORY_FILE)),
        completer=CommandCompleter(),
        complete_while_typing=False,
        bottom_toolbar=bottom_toolbar,
    )


async def read_input(
    session: PromptSession,
    prompt_text: str | None = None,
) -> str | None:
    """Read input from the user. Returns None on EOF (Ctrl+D).

    If prompt_text is provided, it overrides the session's default prompt
    and disables multi-line mode (used for single-line prompts like interrupt choices).
    """
    kwargs = {}
    if prompt_text is not None:
        kwargs["message"] = HTML(f"<b>{prompt_text} </b>")
        kwargs["multiline"] = False
    try:
        return await session.prompt_async(**kwargs)
    except EOFError:
        return None
    except KeyboardInterrupt:
        return ""
