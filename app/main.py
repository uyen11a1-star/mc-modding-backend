import os
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import Base, engine
from app.routers import auth

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Minecraft Modding Community API")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),
)

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5500")
_parsed = urlparse(_frontend_url)
FRONTEND_ORIGIN = f"{_parsed.scheme}://{_parsed.netloc}"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "mc-modding-backend"}
