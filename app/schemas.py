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
