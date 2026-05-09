"""Pluggable multi-provider LLM router with task-tier routing."""

from .client import (
    LLMClient,
    LLMUsage,
    OpenAICompatibleClient,
    ResolvedLLMConfig,
    TaskTier,
    available_providers,
    get_last_usage,
    get_provider,
    list_providers,
    register_provider,
    resolve_llm_config,
    resolve_route,
    set_default_route,
)
from .config import (
    detect_available_providers,
    get_provider_order,
    get_tier_route,
    load_config,
)
from .plugins import load_plugins

# LiteLLM integration (optional: no-op when litellm is not installed).
try:
    from .litellm_backend import (
        LITELLM_PROVIDERS,
        ProviderMeta,
        detect_litellm_providers,
        get_litellm_provider_meta,
        resolve_provider_api_key,
        suggest_tier_mapping,
    )
except ImportError:

    class ProviderMeta:  # type: ignore[no-redef]
        """Stub when litellm is not installed."""

    LITELLM_PROVIDERS: dict = {}  # type: ignore[no-redef]

    def detect_litellm_providers() -> list[str]:  # type: ignore[no-redef]
        return []

    def get_litellm_provider_meta(name: str):  # type: ignore[no-redef]
        return None

    def resolve_provider_api_key(meta) -> str:  # type: ignore[no-redef]
        return ""

    def suggest_tier_mapping(available: list[str]) -> dict:  # type: ignore[no-redef]
        return {}


__all__ = [
    "LLMClient",
    "LLMUsage",
    "LITELLM_PROVIDERS",
    "OpenAICompatibleClient",
    "ProviderMeta",
    "ResolvedLLMConfig",
    "TaskTier",
    "available_providers",
    "detect_available_providers",
    "detect_litellm_providers",
    "get_last_usage",
    "get_litellm_provider_meta",
    "get_provider",
    "get_provider_order",
    "get_tier_route",
    "list_providers",
    "load_config",
    "load_plugins",
    "register_provider",
    "resolve_llm_config",
    "resolve_provider_api_key",
    "resolve_route",
    "set_default_route",
    "suggest_tier_mapping",
]

# Discover user-supplied provider plugins. Failures are logged, not raised,
# so a broken plugin cannot crash the rest of the router.
load_plugins()
