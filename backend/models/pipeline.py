import json
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False)
    order = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    step_type = Column(String, nullable=False)   # "script" | "shell" | "module"
    config = Column(Text, default="{}")          # JSON string
    on_success = Column(String, default="continue")  # "continue" | "stop"
    on_failure = Column(String, default="stop")      # "continue" | "stop"

    __table_args__ = (
        Index("ix_pipeline_steps_pipeline_id", "pipeline_id"),
    )

    @property
    def config_dict(self) -> dict:
        return json.loads(self.config or "{}")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False)
    triggered_by = Column(String, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # "running" | "success" | "failed"

    __table_args__ = (
        Index("ix_pipeline_runs_pipeline_id", "pipeline_id"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )


class PipelineStepRun(Base):
    __tablename__ = "pipeline_step_runs"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, nullable=False)
    step_id = Column(Integer, nullable=False)
    step_order = Column(Integer, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    status = Column(String, default="running")  # "running" | "skipped" | "success" | "failed"

    __table_args__ = (
        Index("ix_pipeline_step_runs_run_id", "run_id"),
    )
