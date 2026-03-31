# deepagent-repl: Terminal REPL for any LangChain Deep Agent Server

## Context

LangChain Deep Agents deployed via `langgraph dev` (or LangGraph Cloud) expose a standard LangGraph API on `localhost:2024`. There is no dedicated terminal UI for interacting with them — users rely on LangGraph Studio or web UIs. The goal is to build a **generic, server-agnostic** Python CLI (`deepagent-repl`) that connects to **any** LangGraph server running a Deep Agent and provides a rich, Claude Code-like terminal experience.

This is a **separate project** (its own repo, its own `pyproject.toml`) that acts purely as a client. It does NOT embed agent logic — it talks to the server over the LangGraph SDK. It auto-discovers available graphs, tools, and skills from the connected server, so it works with cowork, langrepl-style agents, or any custom Deep Agent deployment.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Input | **Prompt Toolkit** | Multi-line editing, key bindings, history, tab completion — same as langrepl |
| Output | **Rich** | Markdown rendering, syntax highlighting, panels, spinners, tables |
| Server comms | **`langgraph-sdk`** | Official async Python client for LangGraph servers |
| Async | **`asyncio`** | Streaming requires async; Prompt Toolkit has native async support |
| Config | **Pydantic Settings** | `.env` + CLI flags, consistent with cowork itself |
| Persistence | **SQLite** (via `aiosqlite`) | Thread history, token/cost tracking |
| Packaging | **uv** | Matches cowork ecosystem |

---

## Phases

### Phase 0 — Project Scaffold
> Get the repo structure, packaging, and dev tooling in place.

- Init git repo `deepagent-repl/`
- `pyproject.toml` with dependencies: `langgraph-sdk`, `prompt-toolkit`, `rich`, `pydantic-settings`, `aiosqlite`
- Directory layout:
  ```
  deepagent-repl/
  ├── pyproject.toml
  ├── README.md
  ├── .env.example          # LANGGRAPH_URL, LANGSMITH_API_KEY (optional)
  ├── src/
  │   └── deepagent_repl/
  │       ├── __init__.py
  │       ├── __main__.py    # entry point (python -m deepagent_repl)
  │       ├── cli.py         # arg parsing, startup
  │       ├── config.py      # Pydantic Settings
  │       ├── client.py      # LangGraph SDK wrapper
  │       ├── session.py     # Session state (thread, tokens, cost)
  │       ├── ui/
  │       │   ├── __init__.py
  │       │   ├── prompt.py      # Prompt Toolkit input
  │       │   ├── renderer.py    # Rich output rendering
  │       │   ├── markdown.py    # Markdown processing
  │       │   ├── toolbar.py     # Status bar
  │       │   └── theme.py       # Theme detection + colors
  │       ├── commands/
  │       │   ├── __init__.py    # Command registry + dispatcher
  │       │   ├── help.py
  │       │   └── ...            # One file per slash command
  │       ├── handlers/
  │       │   ├── __init__.py
  │       │   ├── stream.py      # Stream event processing
  │       │   ├── interrupt.py   # HITL interrupt handling
  │       │   └── tools.py       # Tool call formatting
  │       ├── storage/
  │       │   ├── __init__.py
  │       │   └── db.py          # SQLite thread/session persistence
  │       └── utils/
  │           ├── __init__.py
  │           ├── tokens.py      # Token counting
  │           └── cost.py        # Cost calculation
  ├── tests/
  │   └── ...
  └── .env.example
  ```
- Ruff config (match cowork: line-length 100)
- `uv run deepagent-repl` as the entry command (via `[project.scripts]`)

---

### Phase 1 — Basic Chat Loop ✅
> Minimum viable REPL: send a message, see the full response.

**Files:** `cli.py`, `client.py`, `config.py`, `session.py`, `ui/prompt.py`, `ui/renderer.py`

1. **Config** (`config.py`):
   - `langgraph_url` (default `http://localhost:2024`)
   - `graph_id` (default `None` — auto-discover from server via `client.graphs.list()`, prompt user if multiple)
   - `thread_id` (auto-generated UUID, or passed via CLI)
   - `langsmith_api_key` (optional, for authenticated LangGraph Cloud connections)

2. **Client wrapper** (`client.py`):
   - Initialize `langgraph_sdk.get_client(url=...)`
   - `discover_graph()` — List available graphs, auto-select if one, prompt if multiple
   - `send_message(thread_id, content) -> async generator of events`
   - `get_thread_state(thread_id)`
   - `create_thread() -> thread_id`

3. **Input** (`ui/prompt.py`):
   - Prompt Toolkit `PromptSession` with basic prompt (`> `)
   - Single-line input (multi-line comes later)
   - Ctrl+C = cancel current, Ctrl+D = exit

4. **Output** (`ui/renderer.py`):
   - Rich `Console` for output
   - Print assistant text as plain text (markdown comes later)
   - Print `[tool_name]` placeholder when tools are called

5. **Main loop** (`cli.py`):
   - Create thread on start
   - Loop: read input -> send to server -> print response -> repeat
   - Use `client.runs.stream()` with `stream_mode="updates"` to get node-level updates
   - Extract final `AIMessage` content from the `model` node updates

**Exit criteria:** Can send messages and receive complete responses from any Deep Agent server.

---

### Phase 2 — Streaming Output
> Show tokens as they arrive, not after the full response.

**Files:** `handlers/stream.py`, `ui/renderer.py`

1. **Stream handler** (`handlers/stream.py`):
   - Switch to `stream_mode="messages"` to get token-level chunks
   - Process `AIMessageChunk` objects — accumulate and display incrementally
   - Detect end-of-message (chunk with `finish_reason`)
   - Handle multiple messages per run (tool loops produce several AI messages)

2. **Live rendering** (`ui/renderer.py`):
   - Use Rich `Live` context for in-place updates during streaming
   - Buffer incoming text, re-render markdown periodically (every ~100ms or N tokens)
   - Show spinner while waiting for first token

**Exit criteria:** Tokens appear in real-time as the agent thinks.

---

### Phase 3 — Markdown & Code Rendering
> Make output look polished — syntax-highlighted code, formatted markdown.

**Files:** `ui/markdown.py`, `ui/renderer.py`, `ui/theme.py`

1. **Theme detection** (`ui/theme.py`):
   - Detect terminal dark/light mode (query `$COLORFGBG` or similar heuristics)
   - Define color palette for both modes
   - Rich theme object for consistent styling

2. **Markdown processor** (`ui/markdown.py`):
   - Pre-process markdown before Rich rendering (protect HTML blocks, fix edge cases)
   - Rich `Markdown` object for final rendering

3. **Renderer updates** (`ui/renderer.py`):
   - Render final messages as Rich Markdown
   - Syntax-highlighted code blocks (Rich handles this natively)
   - Proper heading, list, table, and blockquote rendering

**Exit criteria:** Code blocks have syntax highlighting; markdown renders with proper formatting.

---

### Phase 4 — Tool Call Visualization
> Show what the agent is doing when it calls tools.

**Files:** `handlers/tools.py`, `ui/renderer.py`

1. **Tool call formatting** (`handlers/tools.py`):
   - Parse `AIMessage.tool_calls` from stream events
   - Format: tool name, key arguments (truncated if long)
   - Distinguish between main agent tools and subagent delegation (`task` tool)
   - For `task` tool calls: show subagent name and input summary

2. **Renderer** (`ui/renderer.py`):
   - Collapsible tool call display (show name + status inline, expand on request)
   - Spinner while tool executes
   - Show tool result summary (truncated) when complete
   - Color-coded: success (green), error (red)
   - Nested display for subagent tool chains

3. **Stream handler updates** (`handlers/stream.py`):
   - Detect `tools` node updates to show tool execution progress
   - Map tool_call_id to tool name for result attribution

**Exit criteria:** When the agent calls tools, the user sees which tool ran, its arguments, and the result.

---

### Phase 5 — Human-in-the-Loop (HITL) Interrupts
> Handle the Deep Agent's HITL system — tools like `edit_file` pause for approval.

**Files:** `handlers/interrupt.py`, `client.py`

1. **Interrupt detection** (`handlers/interrupt.py`):
   - After streaming completes, check thread state for pending interrupts via `client.threads.get_state(thread_id)`
   - State will have `tasks` with `interrupts` containing the interrupt value
   - Extract options (e.g., `["approve", "edit", "reject"]`)

2. **Approval UI** (`handlers/interrupt.py`):
   - Display the pending tool call details (file being edited, the diff)
   - Show numbered options: `[1] approve  [2] edit  [3] reject`
   - Accept input
   - For "edit" option: open `$EDITOR` with the proposed content

3. **Resume** (`client.py`):
   - Send `Command(resume=value)` via `client.runs.stream(... command=...)` to resume the graph
   - Continue streaming from the resumed point

**Exit criteria:** HITL-enabled tools pause the REPL, show details, and let the user approve/edit/reject.

---

### Phase 6 — Multi-line Input & History
> Better input experience.

**Files:** `ui/prompt.py`

1. **Multi-line input**:
   - Ctrl+J or Shift+Enter to insert newlines
   - Enter submits (configurable)
   - Visual continuation indicator for multi-line

2. **History**:
   - Prompt Toolkit `FileHistory` backed by `~/.deepagent-repl/history`
   - Up/Down arrow to cycle through past inputs
   - Ctrl+R for reverse search

3. **Tab completion**:
   - Complete slash commands (`/help`, `/resume`, etc.)
   - Complete file paths when relevant

**Exit criteria:** Can write multi-line prompts; history persists across sessions.

---

### Phase 7 — Thread Management
> Resume past conversations, start new ones.

**Files:** `commands/resume.py`, `commands/new.py`, `commands/threads.py`, `storage/db.py`

1. **Local thread index** (`storage/db.py`):
   - SQLite table: `threads(id, created_at, last_message, message_count, total_tokens, total_cost)`
   - Update on every message exchange
   - Query recent threads for `/resume` display

2. **Slash commands**:
   - `/new` — Start a fresh thread
   - `/resume` — Interactive thread picker (arrow keys, shows last message preview, timestamp)
   - `/threads` — List all saved threads

3. **Thread state sync**:
   - On resume, fetch full state from server via `client.threads.get_state()`
   - Display conversation history summary

**Exit criteria:** Can switch between conversations; thread list persists across sessions.

---

### Phase 8 — Status Bar & Session Info
> Persistent bottom bar with context.

**Files:** `ui/toolbar.py`, `session.py`

1. **Status bar** (`ui/toolbar.py`):
   - Prompt Toolkit `bottom_toolbar` callback
   - Left: graph ID, thread ID (truncated)
   - Center: agent status (idle / streaming / waiting for approval)
   - Right: token count, estimated cost, model name

2. **Session state** (`session.py`):
   - Track: thread_id, total input/output tokens, cost, current agent status
   - Update from stream metadata (usage info in `AIMessage.usage_metadata`)
   - Persist to SQLite per thread

3. **Token counting** (`utils/tokens.py`):
   - Extract from `usage_metadata` in streamed messages
   - Fallback: estimate via `tiktoken` if metadata unavailable

4. **Cost calculation** (`utils/cost.py`):
   - Model-specific rates (Claude Haiku 4.5 pricing)
   - Running total per session

**Exit criteria:** Bottom bar shows live info; cost tracks across messages.

---

### Phase 9 — Slash Command System
> Extensible command framework with built-in + dynamic server-discovered commands.

**Files:** `commands/__init__.py`, `commands/*.py`, `client.py`

1. **Command registry** (`commands/__init__.py`):
   - Two-tier registry: **built-in** commands (hardcoded) + **dynamic** commands (discovered from server)
   - Dispatcher: if input starts with `/`, check built-in first, then dynamic, then show "unknown" help
   - Commands are async handler functions

2. **Built-in commands**:
   - `/help` — List all commands (both built-in and dynamic) with descriptions
   - `/new` — New thread (Phase 7)
   - `/resume` — Thread picker (Phase 7)
   - `/threads` — List threads (Phase 7)
   - `/clear` — Clear terminal screen
   - `/exit` — Quit
   - `/status` — Show server connection info, current thread, graph details, available tools

3. **Dynamic skill commands** (server-discovered):
   - On connect, fetch graph metadata and tool list from server
   - If the connected Deep Agent has a skills system (SkillsMiddleware), discover available skills
   - Register each skill as a slash command: `/skill-name` sends a message like "Use the skill-name skill to: {args}"
   - `/skills` — List all available skills from the connected agent with descriptions
   - Skills are agent-specific — reconnecting to a different server refreshes the list

4. **Command completion**:
   - Tab-complete all slash commands (built-in + dynamic) in prompt
   - Dynamic completions refresh when server connection changes

**Exit criteria:** Command system is extensible; built-in commands work; skills from the connected agent appear as slash commands.

---

### Phase 10 — Conversation Compression
> Handle long conversations that approach context limits.

**Files:** `commands/compress.py`, `client.py`

1. **Compression command** (`commands/compress.py`):
   - `/compress` — Summarize conversation history to reduce tokens
   - Show before/after token counts
   - Ask for confirmation before compressing

2. **Implementation**:
   - Fetch full thread state
   - Send a compression request to the LangGraph server (create a new thread with summarized messages)
   - Or: client-side compression using a local LLM call to summarize
   - Switch session to new compressed thread

3. **Auto-compression**:
   - Warn when approaching context window limits (based on token tracking)
   - Suggest `/compress` when threshold exceeded

**Exit criteria:** Long conversations can be compressed; token count drops significantly.

---

### Phase 11 — Image Support
> View images the agent produces and send images as input.

**Files:** `ui/renderer.py`, `ui/prompt.py`, `handlers/tools.py`

1. **Image output**:
   - Detect image references in tool results (e.g., from `to_md` OCR, `view_image`)
   - For terminals with image support (iTerm2, Kitty): render inline via escape sequences
   - Fallback: show file path with Rich panel

2. **Image input**:
   - Accept file paths in messages
   - Detect image file extensions, base64-encode, send as multimodal content
   - `/image <path>` command as explicit alternative

**Exit criteria:** Images from OCR/screenshots display in terminal; can send images to agent.

---

### Phase 12 — Replay & Branch
> Navigate conversation history and branch from earlier points.

**Files:** `commands/replay.py`, `client.py`

1. **Replay UI** (`commands/replay.py`):
   - `/replay` — Show list of user messages in thread
   - Arrow key selection
   - Selecting a message forks the conversation from that point

2. **Implementation**:
   - Fetch thread history via `client.threads.get_history(thread_id)`
   - Get state at selected checkpoint
   - Create new thread from that state
   - Switch session to forked thread

**Exit criteria:** Can branch a conversation from any earlier user message.

---

### Phase 13 — Approval Rules
> Configurable auto-approve/deny/ask for tool calls (beyond HITL).

**Files:** `commands/approve.py`, `handlers/interrupt.py`, `storage/db.py`

1. **Rule system**:
   - Three lists: `always_allow`, `always_ask`, `always_deny`
   - Rules match tool names (with optional arg patterns)
   - Persisted in SQLite or JSON config file

2. **Interactive manager** (`commands/approve.py`):
   - `/approve` — Opens interactive rule editor
   - Tab between lists, arrow keys to navigate
   - Add/remove rules

3. **Integration with HITL** (`handlers/interrupt.py`):
   - Before prompting user, check rules
   - Auto-approve or auto-deny if rule matches
   - Only prompt for `always_ask` or unmatched tools

**Exit criteria:** Can configure rules that auto-approve common tools; rules persist.

---

### Phase 14 — Graph Visualization
> See the agent's execution graph.

**Files:** `commands/graph.py`

1. **Mermaid rendering**:
   - `/graph` — Fetch graph structure from server via `client.graphs.get(graph_id)`
   - Generate Mermaid diagram from graph nodes/edges
   - Render as ASCII art in terminal (Rich tree or similar)
   - Optionally open in browser as HTML with Mermaid.js

**Exit criteria:** `/graph` displays the agent's node/edge structure.

---

### Phase 15 — One-Shot Mode & Piping
> Use deepagent-repl in scripts and pipelines.

**Files:** `cli.py`

1. **One-shot mode**:
   - `deepagent-repl "what is 2+2"` — Send single message, print response, exit
   - `echo "query" | deepagent-repl` — Read from stdin
   - `--no-stream` flag for clean output (no spinners/formatting)
   - `--json` flag for raw JSON output

2. **Exit code**:
   - 0 on success, 1 on error, 2 on interrupt

**Exit criteria:** Can use in shell scripts and pipelines.

---

### Phase 16 — Polish & Advanced Features
> Final langrepl feature parity.

1. **Theme system**:
   - Multiple built-in themes (dark, light, tokyo-night, etc.)
   - `/theme` command to switch
   - Auto-detection refinement

2. **Rate limiting** (`utils/rate_limiter.py`):
   - Respect server rate limits
   - Exponential backoff on 429 responses
   - Display wait time to user

3. **Connection resilience**:
   - Auto-reconnect on server disconnect
   - Retry logic for transient failures
   - Clear error messages when server is unreachable

4. **Keyboard shortcuts**:
   - Ctrl+L: clear screen
   - Ctrl+C: cancel current stream (send cancellation to server)
   - Ctrl+D: exit gracefully
   - Esc: dismiss current tool output

5. **Export**:
   - `/export` — Save conversation to markdown file
   - Include tool calls, results, and metadata

---

## Verification Plan

Each phase has its own exit criteria above. End-to-end testing:

1. Start any Deep Agent server (e.g., cowork): `cd /path/to/agent && uv run langgraph dev`
2. In another terminal: `cd deepagent-repl && uv run deepagent-repl`
   - Should auto-discover the graph and connect
3. Test basic chat, streaming, tool calls, HITL approval
4. Test slash commands: `/new`, `/resume`, `/threads`, `/help`, `/compress`, `/skills`
5. Test with a different Deep Agent server to verify server-agnostic behavior
6. Test edge cases: server down, long responses, rapid input, multiple graphs on same server
7. Run `uv run pytest -v` for unit tests
8. Run `uv run ruff check src/ tests/` for linting
