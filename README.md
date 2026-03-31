# deepagent-repl

Terminal REPL for any LangChain Deep Agent server.

## Quick Start

```bash
# Install
uv sync

# Start your Deep Agent server (in another terminal)
cd /path/to/your/agent && uv run langgraph dev

# Connect
uv run deepagent-repl
```

## Configuration

Set via environment variables or `.env` file:

- `LANGGRAPH_URL` — Server URL (default: `http://localhost:2024`)
- `GRAPH_ID` — Graph ID (default: auto-discover)
- `LANGSMITH_API_KEY` — For authenticated connections (optional)
