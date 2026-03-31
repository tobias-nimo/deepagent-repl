from __future__ import annotations

import re

from rich.markdown import Markdown

from deepagent_repl.ui.theme import SYNTAX_THEME


def render_markdown(text: str) -> Markdown:
    """Convert a markdown string to a Rich Markdown renderable.

    Pre-processes the text to handle edge cases before Rich rendering.
    """
    processed = _preprocess(text)
    return Markdown(processed, code_theme=SYNTAX_THEME)


def _preprocess(text: str) -> str:
    """Clean up markdown text before rendering.

    - Normalizes line endings
    - Ensures opening fenced code blocks have a language tag (defaults to 'text')
    """
    text = text.replace("\r\n", "\n")

    # Add 'text' language to opening fences that lack one.
    # Track fence state to only modify opening (not closing) fences.
    lines = text.split("\n")
    result = []
    in_fence = False
    for line in lines:
        if re.match(r"^```\S+", line):
            # Opening fence with language — enter code block
            in_fence = True
            result.append(line)
        elif re.match(r"^```\s*$", line):
            if in_fence:
                # Closing fence
                in_fence = False
                result.append(line)
            else:
                # Opening fence without language — add default
                in_fence = True
                result.append("```text")
        else:
            result.append(line)

    return "\n".join(result)
