from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.sql import func

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    # Append-only table - no updates or deletes allowed via trigger
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(100), nullable=False, index=True)  # e.g., "case", "target", "action"
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., "created", "status_changed", "approved"
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    user_id = Column(String(255), nullable=True)  # Who performed the action
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)