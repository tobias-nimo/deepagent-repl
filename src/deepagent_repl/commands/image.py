"""The /image command — send an image to the agent."""

from __future__ import annotations

from pathlib import Path

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import render_error, render_image, render_info
from deepagent_repl.utils.images import is_image_path


@command("image", "Send an image to the agent: /image <path> [message]")
async def cmd_image(client, session, args: str) -> None:
    if not args.strip():
        render_error("Usage: /image <path> [optional message]")
        return

    parts = args.strip().split(None, 1)
    image_path = parts[0]
    message = parts[1] if len(parts) > 1 else "Please analyze this image."

    # Expand ~ and resolve
    image_path = str(Path(image_path).expanduser().resolve())

    if not Path(image_path).exists():
        render_error(f"File not found: {image_path}")
        return

    if not is_image_path(image_path):
        render_error(f"Not a recognized image format: {image_path}")
        return

    # Show preview
    render_image(image_path)
    render_info(f"Sending image with message: {message}")

    # Send as multimodal content
    from deepagent_repl.cli import handle_stream
    from deepagent_repl.utils.images import build_multimodal_content

    # Override the content sent to the server with multimodal content
    content = build_multimodal_content(message, [image_path])
    await handle_stream(client, session, content)
