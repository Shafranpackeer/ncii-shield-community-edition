from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class CaseStatus(enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUSPENDED = "suspended"


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    victim_id = Column(String(255), nullable=False)
    status = Column(Enum(CaseStatus), default=CaseStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    authorization_doc = Column(Text, nullable=True)  # Path or reference to authorization document

    # Relationships
    reference_hashes = relationship("ReferenceHash", back_populates="case", cascade="all, delete-orphan")
    identifiers = relationship("Identifier", back_populates="case", cascade="all, delete-orphan")
    targets = relationship("Target", back_populates="case", cascade="all, delete-orphan")