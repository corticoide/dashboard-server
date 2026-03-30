from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    script_path = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    output_summary = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_execution_logs_started_at", "started_at"),
        Index("ix_execution_logs_username", "username"),
        Index("ix_execution_logs_exit_code", "exit_code"),
        Index("ix_execution_logs_username_started_at", "username", "started_at"),
    )
