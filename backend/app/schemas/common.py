from pydantic import BaseModel, ConfigDict
from typing import Any, Optional, Dict


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {}
            }
        }
    )


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "message": "Validation error",
                "error": "Invalid input",
                "details": {"field": ["error message"]}
            }
        }
    )