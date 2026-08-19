from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, default="Dev log")

    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author = relationship("User")

    created_at = Column(DateTime, default=datetime.utcnow)
