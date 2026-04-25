from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class IdentifierType(enum.Enum):
    NAME = "name"
    HANDLE = "handle"
    ALIAS = "alias"
    EMAIL = "email"
    PHONE = "phone"


class Identifier(Base):
    __tablename__ = "identifiers"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    type = Column(Enum(IdentifierType), nullable=False)
    value = Column(String(500), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="identifiers")