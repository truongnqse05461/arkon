"""Mindmap router — GET cached mindmap, POST generate, DELETE."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
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
    generated_at: datetime

    model_config = {"from_attributes": True}


class MindmapSummaryResponse(BaseModel):
    id: uuid.UUID
    scope_type: str
    scope_id: Optional[uuid.UUID]
    title: str
    source_type: str
    wiki_page_count: int
    generated_at: datetime

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    scope_type: Literal["global", "department", "project"]
    scope_id: Optional[uuid.UUID] = None
    source_type: Literal["wiki", "source_docs"] = "wiki"
    source_ids: Optional[list[uuid.UUID]] = None
    instruction: Optional[str] = None

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 500:
            raise ValueError("Instruction must be 500 characters or less")
        return v

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, v: Optional[list[uuid.UUID]], info) -> Optional[list[uuid.UUID]]:
        if info.data.get("source_type") == "source_docs" and not v:
            raise ValueError("source_ids required when source_type is 'source_docs'")
        return v


@router.get("/mindmaps", response_model=list[MindmapSummaryResponse])
async def list_mindmaps_endpoint(
    scope_type: Optional[str] = None,
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmaps = await mindmap_service.list_mindmaps(db, scope_type=scope_type, scope_id=scope_id)
    return mindmaps


@router.get("/mindmap", response_model=MindmapResponse)
async def get_mindmap_endpoint(
    scope_type: Literal["global", "department", "project"] = "global",
    scope_id: Optional[uuid.UUID] = None,
    source_type: Literal["wiki", "source_docs"] = "wiki",
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmap = await mindmap_service.get_mindmap(db, scope_type, scope_id, source_type)
    if not mindmap:
        raise HTTPException(status_code=404, detail="No MindMap for this scope yet.")
    return mindmap


@router.get("/mindmap/{mindmap_id}", response_model=MindmapResponse)
async def get_mindmap_by_id_endpoint(
    mindmap_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    mindmap = await mindmap_service.get_mindmap_by_id(db, mindmap_id)
    if not mindmap:
        raise HTTPException(status_code=404, detail="MindMap not found.")
    return mindmap


@router.post("/mindmap/generate", response_model=MindmapResponse)
async def generate_mindmap_endpoint(
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    try:
        mindmap = await mindmap_service.generate_mindmap(
            db,
            body.scope_type,
            body.scope_id,
            source_type=body.source_type,
            source_ids=body.source_ids,
            instruction=body.instruction,
        )
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
