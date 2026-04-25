from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReferenceHash(Base):
    __tablename__ = "reference_hashes"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    phash = Column(BigInteger, nullable=False, index=True)  # 64-bit perceptual hash
    dhash = Column(BigInteger, nullable=False, index=True)  # 64-bit difference hash
    face_embedding = Column(JSON, nullable=True)  # 128-dim vector as JSON array
    label = Column(String(255), nullable=True)  # Optional label for the reference
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    case = relationship("Case", back_populates="reference_hashes")
    matched_targets = relationship("TargetHash", back_populates="reference_hash")