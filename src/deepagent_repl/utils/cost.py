"""Cost calculation based on model-specific token pricing."""

from __future__ import annotations

# Pricing per 1M tokens (input, output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Claude 4.5 / 4.6 family
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    # Claude 3.5 family
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.80, 4.0),
    # Claude 3 family
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
}

# Default pricing if model is unknown
DEFAULT_PRICING = (3.0, 15.0)


def compute_cost(input_tokens: int, output_tokens: int, model: str | None = None) -> float:
    """Compute cost in USD for a given token count and model."""
    pricing = DEFAULT_PRICING
    if model:
        # Try exact match first, then prefix match
        if model in MODEL_PRICING:
            pricing = MODEL_PRICING[model]
        else:
            for key, val in MODEL_PRICING.items():
                if model.startswith(key) or key.startswith(model):
                    pricing = val
                    break

    input_rate, output_rate = pricing
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def format_cost(cost: float) -> str:
    """Format a cost value for display."""
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def format_tokens(count: int) -> str:
    """Format a token count for compact display."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)
