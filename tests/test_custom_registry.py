import pytest
from unittest.mock import AsyncMock, patch
from app.ai.registry import ProviderRegistry
from app.ai.providers.base import ProviderType
from app.services.config_service import ACTIVE_LLM_MODEL_KEY


@pytest.mark.asyncio
async def test_custom_llm_resolution():
    # Mock AsyncSession
    db = AsyncMock()
    
    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            if key == ACTIVE_LLM_MODEL_KEY:
                return "custom/openai"
            elif key == "llm_api_key":
                return "sk-custom-test-key"
            elif key == "llm_base_url":
                return "http://localhost:8000/v1"
            elif key == "llm_custom_model_id":
                return "meta-llama/Llama-3-8B-Instruct"
            return None
        
        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()
        
        assert llm.config.provider == ProviderType.CUSTOM_OPENAI
        assert llm.config.model_id == "meta-llama/Llama-3-8B-Instruct"
        assert llm.config.base_url == "http://localhost:8000/v1"
        assert llm.config.api_key == "sk-custom-test-key"


@pytest.mark.asyncio
async def test_standard_llm_ignores_custom_base_url():
    # Mock AsyncSession
    db = AsyncMock()
    
    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            if key == ACTIVE_LLM_MODEL_KEY:
                # Standard OpenAI model spec
                return "openai/gpt-4o"
            elif key == "llm_api_key":
                return "sk-standard-key"
            elif key == "llm_base_url":
                # Configured in database for custom, but active model is standard
                return "http://localhost:8000/v1"
            return None
        
        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()
        
        assert llm.config.provider == ProviderType.OPENAI
        assert llm.config.model_id == "gpt-4o"
        # Standard model must ignore llm_base_url!
        assert llm.config.base_url is None
        assert llm.config.api_key == "sk-standard-key"


@pytest.mark.asyncio
async def test_custom_embedding_resolution():
    # Mock AsyncSession
    db = AsyncMock()
    from app.services.config_service import ACTIVE_EMBEDDING_MODEL_KEY

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            if key == ACTIVE_EMBEDDING_MODEL_KEY:
                return "custom/openai-1536"
            elif key == "embedding_api_key__custom_openai":
                return "sk-custom-emb-key"
            elif key == "embedding_base_url":
                return "http://localhost:8001/v1"
            elif key == "embedding_custom_model_id":
                return "local-embedding-model"
            return None
        
        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        emb = await registry.get_embedding()
        
        assert emb.config.provider == ProviderType.CUSTOM_OPENAI
        assert emb.config.model_id == "local-embedding-model"
        assert emb.config.base_url == "http://localhost:8001/v1"
        assert emb.config.api_key == "sk-custom-emb-key"
        assert emb.config.dimensions == 1536


@pytest.mark.asyncio
async def test_custom_vision_resolution():
    # Mock AsyncSession
    db = AsyncMock()
    from app.services.config_service import ACTIVE_VISION_MODEL_KEY

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            if key == ACTIVE_VISION_MODEL_KEY:
                return "custom/openai"
            elif key == "vision_api_key":
                return "sk-custom-vis-key"
            elif key == "vision_base_url":
                return "http://localhost:8002/v1"
            elif key == "vision_custom_model_id":
                return "local-vision-model"
            return None

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        vis = await registry.get_vision()

        assert vis is not None
        assert vis.config.provider == ProviderType.CUSTOM_OPENAI
        assert vis.config.model_id == "local-vision-model"
        assert vis.config.base_url == "http://localhost:8002/v1"
        assert vis.config.api_key == "sk-custom-vis-key"


@pytest.mark.asyncio
async def test_bifrost_llm_resolution():
    """Registry loads Bifrost-scoped keys and parses fallbacks JSON."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/bifrost",
                "llm_api_key__bifrost": "bfk-virtual-key",
                "llm_bifrost_base_url": "https://bifrost.myco.com",
                "llm_bifrost_model_id": "gpt-4o-mini",
                "llm_bifrost_fallbacks": '["anthropic/claude-3-5-sonnet","bedrock/claude-3"]',
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.provider == ProviderType.BIFROST
        assert llm.config.model_id == "gpt-4o-mini"
        assert llm.config.base_url == "https://bifrost.myco.com"
        assert llm.config.api_key == "bfk-virtual-key"
        assert llm.config.extra["fallbacks"] == [
            "anthropic/claude-3-5-sonnet",
            "bedrock/claude-3",
        ]


@pytest.mark.asyncio
async def test_bifrost_llm_empty_fallbacks():
    """Registry handles missing fallbacks key gracefully (returns empty list)."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/bifrost",
                "llm_api_key__bifrost": "bfk-key",
                "llm_bifrost_base_url": "https://bifrost.myco.com",
                "llm_bifrost_model_id": "gpt-4o",
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.extra["fallbacks"] == []


@pytest.mark.asyncio
async def test_bifrost_vision_resolution():
    """Registry loads Bifrost vision-scoped keys."""
    db = AsyncMock()
    from app.services.config_service import ACTIVE_VISION_MODEL_KEY

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                ACTIVE_VISION_MODEL_KEY: "custom/bifrost",
                "vision_api_key__bifrost": "bfk-vis-key",
                "vision_bifrost_base_url": "https://bifrost.myco.com",
                "vision_bifrost_model_id": "gpt-4o",
                "vision_bifrost_fallbacks": '["anthropic/claude-3-5-sonnet"]',
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        vis = await registry.get_vision()

        assert vis is not None
        assert vis.config.provider == ProviderType.BIFROST
        assert vis.config.model_id == "gpt-4o"
        assert vis.config.base_url == "https://bifrost.myco.com"
        assert vis.config.extra["fallbacks"] == ["anthropic/claude-3-5-sonnet"]


@pytest.mark.asyncio
async def test_custom_openai_unaffected_by_bifrost():
    """custom/openai still loads from llm_base_url / llm_custom_model_id."""
    db = AsyncMock()

    with patch("app.services.config_service.ConfigService.get") as mock_get:
        async def mock_get_fn(key):
            return {
                "active_llm_model_spec_id": "custom/openai",
                "llm_api_key__custom_openai": "sk-openai",
                "llm_base_url": "http://localhost:8080/v1",
                "llm_custom_model_id": "llama-3-8b",
            }.get(key)

        mock_get.side_effect = mock_get_fn

        registry = ProviderRegistry(db)
        llm = await registry.get_llm()

        assert llm.config.provider == ProviderType.CUSTOM_OPENAI
        assert llm.config.base_url == "http://localhost:8080/v1"
        assert llm.config.model_id == "llama-3-8b"
        assert llm.config.extra.get("fallbacks") is None
