from sqlalchemy import Column, Integer, String, Enum, Index
from backend.database import Base
from backend.models.user import UserRole


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(UserRole), nullable=False)
    resource = Column(String, nullable=False)
    action = Column(String, nullable=False)

    __table_args__ = (
        Index("ix_permissions_role", "role"),
        Index("ix_permissions_role_resource", "role", "resource"),
    )
