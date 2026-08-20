from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    avatar_url: str | None
    provider: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PostCreate(BaseModel):
    title: str
    content: str
    category: str = "Dev log"


class PostAuthor(BaseModel):
    id: int
    name: str | None
    email: str
    avatar_url: str | None

    class Config:
        from_attributes = True


class PostOut(BaseModel):
    id: int
    title: str
    content: str
    category: str
    created_at: datetime
    author: PostAuthor

    class Config:
        from_attributes = True


class BackupProfile(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=2048)


class BackupPost(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=20000)
    category: str = Field(default="Dev log", min_length=1, max_length=64)
    created_at: datetime


class BackupDocument(BaseModel):
    schema_version: Literal["modden-backup-v1"]
    exported_at: datetime
    profile: BackupProfile
    posts: list[BackupPost] = Field(default_factory=list, max_length=1000)


class BackupExport(BackupDocument):
    pass


class RestoreRequest(BaseModel):
    backup: BackupDocument


class RestoreResponse(BaseModel):
    restored_posts: int
    profile_updated: bool


ResourceKind = Literal["Mod", "Resource Pack", "Shader Pack", "Datapack", "Plugin", "Modpack"]


class ResourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=10, max_length=220)
    description: str = Field(min_length=20, max_length=20000)
    kind: ResourceKind
    minecraft_version: str = Field(min_length=2, max_length=32)
    loader: str = Field(min_length=2, max_length=32)
    release_version: str = Field(min_length=1, max_length=64)
    file_name: str = Field(pattern=r"^.+\.(jar|zip|mrpack)$", max_length=255)
    file_size: int = Field(gt=0, le=500 * 1024 * 1024)


class ResourceUploadInit(ResourceCreate):
    pass


class ResourceOut(BaseModel):
    id: int
    slug: str
    name: str
    summary: str
    description: str
    kind: ResourceKind
    minecraft_version: str
    loader: str
    release_version: str
    file_name: str
    file_size: int
    upload_state: str
    download_count: int
    can_download: bool
    status: Literal["pending", "approved", "rejected"]
    moderation_reason: str | None
    moderation_confidence: float | None
    moderation_tags: list[str]
    created_at: datetime
    author: PostAuthor


class ResourceUploadInitOut(ResourceOut):
    upload_url: str
    upload_content_type: str
    upload_expires_in: int
