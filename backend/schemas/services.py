from pydantic import BaseModel
from typing import List

class ServiceInfo(BaseModel):
    name: str
    load_state: str
    active_state: str
    sub_state: str
    description: str
    enabled: str

class ServiceLog(BaseModel):
    service: str
    lines: List[str]
