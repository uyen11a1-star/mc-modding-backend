from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    summary = Column(String(220), nullable=False)
    description = Column(Text, nullable=False)
    kind = Column(String(32), nullable=False)
    minecraft_version = Column(String(32), nullable=False)
    loader = Column(String(32), nullable=False)
    release_version = Column(String(64), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    moderation_reason = Column(Text, nullable=True)
    moderation_confidence = Column(String(16), nullable=True)
    moderation_tags = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    author = relationship("User")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
