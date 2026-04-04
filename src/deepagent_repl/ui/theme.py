from __future__ import annotations

from rich.color import Color, ColorParseError

from deepagent_repl.config import settings


def _valid_color(name: str) -> bool:
    try:
        Color.parse(name)
        return True
    except ColorParseError:
        return False


# Accent color used throughout the REPL UI
ACCENT_COLOR = settings.deepagent_color if _valid_color(settings.deepagent_color) else "cyan"

SUGGESTED_COLORS = [
    "cyan", "blue", "green", "magenta", "red", "yellow", "white",
    "bright_cyan", "bright_blue", "bright_green", "bright_magenta",
]


def set_accent_color(color: str) -> bool:
    """Set the accent color. Accepts any Rich color name or hex code (#rrggbb).
    Returns True if the color is valid."""
    global ACCENT_COLOR
    if not _valid_color(color):
        return False
    ACCENT_COLOR = color
    return True


def current_accent() -> str:
    return ACCENT_COLOR


# Mapping from Rich color names to prompt_toolkit ansi names
_PTK_ANSI: dict[str, str] = {
    "cyan": "ansicyan",
    "blue": "ansiblue",
    "green": "ansigreen",
    "magenta": "ansimagenta",
    "red": "ansired",
    "yellow": "ansiyellow",
    "white": "ansiwhite",
    "bright_cyan": "ansibrightcyan",
    "bright_blue": "ansibrightblue",
    "bright_green": "ansibrightgreen",
    "bright_magenta": "ansibrightmagenta",
    "bright_red": "ansibrightred",
    "bright_yellow": "ansibrightyellow",
    "bright_white": "ansibrightwhite",
}


def accent_ptk() -> str:
    """Return accent color as a prompt_toolkit fg: style string."""
    color = ACCENT_COLOR
    if color.startswith("#"):
        return f"fg:{color}"
    ptk = _PTK_ANSI.get(color)
    if ptk:
        return f"fg:{ptk}"
    # fallback: try passing as-is (prompt_toolkit accepts some names)
    return f"fg:{color}"
