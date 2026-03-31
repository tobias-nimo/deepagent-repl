from __future__ import annotations

import argparse
import asyncio
import json
import sys

import deepagent_repl.commands.approve  # noqa: F401
import deepagent_repl.commands.builtins  # noqa: F401
import deepagent_repl.commands.compress  # noqa: F401
import deepagent_repl.commands.export  # noqa: F401
import deepagent_repl.commands.graph  # noqa: F401
import deepagent_repl.commands.image  # noqa: F401
import deepagent_repl.commands.new  # noqa: F401
import deepagent_repl.commands.replay  # noqa: F401
import deepagent_repl.commands.resume  # noqa: F401
import deepagent_repl.commands.skills  # noqa: F401
import deepagent_repl.commands.theme  # noqa: F401
import deepagent_repl.commands.threads  # noqa: F401
from deepagent_repl.client import AgentClient
from deepagent_repl.commands import clear_dynamic, is_command, register_skill
from deepagent_repl.commands import dispatch as dispatch_command
from deepagent_repl.config import settings
from deepagent_repl.handlers.interrupt import (
    InterruptInfo,
    build_resume_value,
    extract_interrupts,
    open_in_editor,
)
from deepagent_repl.handlers.stream import (
    StreamState,
    process_messages_event,
    process_updates_event,
)
from deepagent_repl.handlers.tools import format_tool_call, format_tool_result
from deepagent_repl.session import Session
from deepagent_repl.storage.db import upsert_thread
from deepagent_repl.ui.prompt import create_prompt_session, read_input
from deepagent_repl.ui.renderer import (
    StreamingRenderer,
    console,
    render_assistant_text,
    render_error,
    render_info,
    render_interrupt,
    render_tool_call,
    render_tool_result,
)
from deepagent_repl.ui.toolbar import create_toolbar


async def connect(client: AgentClient, session: Session) -> bool:
    """Connect to the server, discover assistant, create thread. Returns True on success."""
    try:
        assistants = await client.discover_assistants()
    except Exception as e:
        render_error(f"Cannot connect to {settings.langgraph_url}: {e}")
        return False

    if not assistants:
        render_error("No assistants found on server.")
        return False

    if settings.graph_id:
        matches = [a for a in assistants if a["graph_id"] == settings.graph_id]
        if not matches:
            available = ", ".join(a["graph_id"] for a in assistants)
            render_error(f"Graph '{settings.graph_id}' not found. Available: {available}")
            return False
        assistant = matches[0]
    elif len(assistants) == 1:
        assistant = assistants[0]
    else:
        render_info("Multiple assistants found:")
        for i, a in enumerate(assistants, 1):
            render_info(f"  [{i}] {a['graph_id']} (id: {a['assistant_id'][:8]}...)")
        try:
            choice = int(input("Select assistant number: ")) - 1
            assistant = assistants[choice]
        except (ValueError, IndexError):
            render_error("Invalid selection.")
            return False

    session.assistant_id = assistant["assistant_id"]
    session.graph_id = assistant["graph_id"]

    if settings.thread_id:
        session.thread_id = settings.thread_id
    else:
        session.thread_id = await client.create_thread()

    # Record thread in local index
    await upsert_thread(session.thread_id, session.graph_id or "")

    return True


async def discover_and_register_skills(client: AgentClient, session: Session) -> None:
    """Discover skills from the connected server and register as dynamic slash commands."""
    clear_dynamic()

    if not session.assistant_id:
        return

    try:
        skills = await client.discover_skills(session.assistant_id)
    except Exception:
        return

    for skill in skills:
        name = skill.get("name", "")
        desc = skill.get("description", "")
        if not name:
            continue

        # Create a handler that sends a message invoking the skill
        def _make_handler(skill_name: str):
            async def handler(c: AgentClient, s: Session, args: str) -> None:
                prompt = f"Use the {skill_name} skill"
                if args:
                    prompt += f" to: {args}"
                await handle_stream(c, s, prompt)

            return handler

        register_skill(name, desc, _make_handler(name))

    if skills:
        render_info(f"Discovered {len(skills)} skill(s). Type /skills to list.")


# Token threshold for auto-compression warning (default ~80% of 200k context)
_COMPRESS_WARN_TOKENS = 160_000
_compress_warned = False


def _flush_usage(state: StreamState, session: Session) -> None:
    """Transfer accumulated token usage from a stream state into the session."""
    if state.total_input_tokens or state.total_output_tokens:
        session.add_usage(state.total_input_tokens, state.total_output_tokens)
    if state.model and not session.model:
        session.model = state.model


async def _consume_stream(stream, state: StreamState, renderer: StreamingRenderer) -> None:
    """Consume a stream of events, updating the renderer and state."""
    async for chunk in stream:
        event_type = chunk.event
        data = chunk.data

        if event_type == "messages/partial":
            text_fragment = process_messages_event(data, state)
            if text_fragment:
                renderer.update(text_fragment)

        elif event_type == "updates" and isinstance(data, dict):
            # Finish live display (transient — vanishes on stop)
            accumulated = renderer.finish()
            if accumulated.strip():
                render_assistant_text(accumulated)
                state.text_buffer = ""

            messages = process_updates_event(data, state)
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                msg_type = msg.get("type")

                if msg_type == "ai":
                    # Render text content if it wasn't already shown via streaming
                    from deepagent_repl.handlers.stream import extract_text_content

                    ai_text = extract_text_content(msg.get("content", ""))
                    if ai_text.strip() and ai_text.strip() != accumulated.strip():
                        render_assistant_text(ai_text)

                    for tc in msg.get("tool_calls", []):
                        render_tool_call(format_tool_call(tc))

                elif msg_type == "tool":
                    render_tool_result(format_tool_result(msg))

            # Restart live display for continued streaming
            renderer.start()


async def _prompt_interrupt(
    interrupt: InterruptInfo, prompt_session,
) -> tuple[str, str | None]:
    """Display an interrupt and get the user's choice.

    Returns (chosen_option, edited_content_or_None).
    """
    render_interrupt(interrupt)

    while True:
        try:
            raw = await read_input(prompt_session, prompt_text="choice> ")
        except KeyboardInterrupt:
            # Treat Ctrl+C as reject
            return "reject", None

        if raw is None:
            return "reject", None

        raw = raw.strip()
        if not raw:
            continue

        # Accept number or option name
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(interrupt.options):
                chosen = interrupt.options[idx]
            else:
                render_error(f"Choose 1-{len(interrupt.options)}")
                continue
        except ValueError:
            # Try matching option name directly
            lower = raw.lower()
            matched = [o for o in interrupt.options if o.lower().startswith(lower)]
            if len(matched) == 1:
                chosen = matched[0]
            else:
                render_error(f"Choose 1-{len(interrupt.options)} or type option name")
                continue

        # Handle "edit" option — open in $EDITOR
        edited_content = None
        if chosen.lower() in ("edit", "modify"):
            content = interrupt.detail or ""
            edited_content = open_in_editor(content)
            if edited_content is None:
                render_info("Edit cancelled.")
                continue

        return chosen, edited_content


def _check_approval_rules(interrupt: InterruptInfo) -> str | None:
    """Check if approval rules auto-resolve this interrupt.

    Returns "approve"/"reject" if a rule matches, or None to prompt the user.
    """
    from deepagent_repl.storage.rules import match_rule

    # Extract tool name from interrupt value
    tool_name = None
    if isinstance(interrupt.value, dict):
        tool_name = (
            interrupt.value.get("tool_name")
            or interrupt.value.get("action")
            or interrupt.value.get("name")
            or interrupt.value.get("type")
        )

    if not tool_name or not isinstance(tool_name, str):
        return None

    action = match_rule(tool_name)
    if action == "allow":
        return "approve"
    elif action == "deny":
        return "reject"
    # "ask" or None → prompt the user
    return None


async def handle_stream(
    client: AgentClient, session: Session, user_input: str | list,
) -> None:
    """Send a message and process the streamed response, handling HITL interrupts.

    user_input can be a plain string or a multimodal content list (for images).
    """
    session.status = "streaming"
    session.messages.append({"role": "user", "content": user_input})
    state = StreamState()
    renderer = StreamingRenderer()
    renderer.start()
    prompt_session = session.prompt_session

    try:
        # Initial message
        stream = client.stream_message(session.thread_id, session.assistant_id, user_input)
        await _consume_stream(stream, state, renderer)
        _flush_usage(state, session)

        # Finalize buffered text
        final_text = renderer.finish()
        if final_text.strip():
            render_assistant_text(final_text)

        # Check for interrupts and handle resume loop
        while True:
            try:
                thread_state = await client.get_thread_state(session.thread_id)
            except Exception:
                break

            interrupts = extract_interrupts(thread_state)
            if not interrupts:
                break

            # Handle each interrupt (typically just one)
            for interrupt in interrupts:
                session.status = "interrupted"

                # Check approval rules before prompting user
                auto_choice = _check_approval_rules(interrupt)
                if auto_choice is not None:
                    chosen, edited = auto_choice, None
                    render_info(f"Auto-{chosen} by approval rule.")
                else:
                    chosen, edited = await _prompt_interrupt(interrupt, prompt_session)

                resume_value = build_resume_value(interrupt, chosen, edited)
                render_info(f"Resuming with: {chosen}")

                # Resume and stream continuation
                session.status = "streaming"
                state = StreamState()
                renderer = StreamingRenderer()
                renderer.start()

                resume_stream = client.resume(
                    session.thread_id, session.assistant_id, resume_value
                )
                await _consume_stream(resume_stream, state, renderer)
                _flush_usage(state, session)

                final_text = renderer.finish()
                if final_text.strip():
                    render_assistant_text(final_text)

    except Exception as e:
        renderer.finish()
        render_error(f"Stream error: {e}")
    finally:
        session.status = "idle"
        # Update thread metadata in local index
        try:
            if isinstance(user_input, str):
                preview = user_input[:100]
            else:
                # Multimodal content — extract text part for preview
                text_parts = [
                    c.get("text", "") for c in user_input
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                preview = (" ".join(text_parts))[:100] if text_parts else "[image]"
            await upsert_thread(
                session.thread_id,
                session.graph_id or "",
                last_message=preview,
                message_count=len(session.messages) + 1,
            )
        except Exception:
            pass

        # Auto-compression warning
        global _compress_warned
        total = session.input_tokens + session.output_tokens
        if total >= _COMPRESS_WARN_TOKENS and not _compress_warned:
            _compress_warned = True
            from deepagent_repl.utils.cost import format_tokens

            render_info(
                f"Warning: {format_tokens(total)} tokens used. "
                f"Consider running /compress to reduce context size."
            )


async def run() -> None:
    """Main async entry point."""
    client = AgentClient(url=settings.langgraph_url, api_key=settings.langsmith_api_key)
    session = Session()
    toolbar = create_toolbar(session)
    prompt_session = create_prompt_session(bottom_toolbar=toolbar)
    session.prompt_session = prompt_session

    console.print()
    render_info("deepagent-repl v0.1.0")
    render_info(f"Connecting to {settings.langgraph_url}...")

    if not await connect(client, session):
        sys.exit(1)

    render_info(f"Connected to graph: {session.graph_id}")
    render_info(f"Thread: {session.thread_id}")

    # Discover skills from the server (non-blocking, best-effort)
    await discover_and_register_skills(client, session)

    render_info("Type your message. Ctrl+D to exit.\n")

    while True:
        try:
            user_input = await read_input(prompt_session)
        except KeyboardInterrupt:
            continue

        if user_input is None:
            render_info("\nGoodbye!")
            break

        text = user_input.strip()
        if not text:
            continue

        # Dispatch slash commands before sending to server
        if is_command(text):
            await dispatch_command(client, session, text)
            continue

        # Auto-detect image paths in text and convert to multimodal
        from deepagent_repl.utils.images import build_multimodal_content, detect_image_paths

        image_paths = detect_image_paths(text)
        if image_paths:
            content = build_multimodal_content(text, image_paths)
            render_info(f"Detected {len(image_paths)} image(s), sending as multimodal.")
            await handle_stream(client, session, content)
        else:
            await handle_stream(client, session, text)


async def run_oneshot(message: str, *, output_json: bool = False, no_stream: bool = False) -> int:
    """One-shot mode: send a single message, print response, exit.

    Returns exit code: 0 success, 1 error, 2 interrupt.
    """
    client = AgentClient(url=settings.langgraph_url, api_key=settings.langsmith_api_key)
    session = Session()

    if not await connect(client, session):
        return 1

    if output_json:
        # Non-streaming: send and collect full response
        try:
            result = await client.send_message(
                session.thread_id, session.assistant_id, message
            )
            messages = result.get("messages", [])
            # Find the last AI message
            for msg in reversed(messages):
                if msg.get("type") == "ai" or msg.get("role") == "assistant":
                    print(json.dumps(msg, ensure_ascii=False, indent=2))
                    return 0
            print(json.dumps({"error": "No response"}, indent=2))
            return 1
        except Exception as e:
            print(json.dumps({"error": str(e)}, indent=2))
            return 1

    if no_stream:
        # Non-streaming plain text output
        try:
            result = await client.send_message(
                session.thread_id, session.assistant_id, message
            )
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if msg.get("type") == "ai" or msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            c.get("text", "") for c in content if isinstance(c, dict)
                        )
                    print(content)
                    return 0
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Streaming mode (default for one-shot)
    try:
        await handle_stream(client, session, message)
        return 0
    except KeyboardInterrupt:
        return 2
    except Exception as e:
        render_error(str(e))
        return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="deepagent-repl",
        description="Terminal REPL for any LangChain Deep Agent server",
    )
    parser.add_argument("message", nargs="?", default=None, help="One-shot message to send")
    parser.add_argument("--json", action="store_true", dest="output_json", help="Output raw JSON")
    parser.add_argument(
        "--no-stream", action="store_true", help="Disable streaming (clean output)"
    )
    return parser.parse_args()


def main() -> None:
    """Synchronous entry point for the CLI."""
    args = _parse_args()

    # Check for piped stdin
    message = args.message
    if message is None and not sys.stdin.isatty():
        message = sys.stdin.read().strip()

    try:
        if message:
            code = asyncio.run(
                run_oneshot(message, output_json=args.output_json, no_stream=args.no_stream)
            )
            sys.exit(code)
        else:
            asyncio.run(run())
    except KeyboardInterrupt:
        pass
