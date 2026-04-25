from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class ActionType(enum.Enum):
    EMAIL_INITIAL = "email_initial"
    EMAIL_FOLLOWUP = "email_followup"
    EMAIL_HOSTING = "email_hosting"
    EMAIL_REGISTRAR = "email_registrar"
    MANUAL_ESCALATION = "manual_escalation"
    CHECK_REMOVAL = "check_removal"


class ActionStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class Action(Base):
    __tablename__ = "actions"

    # Append-only table - no updates allowed via trigger
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)
    type = Column(Enum(ActionType), nullable=False)
    payload = Column(JSON, nullable=True)  # Email content, metadata, etc.
    status = Column(Enum(ActionStatus), default=ActionStatus.PENDING, nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)  # Admin user who approved
    error_message = Column(Text, nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    target = relationship("Target", back_populates="actions")