"""Runtime settings endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config.settings_catalog import SETTINGS_CATALOG
from app.db.session import get_db
from app.models.app_setting import AppSetting

router = APIRouter(prefix="/config", tags=["config"])


class SettingValue(BaseModel):
    key: str
    value: str = ""


class SettingsPayload(BaseModel):
    settings: List[SettingValue]


class SettingsResponseItem(BaseModel):
    key: str
    label: str
    description: str
    category: str
    docs_url: Optional[str] = None
    secret: bool = False
    placeholder: Optional[str] = None
    value: str = ""
    updated_at: Optional[str] = None


@router.get("/settings")
async def list_settings(db: Session = Depends(get_db)):
    rows = {row.key: row for row in db.query(AppSetting).all()}
    settings: list[dict] = []
    for setting in SETTINGS_CATALOG:
        row = rows.get(setting.key)
        settings.append(
            {
                "key": setting.key,
                "label": setting.label,
                "description": setting.description,
                "category": setting.category,
                "docs_url": setting.docs_url,
                "secret": setting.secret,
                "placeholder": setting.placeholder,
                "value": row.value if row else "",
                "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            }
        )
    return {"settings": settings}


@router.post("/settings")
async def save_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    known_keys = {setting.key for setting in SETTINGS_CATALOG}
    for item in payload.settings:
        if item.key not in known_keys:
            continue
        row = db.query(AppSetting).filter(AppSetting.key == item.key).first()
        if not row:
            row = AppSetting(key=item.key, value=item.value or "")
            db.add(row)
        else:
            row.value = item.value or ""
            row.updated_at = datetime.utcnow()
    db.commit()
    return await list_settings(db)
