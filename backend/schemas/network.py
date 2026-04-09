from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InterfaceInfo(BaseModel):
    name: str
    ip: str
    mac: str
    is_up: Optional[bool] = None
    speed_mbps: Optional[int] = None
    bytes_sent: float
    bytes_recv: float
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int
    is_internet_gateway: bool = False
    subnet: str = ""


class ConnectionInfo(BaseModel):
    proto: str
    local_addr: str
    remote_addr: str
    status: str
    pid: Optional[int] = None


class ConnectionSummary(BaseModel):
    counts: dict[str, int]


class BandwidthPoint(BaseModel):
    timestamp: datetime
    interface: str
    bytes_sent: float
    bytes_recv: float

    class Config:
        from_attributes = True


class NetworkSnapshotOut(BaseModel):
    id: int
    timestamp: datetime
    interface: str
    bytes_sent: float
    bytes_recv: float
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int

    class Config:
        from_attributes = True
