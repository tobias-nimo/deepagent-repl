"""Shared fixtures for the whole suite.

The suite is split into three layers, each with its own `conftest.py`:

- `tests/unit/`  — pure-logic tests; no app boot, no event loop where avoidable.
- `tests/app/`   — boot the real `DeepAgentTUI` through Textual's pilot harness
                   with bootstrap stubbed (no LangGraph server needed).
- `tests/cli/`   — drive the headless `deepagent` runner against a fake client.

Fixtures here are the ones used across more than one layer.
"""

from __future__ import annotations

import pytest

from deepagent_tui.storage import config_store, db


@pytest.fixture()
def cfg_paths(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Point the config store at a tmp dir so the user's real config.toml is
    never read or written. Yields the config file path for convenience."""
    cfg_dir = tmp_path / ".deepagent-tui"
    monkeypatch.setattr(config_store, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", cfg_dir / "config.toml")
    return cfg_dir / "config.toml"


@pytest.fixture()
def db_paths(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Point the thread index at a tmp sqlite file."""
    monkeypatch.setattr(db, "DB_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "threads.db")
    return tmp_path / "threads.db"
