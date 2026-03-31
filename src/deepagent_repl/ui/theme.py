from __future__ import annotations

import os

# Available themes: name -> (syntax_theme, is_dark)
THEMES: dict[str, tuple[str, bool]] = {
    "dark": ("monokai", True),
    "light": ("default", False),
    "monokai": ("monokai", True),
    "dracula": ("dracula", True),
    "github-dark": ("github-dark", True),
    "one-dark": ("one-dark", True),
    "solarized-dark": ("solarized-dark", True),
    "solarized-light": ("solarized-light", False),
}


def detect_dark_mode() -> bool:
    """Detect whether the terminal is using a dark background.

    Checks several environment heuristics. Defaults to dark if uncertain.
    """
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        parts = colorfgbg.split(";")
        try:
            bg = int(parts[-1])
            return bg < 7 or bg == 8
        except ValueError:
            pass

    return True


def get_syntax_theme(dark: bool = True) -> str:
    """Return a Pygments syntax theme name appropriate for the background."""
    return "monokai" if dark else "default"


# Mutable module-level state
IS_DARK_MODE = detect_dark_mode()
SYNTAX_THEME = get_syntax_theme(IS_DARK_MODE)
_current_theme = "dark" if IS_DARK_MODE else "light"


def set_theme(name: str) -> bool:
    """Switch to a named theme. Returns True if successful."""
    global IS_DARK_MODE, SYNTAX_THEME, _current_theme

    if name not in THEMES:
        return False

    syntax, dark = THEMES[name]
    SYNTAX_THEME = syntax
    IS_DARK_MODE = dark
    _current_theme = name
    return True


def current_theme() -> str:
    return _current_theme


def available_themes() -> list[str]:
    return sorted(THEMES.keys())
