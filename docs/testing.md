# Testing

The suite is a small test pyramid: a broad base of fast pure-logic unit tests, a
thin layer of app-boot integration tests, and a handful of CLI tests. It runs in
~3s with no LangGraph server, and a coverage gate keeps the logic layer honest.

```
tests/
  conftest.py            # shared fixtures: cfg_paths, db_paths (tmp-path redirected)
  unit/                  # pure logic — no app boot, the bulk of the suite
    test_handlers_tools.py      # raw payload → FormattedToolCall/Result
    test_handlers_interrupt.py  # HITL interrupt parsing + build_resume_value
    test_handlers_stream.py     # streaming text-delta + updates parsing
    test_tool_widgets.py        # the inline tool-call/result renderers
    test_utils.py               # tokens, cost, images, session.add_usage
    test_commands.py            # registry/dispatch, renderer sink, transcript builders
    test_storage.py             # per-agent config layering + thread-index scoping
  app/                   # boots the real DeepAgentTUI through Textual's pilot
    conftest.py                 # autouse stub of bootstrap.connect/discover
    test_boot_layout.py         # layout mounts; connect-failure degrades
    test_autocomplete.py        # /, @, and email autocomplete behaviour
    test_input_history.py       # up/down recall, draft restore, file-ref rewrite
    test_shell.py               # ! prefix gating, execution, paste regression
    test_settings.py            # settings tabs + per-agent config round-trip
  cli/                   # headless `deepagent` runner against a fake client
    conftest.py                 # FakeClient + stub fixture
    test_runner.py
```

## Running

```bash
uv run pytest                       # fast, no coverage overhead, no gate
uv run pytest -k slash              # filter by keyword
uv run pytest tests/unit            # one layer
uv run pytest --cov --cov-report=term-missing   # with the coverage gate (what CI runs)
uv run ruff check                   # lint
```

`pytest-asyncio` runs in `auto` mode, so `async def test_*` works without
decorators.

## The two patterns that keep it reliable

**Stubbed bootstrap (app layer).** The TUI's `on_mount` calls
`bootstrap.connect` and `bootstrap.discover_and_register_skills`, both of which
touch the network. The autouse `stub_bootstrap` fixture in `tests/app/conftest.py`
replaces them with fakes that fill `session.assistant_id` / `graph_id` /
`thread_id` and return success, so the whole app mounts without a server. The CLI
layer has the analogous `stub` fixture wrapping a `FakeClient`.

**Drive helpers directly, not keystrokes.** Where a test targets a piece of
logic (autocomplete refresh, history recall, settings cycling), it calls the
method directly (`app._refresh_autocomplete("/")`) instead of simulating a key.
`TextArea.Changed` lands a tick later and pilot key dispatch has been flaky for
unfocused-edge cases across Textual versions, so direct calls are deterministic.
When asserting on rendered content, query the widget and read its
content/attributes (`sb.content`, `ac.option_count`, `"-hidden" in ac.classes`)
rather than scraping the screen buffer.

## Coverage gate

Coverage is **opt-in**: a plain `uv run pytest` never fails on a threshold, so
filtered local runs stay fast. CI runs `uv run pytest --cov`, which enforces the
gate configured in `pyproject.toml` (`[tool.coverage.report] fail_under`).

The gate is scoped to the **pure-logic layer** — `handlers/`, `utils/`,
`storage/`, `session.py`, `ui/tool_widgets.py`, and `commands/__init__.py` — the
parts that are cheap and worthwhile to keep near-fully covered. UI glue in
`tui/` and the IO-coupled command bodies (clipboard, `$EDITOR`, network fetch)
are exercised by the app/cli tests but deliberately left out of the number;
chasing them to a high percentage is churn, not safety. Add new pure logic with
a unit test and the gate stays green on its own.

## Adding a test

Pure logic → `tests/unit/`, no app boot:

```python
from deepagent_tui.handlers.tools import format_tool_call

def test_parses_json_string_args():
    tc = format_tool_call({"name": "edit", "args": '{"file_path": "x.py"}'})
    assert tc.args == {"file_path": "x.py"}
```

App wiring → `tests/app/`, inside Textual's pilot harness:

```python
async def test_my_thing() -> None:
    app = DeepAgentTUI()
    async with app.run_test() as pilot:
        await pilot.pause()   # let mounts and post-mount messages settle
        ...
```

`tool_widgets` renderers return rich `Text` / `Group` trees; flatten them with
the `_plain` helper in `test_tool_widgets.py` and assert on the visible text and
markers. To check mode-dependent output, flip `tw.set_widget_mode(...)` — the
autouse `reset_mode` fixture restores the default afterward.

## What's intentionally not tested

- **Live streaming against a real server** — the stream→render→approve loop is
  covered by unit-testing its pure pieces (`handlers/stream`, `handlers/tools`,
  `handlers/interrupt`, `tool_widgets`) plus the CLI runner driving a fake
  stream. A full fake of the SDK's async protocol would be brittle.
- **HITL approval end-to-end** — `build_resume_value` and the interrupt parser
  are unit-tested; gluing them through a live stream is left to manual checks.
- **Clipboard, terminal image protocols, `$EDITOR` round-trips** — the escape
  builders and detection are unit-tested via env vars; the actual subprocess /
  terminal IO is environment-dependent and out of scope for CI.
- **Theme rendering** — visual; eyeballing is the test.
