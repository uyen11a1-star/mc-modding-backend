import json
import re
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models_resource import Resource
from app.moderation import moderate_resource
from app.schemas import ResourceCreate, ResourceOut, ResourceUploadInit, ResourceUploadInitOut
from app.storage import PRESIGN_SECONDS, StorageUnavailable, create_download_url, create_upload_url, storage_key, uploaded_size

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
        "upload_state": resource.upload_state,
        "download_count": resource.download_count,
        "can_download": bool(
            resource.status == "approved" and resource.upload_state == "ready" and resource.file_key
        ),
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


@router.post("/uploads/init", response_model=ResourceUploadInitOut)
def init_resource_upload(
    payload: ResourceUploadInit,
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
        upload_state="uploading",
        moderation_reason="Waiting for the release file to finish uploading.",
    )
    db.add(resource)
    db.flush()
    resource.file_key = storage_key(current_user.id, resource.id, payload.file_name)
    try:
        upload_url, content_type = create_upload_url(resource.file_key, resource.file_name)
    except StorageUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    db.commit()
    db.refresh(resource)
    return _to_out(resource) | {
        "upload_url": upload_url,
        "upload_content_type": content_type,
        "upload_expires_in": PRESIGN_SECONDS,
    }


@router.post("/{resource_id}/uploads/complete", response_model=ResourceOut)
def complete_resource_upload(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = db.query(Resource).filter(Resource.id == resource_id, Resource.author_id == current_user.id).first()
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")
    if resource.upload_state != "uploading" or not resource.file_key:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This resource is not waiting for an upload.")
    try:
        if uploaded_size(resource.file_key) != resource.file_size:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file size did not match the requested release.")
    except StorageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    moderation = moderate_resource(
        {
            "name": resource.name,
            "summary": resource.summary,
            "description": resource.description,
            "kind": resource.kind,
            "minecraft_version": resource.minecraft_version,
            "loader": resource.loader,
            "release_version": resource.release_version,
            "file_name": resource.file_name,
            "file_size": resource.file_size,
        }
    )
    resource.upload_state = "ready"
    resource.file_uploaded_at = datetime.utcnow()
    resource.status = moderation["status"]
    resource.moderation_reason = moderation["reason"]
    resource.moderation_confidence = str(moderation["confidence"]) if moderation["confidence"] is not None else None
    resource.moderation_tags = json.dumps(moderation["suggested_tags"])
    db.commit()
    db.refresh(resource)
    return _to_out(resource)


@router.get("/{resource_id}/download")
def download_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource or resource.status != "approved" or resource.upload_state != "ready" or not resource.file_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This release is not available for download.")
    try:
        url = create_download_url(resource.file_key, resource.file_name)
    except StorageUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    resource.download_count += 1
    db.commit()
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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
        upload_state="metadata_only",
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
