from __future__ import annotations

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from deepagent_repl.handlers.interrupt import InterruptInfo
from deepagent_repl.handlers.tools import FormattedToolCall, FormattedToolResult
from deepagent_repl.ui.markdown import render_markdown

console = Console()


class StreamingRenderer:
    """Manages live-updating display during streaming responses.

    While streaming, renders the accumulated buffer as Rich Markdown so that
    syntax highlighting and formatting appear in real time. A spinner is shown
    until the first token arrives.
    """

    def __init__(self):
        self._live: Live | None = None
        self._buffer: str = ""
        self._has_content: bool = False

    def start(self) -> None:
        """Start the live display with a waiting spinner."""
        self._buffer = ""
        self._has_content = False
        self._live = Live(
            Spinner("dots", text="Thinking...", style="dim"),
            console=console,
            refresh_per_second=10,
            transient=True,
            vertical_overflow="visible",
        )
        self._live.start()

    def update(self, text_fragment: str) -> None:
        """Append a text fragment and refresh the display with markdown rendering."""
        if not self._live:
            return
        self._buffer += text_fragment
        self._has_content = True
        md = render_markdown(self._buffer)
        cursor = Text("\u258b", style="bold green")
        self._live.update(Group(md, cursor))

    def finish(self) -> str:
        """Stop the live display and return the accumulated text.

        The live region is transient, so it vanishes on stop. The caller
        should print the final content if needed.
        """
        if self._live:
            self._live.stop()
            self._live = None
        result = self._buffer
        self._buffer = ""
        return result

    @property
    def has_content(self) -> bool:
        return self._has_content


def render_assistant_text(text: str) -> None:
    """Render assistant response text as formatted markdown."""
    if text.strip():
        console.print(render_markdown(text))


def render_tool_call(tc: FormattedToolCall) -> None:
    """Render a tool call with a styled panel."""
    if tc.is_subagent:
        title = f"subagent: {tc.subagent_name or tc.name}"
        body = tc.subagent_input or ""
        style = "magenta"
        border_style = "dim magenta"
    else:
        title = tc.name
        body = _format_args(tc.args)
        style = "cyan"
        border_style = "dim cyan"

    if body:
        panel = Panel(
            Text(body, style="dim"),
            title=Text(f" {title} ", style=f"bold {style}"),
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
            expand=False,
        )
        console.print(panel)
    else:
        console.print(Text(f"  {title}", style=f"bold {style}"))


def render_tool_running(name: str) -> None:
    """Render a spinner indicating a tool is executing."""
    console.print(Spinner("dots", text=f"  Running {name}...", style="dim"))


def render_tool_result(result: FormattedToolResult) -> None:
    """Render a tool result with color-coded status."""
    if result.is_error:
        style = "red"
        icon = "x"
        border_style = "dim red"
    else:
        style = "green"
        icon = "ok"
        border_style = "dim green"

    header = Text(f"  [{icon}] {result.name}", style=f"bold {style}")

    summary = result.summary
    if summary:
        panel = Panel(
            Text(summary, style="dim"),
            title=header,
            title_align="left",
            border_style=border_style,
            padding=(0, 1),
            expand=False,
        )
        console.print(panel)
    else:
        console.print(header)

    # Detect and render any image paths in the tool result
    if not result.is_error and result.content:
        from deepagent_repl.utils.images import detect_image_paths

        for img_path in detect_image_paths(result.content):
            render_image(img_path)


def render_interrupt(interrupt: InterruptInfo) -> None:
    """Render a pending interrupt that requires user action."""
    console.print()

    # Description
    desc = interrupt.description or "Action required"
    console.print(
        Panel(
            Text(desc, style="bold"),
            title=Text(" Interrupt ", style="bold yellow"),
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
            expand=False,
        )
    )

    # Detail (diff, content, etc.)
    if interrupt.detail:
        detail_text = interrupt.detail
        if len(detail_text) > 2000:
            detail_text = detail_text[:2000] + "\n... (truncated)"
        console.print(
            Panel(
                render_markdown(f"```\n{detail_text}\n```"),
                border_style="dim",
                padding=(0, 1),
                expand=True,
            )
        )

    # Numbered options
    console.print()
    for i, option in enumerate(interrupt.options, 1):
        style = "bold green" if option in ("approve", "accept", "yes") else (
            "bold red" if option in ("reject", "deny", "no") else "bold cyan"
        )
        console.print(Text(f"  [{i}] {option}", style=style))
    console.print()


def render_image(path: str) -> None:
    """Render an image — inline if terminal supports it, otherwise show file path."""
    from deepagent_repl.utils.images import can_render_inline, write_inline_image

    if can_render_inline():
        console.print()
        if write_inline_image(path):
            console.print(Text(f"  {path}", style="dim"))
            return

    # Fallback: show file path in a panel
    console.print(
        Panel(
            Text(path, style="bold"),
            title=Text(" Image ", style="bold blue"),
            title_align="left",
            border_style="blue",
            padding=(0, 1),
            expand=False,
        )
    )


def render_error(message: str) -> None:
    """Render an error message."""
    console.print(Text(f"Error: {message}", style="bold red"))


def render_info(message: str) -> None:
    """Render an informational message."""
    console.print(Text(message, style="dim"))


def _format_args(args: dict, max_total: int = 120) -> str:
    """Format tool arguments as a compact key=value string."""
    if not args:
        return ""
    parts = []
    total = 0
    for key, val in args.items():
        val_str = str(val).replace("\n", " ").strip()
        if len(val_str) > 60:
            val_str = val_str[:57] + "..."
        part = f"{key}={val_str}"
        total += len(part)
        if total > max_total and parts:
            parts.append("...")
            break
        parts.append(part)
    return ", ".join(parts)
