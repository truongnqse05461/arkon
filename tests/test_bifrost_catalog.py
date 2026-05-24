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
