import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import SignupRequest, LoginRequest, TokenResponse, UserOut
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.oauth import oauth

router = APIRouter(prefix="/auth", tags=["auth"])

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "https://uyen11a1-star.github.io/minecraft-modding-hub/",
)


# ---------------- Email + password ----------------

@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    user = User(
        email=payload.email,
        name=payload.name or payload.email.split("@")[0],
        hashed_password=hash_password(payload.password),
        provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------- Google OAuth ----------------

@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        raise HTTPException(status_code=400, detail="Google did not return an email")

    user = _get_or_create_oauth_user(
        db,
        email=userinfo["email"],
        name=userinfo.get("name"),
        avatar_url=userinfo.get("picture"),
        provider="google",
        provider_id=userinfo.get("sub"),
    )
    jwt_token = create_access_token(user.id)
    return RedirectResponse(f"{FRONTEND_URL}?token={jwt_token}")


# ---------------- GitHub OAuth ----------------

@router.get("/github/login")
async def github_login(request: Request):
    redirect_uri = request.url_for("github_callback")
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/github/callback", name="github_callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    profile = (await oauth.github.get("user", token=token)).json()

    email = profile.get("email")
    if not email:
        # GitHub often hides the primary email; fetch it explicitly.
        emails = (await oauth.github.get("user/emails", token=token)).json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = primary["email"] if primary else (emails[0]["email"] if emails else None)

    if not email:
        raise HTTPException(status_code=400, detail="GitHub did not return an email")

    user = _get_or_create_oauth_user(
        db,
        email=email,
        name=profile.get("name") or profile.get("login"),
        avatar_url=profile.get("avatar_url"),
        provider="github",
        provider_id=str(profile.get("id")),
    )
    jwt_token = create_access_token(user.id)
    return RedirectResponse(f"{FRONTEND_URL}?token={jwt_token}")


# ---------------- shared helper ----------------

def _get_or_create_oauth_user(
    db: Session, *, email: str, name: str | None, avatar_url: str | None,
    provider: str, provider_id: str | None,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        email=email,
        name=name or email.split("@")[0],
        avatar_url=avatar_url,
        provider=provider,
        provider_id=provider_id,
        hashed_password=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
