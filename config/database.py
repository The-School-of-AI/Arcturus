import os
from contextlib import contextmanager
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine

# Use the same data directory as Qdrant/Neo4j for local storage
DATA_DIR = os.environ.get("MNEMO_DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

# Define SQLite database URL
SQLITE_DB_PATH = os.path.join(DATA_DIR, "auth.db")
DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# Create engine
# connect_args={"check_same_thread": False} is required for SQLite to be used across threads in FastAPI
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    """Initialize the database. Creates all tables registered with SQLModel."""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with Session(engine) as session:
        yield session

@contextmanager
def get_session_context() -> Generator[Session, None, None]:
    """Context manager for database sessions when outside of FastAPI requests."""
    with Session(engine) as session:
        yield session
