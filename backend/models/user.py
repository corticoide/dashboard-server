import enum
from sqlalchemy import Column, Integer, String, Enum
from backend.database import Base

class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    readonly = "readonly"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.readonly)
