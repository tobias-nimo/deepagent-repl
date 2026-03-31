from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """Mutable session state for the current REPL run."""

    thread_id: str | None = None
    graph_id: str | None = None
    assistant_id: str | None = None
    model: str | None = None
    status: str = "idle"  # idle | streaming | interrupted
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    messages: list[dict] = field(default_factory=list)
    prompt_session: Any = None  # PromptSession instance (set during startup)

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token usage and recompute cost."""
        from deepagent_repl.utils.cost import compute_cost

        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_cost += compute_cost(input_tokens, output_tokens, self.model)
