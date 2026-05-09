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
    # DeepSeek
    "deepseek-chat": ModelPrice(input_per_m=0.27, output_per_m=1.10),
    "deepseek-reasoner": ModelPrice(input_per_m=0.55, output_per_m=2.19),
    # Zhipu / GLM
    "glm-4-flash": ModelPrice(input_per_m=0.10, output_per_m=0.10),
    "glm-4": ModelPrice(input_per_m=0.70, output_per_m=0.70),
    "glm-4-long": ModelPrice(input_per_m=0.14, output_per_m=0.14),
    # Qwen / Tongyi
    "qwen-turbo": ModelPrice(input_per_m=0.30, output_per_m=0.60),
    "qwen-plus": ModelPrice(input_per_m=0.80, output_per_m=2.00),
    "qwen-max": ModelPrice(input_per_m=2.40, output_per_m=9.60),
    # Doubao / Volcengine
    "doubao-lite-32k": ModelPrice(input_per_m=0.04, output_per_m=0.04),
    "doubao-pro-32k": ModelPrice(input_per_m=0.11, output_per_m=0.11),
    "doubao-pro-256k": ModelPrice(input_per_m=0.70, output_per_m=1.30),
    # MiniMax
    "MiniMax-Text-01": ModelPrice(input_per_m=0.15, output_per_m=0.55),
    # Yi / 01.AI
    "yi-lightning": ModelPrice(input_per_m=0.14, output_per_m=0.14),
    "yi-large": ModelPrice(input_per_m=2.80, output_per_m=2.80),
    "yi-large-turbo": ModelPrice(input_per_m=1.70, output_per_m=1.70),
    # Baichuan
    "Baichuan4": ModelPrice(input_per_m=1.40, output_per_m=1.40),
    "Baichuan4-Turbo": ModelPrice(input_per_m=0.55, output_per_m=0.55),
    # StepFun
    "step-1-flash": ModelPrice(input_per_m=0.14, output_per_m=0.55),
    "step-2-16k": ModelPrice(input_per_m=0.55, output_per_m=2.10),
}

DEFAULT_PRICE = ModelPrice(input_per_m=3.0, output_per_m=15.0)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = PRICES.get(model)
    if price is None:
        # Try litellm's cost database before falling back to default.
        try:
            import litellm

            cost = litellm.completion_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            if cost is not None and cost >= 0:
                return float(cost)
        except Exception:
            pass
        price = DEFAULT_PRICE
    return (
        prompt_tokens * price.input_per_m + completion_tokens * price.output_per_m
    ) / 1_000_000
