from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReviewThumbnail(Base):
    """
    Temporary thumbnails for admin review.

    These are created during confirmation and deleted after review
    or when they expire.
    """
    __tablename__ = "review_thumbnails"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False, index=True)
    image_url = Column(String(2048), nullable=False)
    thumbnail_blob = Column(LargeBinary, nullable=False)  # JPEG bytes
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    target = relationship("Target")