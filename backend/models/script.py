from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from backend.database import Base


class ScriptFavorite(Base):
    __tablename__ = "script_favorites"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, nullable=False, index=True)
    run_as_root = Column(Boolean, default=False, nullable=False)
    admin_only = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ScriptExecution(Base):
    __tablename__ = "script_executions"

    id = Column(Integer, primary_key=True, index=True)
    script_path = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    exit_code = Column(Integer, nullable=True)
    output = Column(Text, default="")
    run_as_root = Column(Boolean, default=False)
    triggered_by = Column(String, nullable=True)
    is_running = Column(Boolean, default=True, nullable=False)
