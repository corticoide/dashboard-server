from pydantic import BaseModel
from datetime import datetime


class MetricsSnapshotOut(BaseModel):
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    disk_percent: float
    disk_used_gb: float

    class Config:
        from_attributes = True
