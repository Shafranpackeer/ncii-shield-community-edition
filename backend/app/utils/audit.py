from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    request: Optional[Request] = None
) -> AuditLog:
    """
    Create an audit log entry.

    Args:
        db: Database session
        entity_type: Type of entity (e.g., "case", "identifier", "reference_hash")
        entity_id: ID of the entity
        action: Action performed (e.g., "created", "updated", "deleted")
        old_value: Previous value (for updates)
        new_value: New value
        user_id: ID of the user performing the action
        request: FastAPI request object to extract IP and user agent

    Returns:
        Created AuditLog instance
    """
    audit_entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id
    )

    # Extract IP address and user agent from request if available
    if request:
        # Get client IP address
        if hasattr(request, "client") and request.client:
            audit_entry.ip_address = request.client.host

        # Get user agent
        audit_entry.user_agent = request.headers.get("user-agent")

    db.add(audit_entry)
    # Don't commit here - let the calling function handle the transaction

    return audit_entry