from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True, index=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
