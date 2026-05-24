"""Smoke tests for Bifrost catalog entries and config keys."""

from app.ai.providers.base import ProviderType
from app.ai.llm_catalog import LLM_CATALOG, get_spec as get_llm_spec
from app.ai.vision_catalog import VISION_CATALOG, get_spec as get_vision_spec


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
