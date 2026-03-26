from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class FavoriteCreate(BaseModel):
    path: str


class FavoriteUpdate(BaseModel):
    run_as_root: Optional[bool] = None
    admin_only: Optional[bool] = None


class FavoriteOut(BaseModel):
    id: int
    path: str
    run_as_root: bool
    admin_only: bool
    runner: str
    exists: bool

    class Config:
        from_attributes = True


class RunRequest(BaseModel):
    sudo_password: Optional[str] = None
    args: Optional[List[str]] = []


class ExecutionOut(BaseModel):
    id: int
    script_path: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    output: str
    run_as_root: bool
    triggered_by: Optional[str] = None
    running: bool = False

    class Config:
        from_attributes = True


class ExecutionPoll(BaseModel):
    id: int
    running: bool
    exit_code: Optional[int] = None
    lines: List[str]
