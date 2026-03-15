from datetime import datetime, timezone
import uuid
from typing import Optional, List
from enum import Enum
from sqlmodel import Field, SQLModel, JSON

class AuthType(str, Enum):
    guest = "guest"
    registered = "registered"

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    # Primary Key - explicitly setting default_factory
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    
    # Auth specifics
    auth_type: AuthType = Field(default=AuthType.guest)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None, index=True, sa_column_kwargs={"unique": True})
    password_hash: Optional[str] = Field(default=None)
    
    # Track migrated guests to ensure idempotency across multiple devices
    # List of UUIDs translated into JSON by SQLModel/SQLAlchemy
    migrated_guest_ids: Optional[List[uuid.UUID]] = Field(default=None, sa_type=JSON)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
