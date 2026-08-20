import json
import re
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models_resource import Resource
from app.moderation import moderate_resource
from app.schemas import ResourceCreate, ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])


def _slug(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:180] or "resource"
    return f"{base}-{secrets.token_hex(3)}"


def _to_out(resource: Resource) -> dict:
    return {
        "id": resource.id,
        "slug": resource.slug,
        "name": resource.name,
        "summary": resource.summary,
        "description": resource.description,
        "kind": resource.kind,
        "minecraft_version": resource.minecraft_version,
        "loader": resource.loader,
        "release_version": resource.release_version,
        "file_name": resource.file_name,
        "file_size": resource.file_size,
        "status": resource.status,
        "moderation_reason": resource.moderation_reason,
        "moderation_confidence": float(resource.moderation_confidence)
        if resource.moderation_confidence
        else None,
        "moderation_tags": json.loads(resource.moderation_tags or "[]"),
        "created_at": resource.created_at,
        "author": resource.author,
    }


@router.get("", response_model=list[ResourceOut])
def list_public_resources(db: Session = Depends(get_db)):
    resources = (
        db.query(Resource)
        .filter(Resource.status == "approved")
        .order_by(desc(Resource.created_at))
        .limit(50)
        .all()
    )
    return [_to_out(resource) for resource in resources]


@router.get("/mine", response_model=list[ResourceOut])
def list_my_resources(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    resources = (
        db.query(Resource)
        .filter(Resource.author_id == current_user.id)
        .order_by(desc(Resource.created_at))
        .all()
    )
    return [_to_out(resource) for resource in resources]


@router.post("", response_model=ResourceOut)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = Resource(
        slug=_slug(payload.name),
        name=payload.name,
        summary=payload.summary,
        description=payload.description,
        kind=payload.kind,
        minecraft_version=payload.minecraft_version,
        loader=payload.loader,
        release_version=payload.release_version,
        file_name=payload.file_name,
        file_size=payload.file_size,
        author_id=current_user.id,
        status="pending",
    )
    db.add(resource)
    db.flush()
    moderation = moderate_resource(payload.model_dump())
    resource.status = moderation["status"]
    resource.moderation_reason = moderation["reason"]
    resource.moderation_confidence = (
        str(moderation["confidence"]) if moderation["confidence"] is not None else None
    )
    resource.moderation_tags = json.dumps(moderation["suggested_tags"])
    db.commit()
    db.refresh(resource)
    return _to_out(resource)
