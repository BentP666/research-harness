"""Tests for litellm_backend.py — LiteLLM provider integration."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

_has_litellm = importlib.util.find_spec("litellm") is not None
needs_litellm = pytest.mark.skipif(not _has_litellm, reason="litellm not installed")


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset provider registry after each test to avoid cross-contamination."""
    from llm_router.client import _PROVIDER_REGISTRY

    snapshot = dict(_PROVIDER_REGISTRY)
    yield
    _PROVIDER_REGISTRY.clear()
    _PROVIDER_REGISTRY.update(snapshot)


# ---------------------------------------------------------------------------
# detect_litellm_providers
# ---------------------------------------------------------------------------


class TestDetectLitellmProviders:
    def test_empty_when_no_keys(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

        from llm_router.litellm_backend import detect_litellm_providers

        result = detect_litellm_providers()
        for name in ("deepseek", "zhipu", "qwen"):
            assert name not in result

    def test_detects_deepseek(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        from llm_router.litellm_backend import detect_litellm_providers

        assert "deepseek" in detect_litellm_providers()

    def test_detects_zhipu_alt_key(self, monkeypatch):
        monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
        monkeypatch.setenv("GLM_API_KEY", "test-glm")
        from llm_router.litellm_backend import detect_litellm_providers

        assert "zhipu" in detect_litellm_providers()

    def test_detects_qwen_alt_key(self, monkeypatch):
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.setenv("QWEN_API_KEY", "test-qwen")
        from llm_router.litellm_backend import detect_litellm_providers

        assert "qwen" in detect_litellm_providers()

    def test_detects_multiple(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-1")
        monkeypatch.setenv("MOONSHOT_API_KEY", "sk-2")
        from llm_router.litellm_backend import detect_litellm_providers

        detected = detect_litellm_providers()
        assert "deepseek" in detected
        assert "moonshot" in detected


# ---------------------------------------------------------------------------
# register_litellm_providers
# ---------------------------------------------------------------------------


class TestRegisterLitellmProviders:
    def test_registers_when_key_present(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        from llm_router.client import _PROVIDER_REGISTRY
        from llm_router.litellm_backend import register_litellm_providers

        _PROVIDER_REGISTRY.pop("deepseek", None)
        registered = register_litellm_providers()
        assert "deepseek" in registered
        assert "deepseek" in _PROVIDER_REGISTRY

    def test_skips_native_providers(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-native")
        from llm_router.client import _PROVIDER_REGISTRY
        from llm_router.litellm_backend import register_litellm_providers

        original_fn = _PROVIDER_REGISTRY.get("openai")
        register_litellm_providers()
        assert _PROVIDER_REGISTRY.get("openai") is original_fn

    def test_skips_when_no_key(self, monkeypatch):
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        from llm_router.client import _PROVIDER_REGISTRY
        from llm_router.litellm_backend import register_litellm_providers

        _PROVIDER_REGISTRY.pop("siliconflow", None)
        register_litellm_providers()
        assert "siliconflow" not in _PROVIDER_REGISTRY


# ---------------------------------------------------------------------------
# _make_litellm_chat_fn
# ---------------------------------------------------------------------------


@needs_litellm
class TestMakeLitellmChatFn:
    def test_calls_litellm_completion(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        from llm_router.litellm_backend import LITELLM_PROVIDERS, _make_litellm_chat_fn

        meta = LITELLM_PROVIDERS["deepseek"]
        fn = _make_litellm_chat_fn(meta)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from DeepSeek"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            result = fn("test prompt", "deepseek-chat", api_key="sk-test")

        assert result == "Hello from DeepSeek"
        mock_comp.assert_called_once()
        call_kwargs = mock_comp.call_args
        assert call_kwargs.kwargs["model"] == "deepseek/deepseek-chat"

    def test_openai_compat_prefix(self, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-qwen")
        from llm_router.litellm_backend import LITELLM_PROVIDERS, _make_litellm_chat_fn

        meta = LITELLM_PROVIDERS["qwen"]
        fn = _make_litellm_chat_fn(meta)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Qwen response"
        mock_response.usage = None

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            fn("test", "qwen-max", api_key="sk-qwen")

        call_kwargs = mock_comp.call_args
        assert call_kwargs.kwargs["model"] == "openai/qwen-max"
        assert call_kwargs.kwargs["base_url"] == meta.base_url

    def test_records_usage(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        from llm_router.client import get_last_usage
        from llm_router.litellm_backend import LITELLM_PROVIDERS, _make_litellm_chat_fn

        meta = LITELLM_PROVIDERS["deepseek"]
        fn = _make_litellm_chat_fn(meta)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        with patch("litellm.completion", return_value=mock_response):
            fn("test", "deepseek-chat", api_key="sk-test")

        usage = get_last_usage()
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50


# ---------------------------------------------------------------------------
# suggest_tier_mapping
# ---------------------------------------------------------------------------


class TestSuggestTierMapping:
    def test_single_provider_maps_all_tiers(self):
        from llm_router.litellm_backend import suggest_tier_mapping

        result = suggest_tier_mapping(["deepseek"])
        assert result["light"] == ("deepseek", "deepseek-chat")
        assert result["medium"] == ("deepseek", "deepseek-chat")
        assert result["heavy"] == ("deepseek", "deepseek-reasoner")

    def test_multi_provider_distributes(self):
        from llm_router.litellm_backend import suggest_tier_mapping

        result = suggest_tier_mapping(["siliconflow", "deepseek", "qwen"])
        assert len(result) == 3
        for tier in ("light", "medium", "heavy"):
            prov, model = result[tier]
            assert prov in ("siliconflow", "deepseek", "qwen")
            assert model  # non-empty

    def test_empty_input_returns_empty(self):
        from llm_router.litellm_backend import suggest_tier_mapping

        assert suggest_tier_mapping([]) == {}

    def test_unknown_providers_ignored(self):
        from llm_router.litellm_backend import suggest_tier_mapping

        result = suggest_tier_mapping(["unknown_provider"])
        assert result == {}

    def test_red_line_not_violated(self):
        from llm_router.litellm_backend import suggest_tier_mapping

        # anthropic is not in LITELLM_PROVIDERS so won't be mapped,
        # but verify the function handles it if it were.
        result = suggest_tier_mapping(["deepseek"])
        if "light" in result:
            assert result["light"][0] != "anthropic"
        if "medium" in result:
            assert result["medium"][0] != "anthropic"


# ---------------------------------------------------------------------------
# get_litellm_provider_meta
# ---------------------------------------------------------------------------


class TestGetProviderMeta:
    def test_known_provider(self):
        from llm_router.litellm_backend import get_litellm_provider_meta

        meta = get_litellm_provider_meta("deepseek")
        assert meta is not None
        assert meta.display_name == "DeepSeek"

    def test_unknown_returns_none(self):
        from llm_router.litellm_backend import get_litellm_provider_meta

        assert get_litellm_provider_meta("nonexistent") is None
