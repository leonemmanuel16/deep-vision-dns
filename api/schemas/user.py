import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: str | None = None
    role: str = "operator"


class UserUpdate(BaseModel):
    email: str | None = None
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
