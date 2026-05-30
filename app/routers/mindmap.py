"""Mindmap router — GET cached mindmap, POST generate, DELETE."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database.models import Employee
from app.services import mindmap_service
from app.services.auth_service import get_current_user

router = APIRouter()


class MindmapResponse(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_id: Optional[uuid.UUID]
    title: str
    tree_json: dict
    wiki_page_count: int
    generated_at: str

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    scope_type: str
    scope_id: Optional[uuid.UUID] = None


@router.get("/mindmap", response_model=MindmapResponse)
async def get_mindmap_endpoint(
    scope_type: str = "global",
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmap = await mindmap_service.get_mindmap(db, scope_type, scope_id)
    if not mindmap:
        raise HTTPException(status_code=404, detail="No MindMap for this scope yet.")
    return mindmap


@router.post("/mindmap/generate", response_model=MindmapResponse)
async def generate_mindmap_endpoint(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    try:
        mindmap = await mindmap_service.generate_mindmap(db, body.scope_type, body.scope_id)
        await db.commit()
        return mindmap
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/mindmap/{mindmap_id}", status_code=204)
async def delete_mindmap_endpoint(
    mindmap_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    deleted = await mindmap_service.delete_mindmap(db, mindmap_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MindMap not found.")
    await db.commit()
