from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)
    email = Column(String(255), nullable=False)
    method_found = Column(String(255), nullable=True)  # e.g., "dmca_page", "footer", "whois", "abuse_form"
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    target = relationship("Target", back_populates="contacts")