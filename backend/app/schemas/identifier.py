from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from enum import Enum


class IdentifierType(str, Enum):
    NAME = "name"
    HANDLE = "handle"
    ALIAS = "alias"
    EMAIL = "email"
    PHONE = "phone"


class IdentifierCreate(BaseModel):
    type: IdentifierType
    value: str

    @field_validator('value')
    def validate_value(cls, v, info):
        v = v.strip()
        if not v:
            raise ValueError("Identifier value cannot be empty")
        if len(v) > 500:
            raise ValueError("Identifier value too long (max 500 characters)")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "name",
                "value": "John Doe"
            }
        }
    )


class IdentifierResponse(BaseModel):
    id: int
    case_id: int
    type: IdentifierType
    value: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)