from pydantic import BaseModel
from typing import Optional


class CrontabEntry(BaseModel):
    id: int  # Position in parsed list (0-indexed)
    minute: str = '*'
    hour: str = '*'
    dom: str = '*'   # day of month
    month: str = '*'
    dow: str = '*'   # day of week
    command: str = ''
    comment: Optional[str] = None
    is_special: bool = False
    special: Optional[str] = None   # @reboot, @daily, etc.
    raw: str = ''
    enabled: bool = True


class CrontabEntryCreate(BaseModel):
    minute: str = '*'
    hour: str = '*'
    dom: str = '*'
    month: str = '*'
    dow: str = '*'
    command: str
    comment: Optional[str] = None
    is_special: bool = False
    special: Optional[str] = None
