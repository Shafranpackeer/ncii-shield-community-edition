from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse


class TargetStatus(str, Enum):
    DISCOVERED = "discovered"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    CONTACTED = "contacted"
    REMOVED = "removed"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class TargetCreate(BaseModel):
    url: str
    discovery_source: Optional[str] = "manual"
    confidence_score: Optional[float] = None

    @field_validator('url')
    def validate_url(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        # Basic URL validation
        try:
            result = urlparse(v)
            if not all([result.scheme, result.netloc]):
                raise ValueError("Invalid URL format")
            if result.scheme not in ['http', 'https']:
                raise ValueError("URL must start with http:// or https://")
        except Exception:
            raise ValueError("Invalid URL format")

        return v

    @field_validator('confidence_score')
    def validate_confidence(cls, v):
        if v is not None:
            if v < 0.0 or v > 1.0:
                raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com/page123",
                "discovery_source": "manual",
                "confidence_score": 0.95
            }
        }
    )


class TargetResponse(BaseModel):
    id: int
    case_id: int
    url: str
    status: TargetStatus
    discovery_source: Optional[str] = None
    confidence_score: Optional[float] = None
    next_action_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)