import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# check_same_thread is only needed for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_resource_storage_columns():
    """Add nullable R2 metadata columns to existing deployments without dropping data."""
    if "resources" not in inspect(engine).get_table_names():
        return
    existing = {column["name"] for column in inspect(engine).get_columns("resources")}
    additions = {
        "file_key": "VARCHAR(512)",
        "upload_state": "VARCHAR(24) NOT NULL DEFAULT 'metadata_only'",
        "file_uploaded_at": "TIMESTAMP NULL",
        "download_count": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE resources ADD COLUMN {column} {definition}"))
