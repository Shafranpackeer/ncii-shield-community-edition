from pydantic import BaseModel, ConfigDict, field_validator, Field
from typing import List, Optional
from datetime import datetime


class ReferenceHashCreate(BaseModel):
    phash: int = Field(..., description="64-bit perceptual hash")
    dhash: int = Field(..., description="64-bit difference hash")
    face_embedding: Optional[List[float]] = Field(None, description="128-dimensional face embedding vector")
    label: Optional[str] = Field(None, max_length=255, description="Optional label for the reference")

    @field_validator('phash', 'dhash')
    def validate_hash(cls, v):
        # Ensure it's a valid 64-bit integer
        if v < 0 or v > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("Hash must be a 64-bit unsigned integer")
        return v

    @field_validator('face_embedding')
    def validate_face_embedding(cls, v):
        if v is not None:
            if len(v) != 128:
                raise ValueError("Face embedding must be exactly 128 dimensions")
            # Check all values are floats
            for val in v:
                if not isinstance(val, (int, float)):
                    raise ValueError("Face embedding values must be numeric")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phash": 9223372036854775807,
                "dhash": 1234567890123456789,
                "face_embedding": [0.1] * 128,  # 128-dimensional vector
                "label": "Reference image 1"
            }
        }
    )


class ReferenceHashResponse(BaseModel):
    id: int
    case_id: int
    phash: int
    dhash: int
    face_embedding: Optional[List[float]] = None
    label: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)