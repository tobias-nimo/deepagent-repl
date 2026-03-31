"""The /graph command — visualize the agent's execution graph."""

from __future__ import annotations

import tempfile
import webbrowser

from rich.tree import Tree

from deepagent_repl.commands import command
from deepagent_repl.ui.renderer import console, render_error, render_info


@command("graph", "Visualize the agent's execution graph: /graph [--browser]")
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

    # Build adjacency for tree display
    node_map: dict[str, dict] = {}
    for node in nodes:
        if isinstance(node, dict):
            nid = node.get("id", "")
            node_map[nid] = node

    children: dict[str, list[str]] = {}
    for edge in edges:
        if isinstance(edge, dict):
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            if src:
                children.setdefault(src, []).append(tgt)

    # Terminal display: Rich Tree
    console.print()
    tree = Tree(f"[bold]{session.graph_id}[/bold]", guide_style="dim")
    _build_tree(tree, "__start__", children, node_map, visited=set())
    console.print(tree)
    console.print()

    render_info(f"{len(nodes)} node(s), {len(edges)} edge(s)")

    # Optional browser view with Mermaid
    if "--browser" in args:
        mermaid = _to_mermaid(nodes, edges)
        _open_mermaid_browser(mermaid, session.graph_id)


def _build_tree(
    parent: Tree,
    node_id: str,
    children: dict[str, list[str]],
    node_map: dict[str, dict],
    visited: set[str],
) -> None:
    """Recursively build a Rich Tree from the graph adjacency."""
    if node_id in visited:
        parent.add(f"[dim]{node_id} (cycle)[/dim]")
        return
    visited.add(node_id)

    for child_id in children.get(node_id, []):
        node = node_map.get(child_id, {})
        node_type = node.get("type", "")
        label = child_id

        if child_id == "__end__":
            style = "bold red"
        elif node_type == "tool":
            style = "bold cyan"
        else:
            style = "bold green"

        branch = parent.add(f"[{style}]{label}[/]")
        _build_tree(branch, child_id, children, node_map, visited.copy())


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
<html><head>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body {{ display: flex; justify-content: center; padding: 2rem; }}</style>
</head><body>
<h2>{title}</h2>
<pre class="mermaid">
{mermaid}
</pre>
<script>mermaid.initialize({{startOnLoad: true}});</script>
</body></html>
"""


def _open_mermaid_browser(mermaid: str, title: str) -> None:
    """Write Mermaid HTML to a temp file and open in browser."""
    html = _MERMAID_HTML.format(title=title, mermaid=mermaid)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        path = f.name
    webbrowser.open(f"file://{path}")
    render_info(f"Opened graph in browser: {path}")
