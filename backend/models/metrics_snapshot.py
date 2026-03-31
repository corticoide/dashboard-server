from sqlalchemy import Column, Integer, Float, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    cpu_percent = Column(Float, nullable=False)
    ram_percent = Column(Float, nullable=False)
    ram_used_gb = Column(Float, nullable=False)
    disk_percent = Column(Float, nullable=False)
    disk_used_gb = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_metrics_snapshots_timestamp", "timestamp"),
    )
