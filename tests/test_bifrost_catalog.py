"""Smoke tests for Bifrost catalog entries and config keys."""

from app.ai.providers.base import ProviderType
from app.ai.llm_catalog import LLM_CATALOG, get_spec as get_llm_spec
from app.ai.vision_catalog import VISION_CATALOG, get_spec as get_vision_spec
from app.services.config_service import ALL_CONFIG_KEYS, _is_sensitive


def test_bifrost_provider_type_exists():
    assert ProviderType.BIFROST == "bifrost"


def test_bifrost_in_llm_catalog():
    assert "custom/bifrost" in LLM_CATALOG
    spec = LLM_CATALOG["custom/bifrost"]
    assert spec.provider == "bifrost"
    assert spec.supports_tools is True
    assert spec.supports_vision is True


def test_bifrost_in_vision_catalog():
    assert "custom/bifrost" in VISION_CATALOG
    spec = VISION_CATALOG["custom/bifrost"]
    assert spec.provider == "bifrost"


def test_get_llm_spec_bifrost():
    spec = get_llm_spec("custom/bifrost")
    assert spec.id == "custom/bifrost"


def test_get_vision_spec_bifrost():
    spec = get_vision_spec("custom/bifrost")
    assert spec.id == "custom/bifrost"


def test_bifrost_llm_keys_in_all_config_keys():
    for key in [
        "llm_api_key__bifrost",
        "llm_bifrost_base_url",
        "llm_bifrost_model_id",
        "llm_bifrost_fallbacks",
    ]:
        assert key in ALL_CONFIG_KEYS, f"{key!r} missing from ALL_CONFIG_KEYS"


def test_bifrost_vision_keys_in_all_config_keys():
    for key in [
        "vision_api_key__bifrost",
        "vision_bifrost_base_url",
        "vision_bifrost_model_id",
        "vision_bifrost_fallbacks",
    ]:
        assert key in ALL_CONFIG_KEYS, f"{key!r} missing from ALL_CONFIG_KEYS"


def test_bifrost_api_keys_are_sensitive():
    assert _is_sensitive("llm_api_key__bifrost")
    assert _is_sensitive("vision_api_key__bifrost")


def test_bifrost_non_key_fields_are_not_sensitive():
    assert not _is_sensitive("llm_bifrost_base_url")
    assert not _is_sensitive("llm_bifrost_model_id")
    assert not _is_sensitive("llm_bifrost_fallbacks")


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.ai.providers.base import ProviderConfig, ProviderType
from app.ai.providers.litellm_provider import LiteLLMLLM, LiteLLMVision


@pytest.mark.asyncio
async def test_bifrost_llm_injects_extra_body():
    """LiteLLMLLM passes extra_body with fallbacks for Bifrost provider."""
    config = ProviderConfig(
        provider=ProviderType.BIFROST,
        api_key="bfk-key",
        model_id="gpt-4o-mini",
        base_url="https://bifrost.myco.com",
        extra={"fallbacks": ["anthropic/claude-3-5-sonnet"]},
    )
    llm = LiteLLMLLM(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "hello"

    with patch("litellm.acompletion", return_value=mock_response) as mock_call:
        await llm.generate("Say hi")
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs.get("extra_body") == {"fallbacks": ["anthropic/claude-3-5-sonnet"]}
        # _resolve_model(BIFROST, "gpt-4o-mini") → "openai/gpt-4o-mini"
        assert call_kwargs["model"] == "openai/gpt-4o-mini"
        assert call_kwargs["base_url"] == "https://bifrost.myco.com"


@pytest.mark.asyncio
async def test_bifrost_llm_no_extra_body_when_no_fallbacks():
    """LiteLLMLLM does not inject extra_body when fallbacks list is empty."""
    config = ProviderConfig(
        provider=ProviderType.BIFROST,
        api_key="bfk-key",
        model_id="gpt-4o-mini",
        base_url="https://bifrost.myco.com",
        extra={"fallbacks": []},
    )
    llm = LiteLLMLLM(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "hello"

    with patch("litellm.acompletion", return_value=mock_response) as mock_call:
        await llm.generate("Say hi")
        call_kwargs = mock_call.call_args.kwargs
        assert "extra_body" not in call_kwargs
