"""Smoke tests for Bifrost catalog entries and config keys."""

from app.ai.providers.base import ProviderType


def test_bifrost_provider_type_exists():
    assert ProviderType.BIFROST == "bifrost"
