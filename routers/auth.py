from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
import uuid
from typing import Optional

from config.database import get_session
from memory.models.user import User, AuthType
from core.auth.security import verify_password, get_password_hash, create_access_token, is_jwt_configured, AUTH_NOT_CONFIGURED_MSG
from core.auth.context import get_current_user_id

import traceback

router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    guest_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    guest_id: Optional[str] = None

class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    first_name: Optional[str] = None
    email: Optional[str] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    email: Optional[str] = None
    auth_type: AuthType

# Import migration logic
from memory.auth.migration import migrate_guest_to_registered

@router.post("/register", response_model=TokenOutput)
async def register(user_data: UserCreate, db: Session = Depends(get_session)):
    if not is_jwt_configured():
        raise HTTPException(status_code=503, detail=AUTH_NOT_CONFIGURED_MSG)
    # 1. Check if email already exists
    statement = select(User).where(User.email == user_data.email)
    existing_user = db.exec(statement).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    # 2. Hash password and create User
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        auth_type=AuthType.registered,
        migrated_guest_ids=[] # Initialize empty migrations array
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 3. Handle Guest Migration
    if user_data.guest_id:
        try:
            # Check UUID validity
            gid_str = str(user_data.guest_id)
            clean_guest_id = gid_str.replace("guest_", "") if gid_str.startswith("guest_") else gid_str
            guest_uuid = uuid.UUID(clean_guest_id)
            migration_success = await migrate_guest_to_registered(guest_uuid, new_user.id)
            if migration_success:
                new_user.migrated_guest_ids = list(new_user.migrated_guest_ids or []) + [str(guest_uuid)]
                db.add(new_user)
                db.commit()
                print(f"✅ Migrated guest data: {guest_uuid} -> {new_user.id}")
            else:
                print(f"⚠️ Migration failed for guest: {guest_uuid}")
        except ValueError:
            pass # Invalid UUID passed gracefully ignored
        except Exception as e:
            traceback.print_exc()
            print(f"Migration mapping failed: {e}")
            
    # 4. Generate JWT
    token_data = {"sub": str(new_user.id), "email": new_user.email}
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token, 
        "user_id": str(new_user.id),
        "first_name": new_user.first_name,
        "email": new_user.email
    }


@router.post("/login", response_model=TokenOutput)
async def login(user_data: UserLogin, db: Session = Depends(get_session)):
    if not is_jwt_configured():
        raise HTTPException(status_code=503, detail=AUTH_NOT_CONFIGURED_MSG)
    # 1. Fetch user by email
    statement = select(User).where(User.email == user_data.email)
    user = db.exec(statement).first()
    
    # 2. Verify account and password
    if not user or not user.password_hash or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Handle Guest Migration 
    if user_data.guest_id:
        try:
            gid_str = str(user_data.guest_id)
            clean_guest_id = gid_str.replace("guest_", "") if gid_str.startswith("guest_") else gid_str
            guest_uuid = uuid.UUID(clean_guest_id)
            # Idempotency check
            migrated_list = user.migrated_guest_ids or []
            # Note: SQLite JSON lists often return strings if not mapped strictly 
            # so stringify for robust checking
            str_list = [str(gid) for gid in migrated_list]
            if str(guest_uuid) not in str_list:
                migration_success = await migrate_guest_to_registered(guest_uuid, user.id)
                if migration_success:
                    user.migrated_guest_ids = migrated_list + [str(guest_uuid)]
                    db.add(user)
                    db.commit()
                    print(f"✅ Migrated guest data on login: {guest_uuid} -> {user.id}")
        except ValueError:
            pass
            
    # 4. Generate JWT
    token_data = {"sub": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token, 
        "user_id": str(user.id),
        "first_name": user.first_name,
        "email": user.email
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(db: Session = Depends(get_session)):
    user_id_str = get_current_user_id()
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format in token or header")
        
    user = db.get(User, user_uuid)
    
    # If using just X-User-Id header as a guest for the first time, 
    # the user record might not exist in SQLite yet, just return the Guest representation.
    if not user:
        return UserResponse(
            id=user_uuid, 
            auth_type=AuthType.guest
        )
        
    return UserResponse(
        id=user.id,
        email=user.email,
        auth_type=user.auth_type
    )

@router.get("/legacy-guest-id")
async def get_legacy_guest_id():
    """
    Returns the legacy fallback offline user_id from user_id.json if it exists.
    If it doesn't exist, we return null so the frontend knows to gracefully fall back
    to generating its own random guest ID.
    """
    from memory.user_id import _USER_ID_PATH
    import json
    
    if _USER_ID_PATH.exists():
        try:
            data = json.loads(_USER_ID_PATH.read_text())
            uid = data.get("user_id")
            if uid:
                return {"guest_id": uid}
        except Exception:
            pass
            
    return {"guest_id": None}
