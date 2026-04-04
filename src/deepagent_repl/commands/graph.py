"""The /graph command — visualize the agent's execution graph."""

from __future__ import annotations

import tempfile
import webbrowser

from rich.syntax import Syntax

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import console, render_error, render_info


@command("graph", "Show agent graph as Mermaid: /graph [--browser]")
async def cmd_graph(client, session, args: str) -> None:
    if not session.graph_id:
        render_error("No graph connected.")
        return

    render_info("Fetching graph structure...")

    try:
        graph_info = await client.get_graph(session.graph_id)
    except Exception as e:
        render_error(f"Failed to fetch graph: {e}")
        return

    nodes = graph_info.get("nodes", [])
    edges = graph_info.get("edges", [])

    if not nodes:
        render_info("Graph has no nodes.")
        return

    mermaid = _to_mermaid(nodes, edges)

    # CLI: syntax-highlighted Mermaid code block
    console.print()
    console.print(Syntax(mermaid, "text", theme="monokai", line_numbers=False, word_wrap=False))
    console.print()
    render_info(f"{len(nodes)} node(s), {len(edges)} edge(s)")

    _open_mermaid_browser(mermaid, session.graph_id)


def _to_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    """Convert graph nodes/edges to a Mermaid flowchart."""
    lines = ["graph TD"]

    for node in nodes:
        if isinstance(node, dict):
            nid = node.get("id", "")
            if nid.startswith("__"):
                lines.append(f"    {_safe_id(nid)}(({nid}))")
            else:
                lines.append(f"    {_safe_id(nid)}[{nid}]")

    for edge in edges:
        if isinstance(edge, dict):
            src = _safe_id(edge.get("source", ""))
            tgt = _safe_id(edge.get("target", ""))
            cond = edge.get("conditional", False)
            if cond:
                label = edge.get("data", "")
                if label:
                    lines.append(f"    {src} -.->|{label}| {tgt}")
                else:
                    lines.append(f"    {src} -.-> {tgt}")
            else:
                lines.append(f"    {src} --> {tgt}")

    return "\n".join(lines)


def _safe_id(s: str) -> str:
    """Make a string safe for Mermaid node IDs."""
    return s.replace("__", "X_").replace("-", "_").replace(" ", "_")


_MERMAID_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: monospace;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding: 2rem;
  }}
  h2 {{
    margin-bottom: 2rem;
    color: #89b4fa;
    font-size: 1.2rem;
    letter-spacing: 0.05em;
  }}
  .mermaid {{
    background: #181825;
    border-radius: 8px;
    padding: 2rem;
    max-width: 100%;
    overflow: auto;
  }}
</style>
</head>
<body>
<h2>{title}</h2>
<div class="mermaid">
{mermaid}
</div>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: "dark",
    themeVariables: {{ background: "#181825" }}
  }});
</script>
</body>
</html>
"""


def _open_mermaid_browser(mermaid: str, title: str) -> None:
    """Write Mermaid HTML to a temp file and open in browser."""
    html = _MERMAID_HTML.format(title=title, mermaid=mermaid)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        path = f.name
    webbrowser.open(f"file://{path}")
    render_info(f"Opened graph in browser: {path}")
