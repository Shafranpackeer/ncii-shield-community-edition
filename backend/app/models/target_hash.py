from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, JSON, Float, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class TargetHash(Base):
    __tablename__ = "target_hashes"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False)
    image_url = Column(Text, nullable=False)
    phash = Column(BigInteger, nullable=False, index=True)
    dhash = Column(BigInteger, nullable=False, index=True)
    face_embedding = Column(JSON, nullable=True)
    match_against_ref_id = Column(Integer, ForeignKey("reference_hashes.id"), nullable=True)
    match_score = Column(Float, nullable=True)  # Combined match confidence 0.0-1.0
    match_type = Column(String(50), nullable=True)  # strong_phash, dhash, face, combined
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    target = relationship("Target", back_populates="hashes")
    reference_hash = relationship("ReferenceHash", back_populates="matched_targets")