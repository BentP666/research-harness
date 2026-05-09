"""LiteLLM-backed provider integration for Chinese and other LLM providers.

Registers providers whose APIs are handled by the ``litellm`` SDK so that
the existing tier-routing and plugin system works unchanged.  The module is
**optional**: if ``litellm`` is not installed, every public function degrades
gracefully (returns empty results or raises ``ImportError``).

Supported Chinese providers out of the box:
  DeepSeek, Zhipu/GLM, Qwen/Tongyi, Moonshot/Kimi-API, Doubao/Volcengine,
  MiniMax, Yi/01.AI, Baichuan, SiliconFlow (gateway).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

# Re-use the thread-local usage recorder from the main client module.
from .client import ProviderFn, _coerce_int, _record_usage

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class ProviderMeta:
    """Metadata for a LiteLLM-backed provider."""

    litellm_prefix: str
    api_key_env: str
    display_name: str
    family: str
    base_url: str = ""
    alt_api_key_envs: tuple[str, ...] = ()
    tier_suggestions: dict[str, str] = field(default_factory=dict)
    cost_rank: int = (
        50  # 0 = cheapest, 100 = most expensive (used by suggest_tier_mapping)
    )


LITELLM_PROVIDERS: dict[str, ProviderMeta] = {
    "deepseek": ProviderMeta(
        litellm_prefix="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        family="deepseek",
        tier_suggestions={
            "light": "deepseek-chat",
            "medium": "deepseek-chat",
            "heavy": "deepseek-reasoner",
        },
        cost_rank=20,
    ),
    "zhipu": ProviderMeta(
        litellm_prefix="zhipuai",
        api_key_env="ZHIPUAI_API_KEY",
        alt_api_key_envs=("ZHIPU_API_KEY", "GLM_API_KEY"),
        display_name="Zhipu / GLM",
        family="zhipu",
        tier_suggestions={
            "light": "glm-4-flash",
            "medium": "glm-4",
            "heavy": "glm-4-long",
        },
        cost_rank=25,
    ),
    "qwen": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="DASHSCOPE_API_KEY",
        alt_api_key_envs=("QWEN_API_KEY", "TONGYI_API_KEY"),
        display_name="Qwen / Tongyi",
        family="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        tier_suggestions={
            "light": "qwen-turbo",
            "medium": "qwen-plus",
            "heavy": "qwen-max",
        },
        cost_rank=30,
    ),
    "moonshot": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="MOONSHOT_API_KEY",
        display_name="Moonshot / Kimi API",
        family="moonshot",
        base_url="https://api.moonshot.cn/v1",
        tier_suggestions={
            "light": "moonshot-v1-8k",
            "medium": "moonshot-v1-32k",
            "heavy": "moonshot-v1-128k",
        },
        cost_rank=35,
    ),
    "doubao": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="VOLCENGINE_API_KEY",
        alt_api_key_envs=("ARK_API_KEY", "DOUBAO_API_KEY"),
        display_name="Doubao / Volcengine",
        family="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        tier_suggestions={
            "light": "doubao-lite-32k",
            "medium": "doubao-pro-32k",
            "heavy": "doubao-pro-256k",
        },
        cost_rank=20,
    ),
    "minimax": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="MINIMAX_API_KEY",
        display_name="MiniMax",
        family="minimax",
        base_url="https://api.minimax.chat/v1",
        tier_suggestions={
            "light": "MiniMax-Text-01",
            "medium": "MiniMax-Text-01",
            "heavy": "MiniMax-Text-01",
        },
        cost_rank=30,
    ),
    "yi": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="YI_API_KEY",
        display_name="Yi / 01.AI",
        family="yi",
        base_url="https://api.lingyiwanwu.com/v1",
        tier_suggestions={
            "light": "yi-lightning",
            "medium": "yi-large",
            "heavy": "yi-large-turbo",
        },
        cost_rank=25,
    ),
    "baichuan": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="BAICHUAN_API_KEY",
        display_name="Baichuan",
        family="baichuan",
        base_url="https://api.baichuan-ai.com/v1",
        tier_suggestions={
            "light": "Baichuan4-Turbo",
            "medium": "Baichuan4",
            "heavy": "Baichuan4",
        },
        cost_rank=30,
    ),
    "siliconflow": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="SILICONFLOW_API_KEY",
        display_name="SiliconFlow",
        family="siliconflow",
        base_url="https://api.siliconflow.cn/v1",
        tier_suggestions={
            "light": "deepseek-ai/DeepSeek-V3",
            "medium": "deepseek-ai/DeepSeek-V3",
            "heavy": "deepseek-ai/DeepSeek-R1",
        },
        cost_rank=15,
    ),
    "stepfun": ProviderMeta(
        litellm_prefix="openai",
        api_key_env="STEPFUN_API_KEY",
        display_name="StepFun",
        family="stepfun",
        base_url="https://api.stepfun.com/v1",
        tier_suggestions={
            "light": "step-1-flash",
            "medium": "step-2-16k",
            "heavy": "step-2-16k",
        },
        cost_rank=30,
    ),
}

# Providers that must never be used for light/medium tiers (expensive).
_EXPENSIVE_PROVIDERS = frozenset({"anthropic"})


def resolve_provider_api_key(meta: ProviderMeta) -> str:
    """Return the first non-empty API key from primary + alt env vars."""
    val = os.environ.get(meta.api_key_env, "").strip()
    if val:
        return val
    for alt in meta.alt_api_key_envs:
        val = os.environ.get(alt, "").strip()
        if val:
            return val
    return ""


def detect_litellm_providers() -> list[str]:
    """Return names of LITELLM_PROVIDERS whose API key env var is set."""
    return [
        name
        for name, meta in LITELLM_PROVIDERS.items()
        if resolve_provider_api_key(meta)
    ]


def get_litellm_provider_meta(name: str) -> ProviderMeta | None:
    return LITELLM_PROVIDERS.get(name)


def _make_litellm_chat_fn(meta: ProviderMeta) -> ProviderFn:
    """Factory: return a provider function backed by litellm.completion()."""

    def _chat(
        prompt: str,
        model: str,
        *,
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.0,
        **_: Any,
    ) -> str:
        import litellm

        resolved_key = api_key or resolve_provider_api_key(meta)
        resolved_url = base_url or meta.base_url

        # For providers with litellm native support (e.g. deepseek, zhipuai),
        # use the prefix/model format.  For OpenAI-compatible endpoints, pass
        # the model name directly and rely on base_url.
        if meta.litellm_prefix == "openai" and resolved_url:
            litellm_model = f"openai/{model}"
        elif meta.litellm_prefix:
            litellm_model = f"{meta.litellm_prefix}/{model}"
        else:
            litellm_model = model

        response = litellm.completion(
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            api_key=resolved_key or None,
            base_url=resolved_url or None,
            timeout=_LLM_TIMEOUT_SECONDS,
        )

        usage = getattr(response, "usage", None)
        if usage is not None:
            _record_usage(
                _coerce_int(getattr(usage, "prompt_tokens", None)),
                _coerce_int(getattr(usage, "completion_tokens", None)),
            )

        return response.choices[0].message.content or ""

    _chat.__doc__ = f"LiteLLM-backed chat for {meta.display_name}"
    return _chat


def register_litellm_providers() -> list[str]:
    """Register all detectable LiteLLM-backed providers in the global registry.

    Skips providers that are already natively registered (e.g. ``openai``,
    ``anthropic``) so native implementations are never overridden.

    Returns the list of provider names that were actually registered.
    """
    from .client import _PROVIDER_REGISTRY, register_provider

    registered: list[str] = []
    for name, meta in LITELLM_PROVIDERS.items():
        if name in _PROVIDER_REGISTRY:
            continue
        if not resolve_provider_api_key(meta):
            continue
        fn = _make_litellm_chat_fn(meta)
        register_provider(name, fn)
        registered.append(name)
        logger.info("Registered LiteLLM provider: %s (%s)", name, meta.display_name)
    return registered


def suggest_tier_mapping(
    available: list[str],
) -> dict[str, tuple[str, str]]:
    """Suggest an optimal tier mapping given available provider names.

    Returns ``{"light": (provider, model), "medium": ..., "heavy": ...}``.

    Strategy:
      - Single provider: all three tiers map to that provider's tier_suggestions.
      - Multiple providers: sort by cost_rank; cheapest for light, mid for medium,
        most capable for heavy.
      - Respects RED LINE: never puts ``anthropic`` on light/medium.
    """
    all_meta: dict[str, ProviderMeta] = {}
    for name in available:
        meta = LITELLM_PROVIDERS.get(name)
        if meta:
            all_meta[name] = meta

    if not all_meta:
        return {}

    if len(all_meta) == 1:
        name, meta = next(iter(all_meta.items()))
        return {
            tier: (
                name,
                meta.tier_suggestions.get(
                    tier, meta.tier_suggestions.get("medium", "")
                ),
            )
            for tier in ("light", "medium", "heavy")
        }

    sorted_by_cost = sorted(all_meta.items(), key=lambda kv: kv[1].cost_rank)

    result: dict[str, tuple[str, str]] = {}
    for tier, pick_idx in [
        ("light", 0),
        ("medium", len(sorted_by_cost) // 2),
        ("heavy", -1),
    ]:
        name, meta = sorted_by_cost[pick_idx]
        if tier in ("light", "medium") and name in _EXPENSIVE_PROVIDERS:
            name, meta = sorted_by_cost[0]
        model = meta.tier_suggestions.get(tier) or meta.tier_suggestions.get(
            "medium", ""
        )
        result[tier] = (name, model)

    return result
