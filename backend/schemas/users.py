from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "readonly"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class PermissionOut(BaseModel):
    resource: str
    action: str

    class Config:
        from_attributes = True


class MeOut(BaseModel):
    id: int
    username: str
    role: str
    permissions: List[PermissionOut]
