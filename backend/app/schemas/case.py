from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum


class CaseStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUSPENDED = "suspended"


class CaseCreate(BaseModel):
    victim_id: str
    authorization_doc: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "victim_id": "victim123",
                "authorization_doc": "Authorization from victim received on 2024-04-24"
            }
        }
    )


class CaseResponse(BaseModel):
    id: int
    victim_id: str
    status: CaseStatus
    created_at: datetime
    authorization_doc: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CaseList(BaseModel):
    cases: List[CaseResponse]
    total: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cases": [
                    {
                        "id": 1,
                        "victim_id": "victim123",
                        "status": "active",
                        "created_at": "2024-04-24T00:00:00Z",
                        "authorization_doc": "Authorization document reference"
                    }
                ],
                "total": 1
            }
        }
    )