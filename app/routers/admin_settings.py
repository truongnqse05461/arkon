"""
Admin settings router — provider config, connection testing, dashboard stats.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.models import Department, Employee, Source
from app.database.repository import Repository
from app.services.audit_service import log_audit
from app.services.auth_service import get_current_user, require_permission

router = APIRouter()


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_sources: int
    total_departments: int
    total_employees: int


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    repo = Repository(db)
    return DashboardStats(
        total_sources=await repo.count(Source),
        total_departments=await repo.count(Department),
        total_employees=await repo.count(Employee),
    )


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

class SettingsUpdate(BaseModel):
    """Batch update config values."""
    settings: dict[str, str]


class TestConnectionResult(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None


@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Get current app settings (masked sensitive values for UI)."""
    from app.services.config_service import ConfigService

    svc = ConfigService(db)
    ui_config = await svc.get_all_for_ui()
    return ui_config


@router.put("/settings")
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user: Employee = require_permission("org:settings:manage"),
):
    """Update config values in database."""
    from app.services.config_service import ConfigService

    svc = ConfigService(db)

    # Validate custom LLM settings if active model is a custom spec
    active_spec = body.settings.get("active_llm_model_spec_id")
    if active_spec is None:
        active_spec = await svc.get("active_llm_model_spec_id")

    if active_spec and active_spec.startswith("custom/") and active_spec != "custom/bifrost":
        custom_model = body.settings.get("llm_custom_model_id")
        if custom_model is None:
            custom_model = await svc.get("llm_custom_model_id")
        custom_url = body.settings.get("llm_base_url")
        if custom_url is None:
            custom_url = await svc.get("llm_base_url")

        if not custom_model or not custom_model.strip():
            raise HTTPException(status_code=400, detail="Custom Model ID/Name cannot be empty.")
        if not custom_url or not custom_url.strip():
            raise HTTPException(status_code=400, detail="Custom Base URL cannot be empty.")
    elif active_spec == "custom/bifrost":
        bifrost_model = body.settings.get("llm_bifrost_model_id")
        if bifrost_model is None:
            bifrost_model = await svc.get("llm_bifrost_model_id")
        bifrost_url = body.settings.get("llm_bifrost_base_url")
        if bifrost_url is None:
            bifrost_url = await svc.get("llm_bifrost_base_url")

        if not bifrost_model or not bifrost_model.strip():
            raise HTTPException(status_code=400, detail="Bifrost Model ID cannot be empty.")
        if not bifrost_url or not bifrost_url.strip():
            raise HTTPException(status_code=400, detail="Bifrost Base URL cannot be empty.")

    # Validate custom Embedding settings if active model is a custom spec
    active_emb_spec = body.settings.get("active_embedding_model_spec_id")
    if active_emb_spec is None:
        active_emb_spec = await svc.get("active_embedding_model_spec_id")

    if active_emb_spec and active_emb_spec.startswith("custom/"):
        custom_emb_model = body.settings.get("embedding_custom_model_id")
        if custom_emb_model is None:
            custom_emb_model = await svc.get("embedding_custom_model_id")
        custom_emb_url = body.settings.get("embedding_base_url")
        if custom_emb_url is None:
            custom_emb_url = await svc.get("embedding_base_url")

        if not custom_emb_model or not custom_emb_model.strip():
            raise HTTPException(status_code=400, detail="Custom Embedding Model ID/Name cannot be empty.")
        if not custom_emb_url or not custom_emb_url.strip():
            raise HTTPException(status_code=400, detail="Custom Embedding Base URL cannot be empty.")

    # Validate custom Vision settings if active model is a custom spec
    active_vis_spec = body.settings.get("active_vision_model_spec_id")
    if active_vis_spec is None:
        active_vis_spec = await svc.get("active_vision_model_spec_id")

    if active_vis_spec and active_vis_spec.startswith("custom/") and active_vis_spec != "custom/bifrost":
        custom_vis_model = body.settings.get("vision_custom_model_id")
        if custom_vis_model is None:
            custom_vis_model = await svc.get("vision_custom_model_id")
        custom_vis_url = body.settings.get("vision_base_url")
        if custom_vis_url is None:
            custom_vis_url = await svc.get("vision_base_url")

        if not custom_vis_model or not custom_vis_model.strip():
            raise HTTPException(status_code=400, detail="Custom Vision Model ID/Name cannot be empty.")
        if not custom_vis_url or not custom_vis_url.strip():
            raise HTTPException(status_code=400, detail="Custom Vision Base URL cannot be empty.")
    elif active_vis_spec == "custom/bifrost":
        bifrost_vis_model = body.settings.get("vision_bifrost_model_id")
        if bifrost_vis_model is None:
            bifrost_vis_model = await svc.get("vision_bifrost_model_id")
        bifrost_vis_url = body.settings.get("vision_bifrost_base_url")
        if bifrost_vis_url is None:
            bifrost_vis_url = await svc.get("vision_bifrost_base_url")

        if not bifrost_vis_model or not bifrost_vis_model.strip():
            raise HTTPException(status_code=400, detail="Bifrost Vision Model ID cannot be empty.")
        if not bifrost_vis_url or not bifrost_vis_url.strip():
            raise HTTPException(status_code=400, detail="Bifrost Vision Base URL cannot be empty.")

    results = await svc.set_batch(body.settings)
    
    # Audit log
    keys_updated = list(body.settings.keys())
    await log_audit(db, _user, "update", "settings", "global", reason=f"Updated keys: {', '.join(keys_updated)}")
    await db.commit()
    return {"updated": results}


# ---------------------------------------------------------------------------
# Provider connection testing
# ---------------------------------------------------------------------------

@router.post("/settings/test-providers", response_model=dict[str, TestConnectionResult])
async def test_all_providers(db: AsyncSession = Depends(get_db)):
    """Test all configured AI providers (embedding, LLM, vision)."""
    from app.ai.registry import ProviderRegistry

    registry = ProviderRegistry(db)
    results = await registry.test_all()

    return {
        capability: TestConnectionResult(success=ok, message=msg)
        for capability, (ok, msg) in results.items()
    }


@router.post("/settings/test-embedding", response_model=TestConnectionResult)
async def test_embedding(db: AsyncSession = Depends(get_db)):
    """Test the configured embedding provider."""
    from app.ai.registry import ProviderRegistry

    try:
        registry = ProviderRegistry(db)
        provider = await registry.get_embedding()
        ok, msg = await provider.test_connection()
        return TestConnectionResult(success=ok, message=msg)
    except Exception as e:
        return TestConnectionResult(success=False, message=str(e))


@router.post("/settings/test-llm", response_model=TestConnectionResult)
async def test_llm(db: AsyncSession = Depends(get_db)):
    """Test the configured LLM provider."""
    from app.ai.registry import ProviderRegistry

    try:
        registry = ProviderRegistry(db)
        provider = await registry.get_llm()
        ok, msg = await provider.test_connection()
        return TestConnectionResult(success=ok, message=msg)
    except Exception as e:
        return TestConnectionResult(success=False, message=str(e))


@router.post("/settings/test-vision", response_model=TestConnectionResult)
async def test_vision(db: AsyncSession = Depends(get_db)):
    """Test the configured vision provider."""
    from app.ai.registry import ProviderRegistry

    try:
        registry = ProviderRegistry(db)
        provider = await registry.get_vision()
        if not provider:
            return TestConnectionResult(success=False, message="No vision provider configured")
        ok, msg = await provider.test_connection()
        return TestConnectionResult(success=ok, message=msg)
    except Exception as e:
        return TestConnectionResult(success=False, message=str(e))


# ---------------------------------------------------------------------------
# Supported providers list (for admin UI dropdowns)
# ---------------------------------------------------------------------------

@router.get("/settings/providers")
async def list_providers():
    """
    Catalog-derived listing of supported providers per capability. Each model
    entry includes spec_id, label, cost, and capability metadata so the UI can
    render rich dropdowns.
    """
    from app.ai.registry import supported_providers
    return supported_providers()
