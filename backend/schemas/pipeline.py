from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PipelineStepIn(BaseModel):
    name: str
    step_type: str          # "script" | "shell" | "module"
    config: dict = {}
    on_success: str = "continue"
    on_failure: str = "stop"
    order: int = 0


class PipelineStepOut(BaseModel):
    id: int
    pipeline_id: int
    order: int
    name: str
    step_type: str
    config: dict
    on_success: str
    on_failure: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_step(cls, s) -> "PipelineStepOut":
        import json
        return cls(
            id=s.id,
            pipeline_id=s.pipeline_id,
            order=s.order,
            name=s.name,
            step_type=s.step_type,
            config=json.loads(s.config or "{}"),
            on_success=s.on_success,
            on_failure=s.on_failure,
        )


class PipelineIn(BaseModel):
    name: str
    description: str = ""
    steps: List[PipelineStepIn] = []


class PipelineOut(BaseModel):
    id: int
    name: str
    description: str
    step_count: int
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineDetailOut(BaseModel):
    id: int
    name: str
    description: str
    steps: List[PipelineStepOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineStepRunOut(BaseModel):
    id: int
    run_id: int
    step_id: int
    step_order: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    output: str
    status: str

    model_config = {"from_attributes": True}


class PipelineRunOut(BaseModel):
    id: int
    pipeline_id: int
    triggered_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str

    model_config = {"from_attributes": True}


class PipelineRunDetailOut(BaseModel):
    id: int
    pipeline_id: int
    triggered_by: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    step_runs: List[PipelineStepRunOut]

    model_config = {"from_attributes": True}
