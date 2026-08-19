from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.models_post import Post
from app.schemas import (
    BackupExport,
    BackupPost,
    BackupProfile,
    RestoreRequest,
    RestoreResponse,
)

router = APIRouter(prefix="/account", tags=["account"])
BACKUP_SCHEMA_VERSION = "modden-backup-v1"


def _validate_avatar_url(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Avatar URL must use http or https")
    return value


@router.get("/backup", response_model=BackupExport)
def export_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    posts = (
        db.query(Post)
        .filter(Post.author_id == current_user.id)
        .order_by(asc(Post.created_at), asc(Post.id))
        .limit(1000)
        .all()
    )
    return BackupExport(
        schema_version=BACKUP_SCHEMA_VERSION,
        exported_at=datetime.utcnow(),
        profile=BackupProfile(
            name=current_user.name,
            avatar_url=current_user.avatar_url,
        ),
        posts=[
            BackupPost(
                title=post.title,
                content=post.content,
                category=post.category,
                created_at=post.created_at,
            )
            for post in posts
        ],
    )


@router.post("/restore", response_model=RestoreResponse)
def restore_backup(
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile_updated = False
    profile = payload.backup.profile
    try:
        if profile.name is not None and profile.name != current_user.name:
            current_user.name = profile.name
            profile_updated = True

        avatar_url = _validate_avatar_url(profile.avatar_url)
        if avatar_url != current_user.avatar_url:
            current_user.avatar_url = avatar_url
            profile_updated = True

        restored_posts = [
            Post(
                title=post.title,
                content=post.content,
                category=post.category,
                created_at=post.created_at,
                author_id=current_user.id,
            )
            for post in payload.backup.posts
        ]
        if restored_posts:
            db.add_all(restored_posts)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RestoreResponse(
        restored_posts=len(restored_posts),
        profile_updated=profile_updated,
    )
