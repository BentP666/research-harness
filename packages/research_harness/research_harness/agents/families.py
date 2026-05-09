"""Provider family mapping for agent diversity enforcement."""

from __future__ import annotations

FAMILIES: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai-compat",
    "chatgpt": "openai-compat",
    "google": "google",
    "gemini": "google",
    "kimi": "openai-compat",
    "cursor_agent": "cursor",
    "codex": "openai-compat",
}


def get_family(provider: str) -> str:
    return FAMILIES.get(provider.lower(), provider.lower())


def same_family(provider_a: str, provider_b: str) -> bool:
    return get_family(provider_a) == get_family(provider_b)
