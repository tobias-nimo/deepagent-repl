# deepagent-repl

A rich terminal REPL for any [LangChain Deep Agent](https://github.com/langchain-ai/deepagents) server. Connect to any LangGraph server, stream responses with live markdown rendering, handle human-in-the-loop interrupts, manage threads, invoke skills, and more.

## Quick Start

```bash
# Install
uv sync

# Start your Deep Agent server (in another terminal)
cd /path/to/your/agent && uv run langgraph dev --no-browser

# Connect
uv run deepagent-repl
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGGRAPH_URL` | `http://localhost:2024` | Server URL |
| `GRAPH_ID` | auto-discover | Specific graph/assistant to connect to |
| `LANGSMITH_API_KEY` | — | API key for authenticated connections |
| `THREAD_ID` | — | Resume a specific thread on startup |

## Commands

All commands start with `/` and support **tab completion**.

### Session

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/status` | Connection info, token usage, and cost |
| `/new` | Start a fresh conversation thread |
| `/clear` | Clear the terminal screen |
| `/exit` | Exit the REPL |

### Threads

| Command | Description |
|---------|-------------|
| `/threads` | List saved conversation threads |
| `/resume [thread_id]` | Resume a past thread (interactive picker if no ID given) |
| `/replay` | Browse message history and fork from an earlier point |
| `/compress` | Summarize conversation to reduce token usage |
| `/export [filename]` | Export conversation to markdown |

### Tools & Skills

| Command | Description |
|---------|-------------|
| `/skills` | List discovered skills from the connected agent |
| `/skills refresh` | Re-fetch skills from thread state |
| `/<skill-name> [question]` | Invoke a skill — the agent reads its SKILL.md and follows the instructions |
| `/rules allow <tool>` | Auto-approve a tool (supports wildcards: `edit_*`) |
| `/rules deny <tool>` | Auto-reject a tool |
| `/rules ask <tool>` | Always prompt for a tool |
| `/rules remove <tool>` | Remove a rule |
| `/rules` | Show current approval rules |

### Media & Visualization

| Command | Description |
|---------|-------------|
| `/image <path> [message]` | Send an image to the agent |
| `/graph` | Show the agent's execution graph as a tree |
| `/graph --browser` | Open graph as Mermaid diagram in browser |
| `/theme [name]` | Switch color theme |

Available themes: `dark`, `light`, `monokai`, `dracula`, `github-dark`, `one-dark`, `solarized-dark`, `solarized-light`

## Key Bindings

| Key | Action |
|-----|--------|
| **Enter** | Submit message |
| **Shift+Enter** | Insert newline (kitty/xterm terminals) |
| **Alt+Enter** | Insert newline (universal) |
| **Ctrl+J** | Insert newline (universal) |
| **Ctrl+L** | Clear screen |
| **Ctrl+D** | Exit |
| **Tab** | Auto-complete commands |

> **Note on Shift+Enter**: Requires a terminal that supports the [kitty keyboard protocol](https://sw.kovidgoyal.net/kitty/keyboard-protocol/) (Kitty, Ghostty, iTerm2 with protocol enabled). Use Alt+Enter or Ctrl+J as universal alternatives.

Trailing backslash (`\`) also continues input to the next line.

## Features

### Streaming & Rendering

- Token-by-token streaming with live markdown rendering
- Syntax-highlighted code blocks, tables, bold, italic
- Spinner while the agent is thinking
- Tool calls displayed as styled panels with arguments
- Tool results shown with green/red status indicators

### Human-in-the-Loop (HITL)

When the agent requests approval (e.g., before editing a file):

- Interrupt panel shows description, detail (diffs, content), and numbered options
- Respond by number (`1`, `2`) or name (`approve`, `reject`)
- Choose `edit` to open content in `$EDITOR` before approving
- **Approval rules** auto-resolve common interrupts without prompting

### Skills

Skills are agent capabilities defined as `SKILL.md` files on the server (via Deep Agents' [SkillsMiddleware](https://github.com/langchain-ai/deepagents)).

- Auto-discovered from thread state after the first message
- Registered as `/slash-commands` with tab completion
- `/web-research how does quantum computing work` — reads the skill's instructions and follows them
- `/skills refresh` to re-fetch after reconnecting

### Image & Multimodal

- Send images with `/image <path>` or just include a file path in your message
- Auto-detects image paths and converts to multimodal content
- Inline image rendering in iTerm2, Kitty, and WezTerm
- Supports: PNG, JPG, GIF, BMP, WebP, SVG, TIFF, ICO

### Thread Management

- Conversations persist as threads on the server
- Local SQLite index for quick browsing (`~/.deepagent-repl/threads.db`)
- Fork from any point in history with `/replay`
- `/compress` summarizes long conversations into a new compact thread

### Token & Cost Tracking

- Live token counter in the bottom toolbar
- Automatic cost calculation for Claude models
- Warning when approaching context limits (~80% of 200k)
- `/status` for detailed breakdown

## One-Shot Mode

Send a single message without entering the REPL:

```bash
# Streaming output (default)
deepagent-repl "What is the capital of France?"

# Plain text, no streaming
deepagent-repl --no-stream "Summarize this file"

# Raw JSON output
deepagent-repl --json "List all tools"

# Piped input
echo "Explain this error" | deepagent-repl
```

Exit codes: `0` success, `1` error, `2` interrupted.

## Troubleshooting

### Shift+Enter not working (iTerm2)

If Shift+Enter does nothing in iTerm2, you need to enable the kitty keyboard protocol:

1. Open **iTerm2 → Settings → Profiles → Keys**
2. Enable **"Report modifiers using CSI u"**
3. Restart your terminal session

This allows iTerm2 to send a distinguishable key sequence for Shift+Enter. Without it, Shift+Enter is identical to Enter at the terminal level. Alt+Enter and Ctrl+J always work as alternatives.

## File Locations

| Path | Purpose |
|------|---------|
| `~/.deepagent-repl/history` | Persistent command history |
| `~/.deepagent-repl/threads.db` | Thread index (SQLite) |
| `~/.deepagent-repl/rules.json` | Tool approval rules |
| `.env` | Configuration |
