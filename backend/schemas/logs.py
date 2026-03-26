from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ExecutionLogOut(BaseModel):
    id: int
    script_path: str
    username: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    duration_seconds: Optional[float] = None
    output_summary: Optional[str] = None

    class Config:
        from_attributes = True


class ExecutionStatsOut(BaseModel):
    total: int
    success: int
    failed: int
    last_24h: int
