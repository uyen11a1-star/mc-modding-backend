from pydantic import BaseModel, EmailStr
from datetime import datetime


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
