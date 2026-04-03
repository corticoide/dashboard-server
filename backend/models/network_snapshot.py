from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from sqlalchemy.sql import func
from backend.database import Base


class NetworkSnapshot(Base):
    __tablename__ = "network_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    interface = Column(String, nullable=False)
    bytes_sent = Column(Float, nullable=False)
    bytes_recv = Column(Float, nullable=False)
    packets_sent = Column(Integer, nullable=False)
    packets_recv = Column(Integer, nullable=False)
    errin = Column(Integer, nullable=False, default=0)
    errout = Column(Integer, nullable=False, default=0)
    dropin = Column(Integer, nullable=False, default=0)
    dropout = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_network_snapshots_timestamp", "timestamp"),
        Index("ix_network_snapshots_interface", "interface"),
        Index("ix_network_snapshots_interface_timestamp", "interface", "timestamp"),
    )
