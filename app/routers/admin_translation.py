"""Admin endpoint for backfilling translations on existing wiki pages."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth_service import require_admin
from app.worker import get_arq_pool

router = APIRouter(prefix="/admin", tags=["admin"])


class TranslateBackfillRequest(BaseModel):
    scope_type: str
    scope_id: Optional[str] = None
    target_language: str
    page_ids: Optional[list[str]] = None
    force: bool = False


@router.post("/translate-pages")
async def translate_pages(
    body: TranslateBackfillRequest,
    _admin=Depends(require_admin),
):
    """Queue a backfill translation job for all matching pages in a scope.

    Returns immediately with the arq job_id; progress can be observed in the
    worker log (`Translation backfill: …`).
    """
    if body.scope_type not in ("global", "department", "project"):
        raise HTTPException(status_code=400, detail="Invalid scope_type")
    if not body.target_language or len(body.target_language) > 8:
        raise HTTPException(status_code=400, detail="Invalid target_language")

    pool = await get_arq_pool()
    job = await pool.enqueue_job(
        "backfill_translate_pages_task",
        body.scope_type,
        body.scope_id,
        body.target_language,
        body.page_ids,
        body.force,
    )
    return {"queued": True, "job_id": job.job_id if job else None}
