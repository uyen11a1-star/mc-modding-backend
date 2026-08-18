from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Null when the account was created via OAuth only (no password set)
    hashed_password = Column(String, nullable=True)

    # "local", "google", or "github" — records how the account was created
    provider = Column(String, default="local")
    provider_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
