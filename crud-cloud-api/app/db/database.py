"""SQLAlchemy session + engine helpers for the SQLite backing store."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


settings = get_settings()
db_path = settings.sqlite_path
db_dir = os.path.dirname(db_path)
if db_dir:
    # Docker volumes sometimes start empty, so create the parent dir when needed.
    os.makedirs(db_dir, exist_ok=True)
DATABASE_URL = f"sqlite:///{db_path}"
# SQLite needs `check_same_thread=False` so FastAPI can share the connection.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Yield a transactional session and guarantee cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
