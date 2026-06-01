# Contributing

Thanks for your interest in deepagent-tui. This is the entry point; the details
live in [`CLAUDE.md`](CLAUDE.md) (architecture and conventions) and the
[`docs/`](docs/) tree. This file just gets you set up and points the way.

## Dev setup

```bash
uv sync --extra dev          # install with dev extras (pinned via uv.lock)
uv run deepagent             # launch the TUI
```

The TUI is a **client** — it needs a LangGraph Deep Agent server reachable at
`LANGGRAPH_URL` (default `http://localhost:2024`). Start one in another terminal
with `uv run langgraph dev --no-browser` from your agent project. Env vars and
per-directory `.env` loading are documented in
[`docs/configuration.md`](docs/configuration.md).

## Before you push

```bash
uv run ruff check            # lint (line-length 100, py312, rules E/F/I)
uv run pytest                # full suite — no server needed, runs in ~2s
```

Both must be green. New behaviour should come with a test:

- **Pure logic** → a unit test under `tests/unit/` (no app boot).
- **App wiring** → a test under `tests/app/` using Textual's pilot harness.

CI also runs `pytest --cov`, which enforces a coverage gate scoped to the
pure-logic layer — so untested new logic there will fail the build. See
[`docs/testing.md`](docs/testing.md) for the suite layout, the fixtures, and what
is intentionally out of scope.

## Where things live

- [`docs/architecture.md`](docs/architecture.md) — the full map of how the parts
  fit together.
- [`CLAUDE.md`](CLAUDE.md) — a condensed architecture summary plus the recipes
  for the common extension points: adding a **tool widget**
  (`ui/tool_widgets.py`) or a **slash command** (`commands/`).
- The rest of [`docs/`](docs/) covers individual features (HITL, threads,
  themes, skills, the headless CLI, …).

## Pull requests

- Keep PRs focused on one change; a small, reviewable diff lands faster.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  — match the existing history (`feat(tui): …`, `fix(tui): …`, `docs: …`,
  `test: …`).
- Update the relevant `docs/` page or `CLAUDE.md` when you change behaviour they
  describe.

## Reporting bugs

Open an issue with:

- What you expected vs. what happened (and the terminal output / traceback).
- Your setup: OS, how you launched the server, and the relevant env vars
  (`LANGGRAPH_URL`, `GRAPH_ID`). [`docs/troubleshooting.md`](docs/troubleshooting.md)
  covers the common cases first.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
