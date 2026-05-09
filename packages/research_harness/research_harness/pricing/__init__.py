"""Per-model pricing table for token cost calculation.

All prices are in USD per million tokens. Edit this file to add/update models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_m: float
    output_per_m: float


PRICES: dict[str, ModelPrice] = {
    # Anthropic
    "claude-opus-4-7": ModelPrice(input_per_m=15.0, output_per_m=75.0),
    "claude-opus-4-6": ModelPrice(input_per_m=15.0, output_per_m=75.0),
    "claude-sonnet-4-6": ModelPrice(input_per_m=3.0, output_per_m=15.0),
    "claude-haiku-4-5": ModelPrice(input_per_m=0.80, output_per_m=4.0),
    # OpenAI
    "gpt-5": ModelPrice(input_per_m=10.0, output_per_m=30.0),
    "gpt-4.1": ModelPrice(input_per_m=2.0, output_per_m=8.0),
    "gpt-4.1-mini": ModelPrice(input_per_m=0.40, output_per_m=1.60),
    "gpt-4.1-nano": ModelPrice(input_per_m=0.10, output_per_m=0.40),
    # Google
    "gemini-2.5-pro": ModelPrice(input_per_m=1.25, output_per_m=10.0),
    "gemini-2.5-flash": ModelPrice(input_per_m=0.15, output_per_m=0.60),
    # Kimi / Moonshot
    "kimi-k2": ModelPrice(input_per_m=1.0, output_per_m=4.0),
    "moonshot-v1-128k": ModelPrice(input_per_m=0.80, output_per_m=3.20),
}

DEFAULT_PRICE = ModelPrice(input_per_m=3.0, output_per_m=15.0)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = PRICES.get(model, DEFAULT_PRICE)
    return (
        prompt_tokens * price.input_per_m + completion_tokens * price.output_per_m
    ) / 1_000_000
