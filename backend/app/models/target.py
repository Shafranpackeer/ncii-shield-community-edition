from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class TargetStatus(enum.Enum):
    DISCOVERED = "discovered"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    CONTACTED = "contacted"
    REMOVED = "removed"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class Target(Base):
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    url = Column(Text, nullable=False, unique=True)
    status = Column(Enum(TargetStatus), default=TargetStatus.DISCOVERED, nullable=False, index=True)
    discovery_source = Column(String(255), nullable=True)  # e.g., "bing_dork", "manual", "yandex_reverse"
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    next_action_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="targets")
    hashes = relationship("TargetHash", back_populates="target", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="target", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="target", cascade="all, delete-orphan")