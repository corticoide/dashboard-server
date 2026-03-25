from pydantic import BaseModel
from typing import List


class SystemMetrics(BaseModel):
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    uptime_seconds: int
    load_average: List[float]   # 1min, 5min, 15min
    os_name: str                # e.g. "Linux 6.6.87"
    hostname: str
    cpu_count: int
    cpu_arch: str               # e.g. "x86_64"
