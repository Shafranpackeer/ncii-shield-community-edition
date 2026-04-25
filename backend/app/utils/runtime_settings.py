"""Read runtime settings from the database with environment fallbacks."""

import os
from typing import Optional

from app.db.session import SessionLocal
from app.models.app_setting import AppSetting


def get_runtime_setting(key: str, default: Optional[str] = None, db=None) -> Optional[str]:
    if db is None:
        session = SessionLocal()
        close_session = True
    else:
        session = db
        close_session = False

    try:
        try:
            row = session.query(AppSetting).filter(AppSetting.key == key).first()
            if row and row.value is not None:
                return row.value
        except Exception:
            if hasattr(session, "rollback"):
                session.rollback()
        return os.getenv(key, default)
    finally:
        if close_session:
            session.close()
