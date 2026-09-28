"""
Pydantic schemas for user registration, login, and responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = Field(default="COMPLIANCE_ANALYST")


class UserLogin(BaseModel):
    """Schema for user login."""
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class FirebaseAuthSync(BaseModel):
    """Schema for syncing a Firebase authenticated user."""
    email: str
    full_name: Optional[str] = None
    firebase_uid: Optional[str] = None
    role: Optional[str] = "COMPLIANCE_ANALYST"


class UserResponse(BaseModel):
    """Schema for user data in API responses."""
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
