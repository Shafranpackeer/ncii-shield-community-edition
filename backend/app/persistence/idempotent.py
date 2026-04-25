"""
Idempotent action wrapper for guaranteed exactly-once execution.

This module implements the write-before-act pattern to ensure that
all outbound actions (emails, API calls, webhooks) are executed
exactly once, even in the face of crashes, restarts, or network failures.
"""

import uuid
import functools
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from datetime import datetime
from contextlib import contextmanager
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError

from app.models.action import Action, ActionStatus, ActionType
from app.db.session import SessionLocal
from app.utils.audit import create_audit_log

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IdempotentActionError(Exception):
    """Raised when an idempotent action fails."""
    pass


class IdempotentAction:
    """
    Context manager for idempotent action execution.

    Ensures write-before-act pattern:
    1. Write intent to database with status 'pending'
    2. Check for existing action with same idempotency key
    3. Execute action
    4. Update status to 'completed' or 'failed'
    """

    def __init__(
        self,
        db: Session,
        target_id: int,
        action_type: ActionType,
        idempotency_key: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None
    ):
        self.db = db
        self.target_id = target_id
        self.action_type = action_type
        self.idempotency_key = idempotency_key or str(uuid.uuid4())
        self.payload = payload or {}
        self.scheduled_at = scheduled_at
        self.action: Optional[Action] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_interval_seconds = 1

    def __enter__(self):
        """Write intent before action execution."""
        # Check if action already exists with this idempotency key
        existing = self._find_existing_action()

        if existing:
            if existing.status == ActionStatus.COMPLETED:
                # Action already completed, return existing result
                logger.info(f"Action {self.idempotency_key} already completed")
                self.action = existing
                return self

            elif existing.status == ActionStatus.FAILED:
                # Previous attempt failed, we can retry
                logger.info(f"Retrying failed action {self.idempotency_key}")
                existing.status = ActionStatus.PENDING
                self.db.commit()
                self.action = existing
                return self

            elif existing.status == ActionStatus.PENDING:
                # A pending intent has been written and is ready for a worker to execute.
                logger.info(f"Executing pending action {self.idempotency_key}")
                self.action = existing
                return self

            elif existing.status == ActionStatus.EXECUTING:
                # Action is already in progress.
                logger.warning(f"Action {self.idempotency_key} already in progress")
                raise IdempotentActionError(
                    f"Action with idempotency key {self.idempotency_key} is already in progress"
                )

            else:
                # Unexpected status
                self.action = existing
                return self

        # Create new action with pending status
        try:
            self.action = Action(
                target_id=self.target_id,
                type=self.action_type,
                payload={
                    **self.payload,
                    "idempotency_key": self.idempotency_key
                },
                status=ActionStatus.PENDING,
                scheduled_at=self.scheduled_at
            )
            self.db.add(self.action)
            self.db.flush()

            # Create audit log
            create_audit_log(
                db=self.db,
                entity_type="action",
                entity_id=self.action.id,
                action="created",
                new_value={
                    "target_id": self.target_id,
                    "type": self.action_type.value,
                    "status": ActionStatus.PENDING.value,
                    "idempotency_key": self.idempotency_key
                }
            )

            self.db.commit()
            logger.info(f"Created action {self.action.id} with idempotency key {self.idempotency_key}")

        except IntegrityError:
            # Race condition - another process created the action
            self.db.rollback()
            existing = self._find_existing_action()
            if existing:
                self.action = existing
                return self
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Update action status based on execution result."""
        # Stop heartbeat thread if running
        self._stop_heartbeat()

        if not self.action:
            return

        if self.action.status == ActionStatus.COMPLETED:
            # Already completed by another process or previous execution
            return

        if exc_type is None:
            # Success - mark as completed
            self._update_status(ActionStatus.COMPLETED)
        else:
            # Failure - mark as failed
            self._update_status(
                ActionStatus.FAILED,
                error_message=str(exc_val) if exc_val else "Unknown error"
            )

    def _find_existing_action(self) -> Optional[Action]:
        """Find existing action with the same idempotency key."""
        return self.db.query(Action).filter(
            Action.payload["idempotency_key"].as_string() == self.idempotency_key
        ).first()

    def _update_status(self, status: ActionStatus, error_message: Optional[str] = None):
        """Update action status and create audit log."""
        old_status = self.action.status
        self.action.status = status
        if self.action.payload is not None:
            self.action.payload = dict(self.action.payload)
            flag_modified(self.action, "payload")

        if status == ActionStatus.COMPLETED:
            self.action.executed_at = datetime.utcnow()
        elif error_message:
            self.action.error_message = error_message

        # Create audit log
        create_audit_log(
            db=self.db,
            entity_type="action",
            entity_id=self.action.id,
            action="status_changed",
            old_value={"status": old_status.value},
            new_value={
                "status": status.value,
                "error_message": error_message
            }
        )

        self.db.commit()
        logger.info(f"Updated action {self.action.id} status from {old_status.value} to {status.value}")

    def mark_executing(self):
        """Mark action as executing before starting the actual work."""
        if self.action and self.action.status == ActionStatus.PENDING:
            self._update_status(ActionStatus.EXECUTING)
            # Start heartbeat thread when marking as executing
            self._start_heartbeat()

    def is_already_completed(self) -> bool:
        """Check if the action was already completed."""
        return self.action and self.action.status == ActionStatus.COMPLETED

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Get the result payload if action is completed."""
        if self.action and self.action.status == ActionStatus.COMPLETED:
            return self.action.payload.get("result")
        return None

    def _start_heartbeat(self):
        """Start the heartbeat thread that updates last_heartbeat_at every 30 seconds."""
        if not self.action:
            return

        def heartbeat_worker():
            """Background thread that sends heartbeats."""
            action_id = self.action.id
            logger.debug(f"Starting heartbeat for action {action_id}")

            while not self._heartbeat_stop_event.is_set():
                heartbeat_db = SessionLocal()
                try:
                    # Update heartbeat
                    action = heartbeat_db.get(Action, action_id)
                    if action is None:
                        break
                    action.last_heartbeat_at = datetime.utcnow()
                    heartbeat_db.commit()
                    logger.debug(f"Heartbeat sent for action {action_id}")

                    # Wait briefly or until stop event; tests and recovery rely on fresh heartbeats.
                    if self._heartbeat_stop_event.wait(self._heartbeat_interval_seconds):
                        break

                except Exception as e:
                    logger.error(f"Error sending heartbeat for action {action_id}: {str(e)}")
                    # Continue trying even on error
                finally:
                    heartbeat_db.close()

            logger.debug(f"Heartbeat stopped for action {action_id}")

        # Initial heartbeat
        self.action.last_heartbeat_at = datetime.utcnow()
        self.db.commit()

        # Start background thread
        self._heartbeat_thread = threading.Thread(
            target=heartbeat_worker,
            name=f"heartbeat-action-{self.action.id}",
            daemon=True
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self):
        """Stop the heartbeat thread."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            logger.debug(f"Stopping heartbeat for action {self.action.id if self.action else 'unknown'}")
            self._heartbeat_stop_event.set()
            self._heartbeat_thread.join(timeout=5)  # Wait up to 5 seconds for thread to stop


@contextmanager
def idempotent_action(
    target_id: int,
    action_type: ActionType,
    idempotency_key: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None
):
    """
    Context manager for idempotent action execution.

    Usage:
        with idempotent_action(target_id, ActionType.EMAIL_INITIAL, idempotency_key) as action:
            if action.is_already_completed():
                return action.get_result()

            action.mark_executing()
            # Perform the actual action
            result = send_email(...)
            action.action.payload["result"] = result

    Args:
        target_id: ID of the target
        action_type: Type of action
        idempotency_key: Unique key for idempotency (auto-generated if not provided)
        payload: Additional payload data
        db: Database session (creates new one if not provided)
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        with IdempotentAction(db, target_id, action_type, idempotency_key, payload) as action:
            yield action
    finally:
        if close_db:
            db.close()


def idempotent_task(action_type: ActionType):
    """
    Decorator for Celery tasks that require idempotency.

    Usage:
        @celery_app.task
        @idempotent_task(ActionType.EMAIL_INITIAL)
        def send_email_task(target_id: int, idempotency_key: str, **kwargs):
            # Task implementation
            return {"message_id": "xxx"}

    The decorator automatically:
    1. Creates an action record before execution
    2. Checks for duplicate executions
    3. Updates status on completion/failure
    4. Handles database sessions
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(target_id: int, idempotency_key: Optional[str] = None, **kwargs) -> T:
            db = SessionLocal()
            try:
                queued_action_id = kwargs.pop("action_id", None)
                with idempotent_action(
                    target_id=target_id,
                    action_type=action_type,
                    idempotency_key=idempotency_key,
                    payload=kwargs,
                    db=db
                ) as action:
                    if action.is_already_completed():
                        logger.info(f"Task already completed for idempotency key {idempotency_key}")
                        return action.get_result()

                    action.mark_executing()

                    # Execute the actual task
                    result = func(target_id=target_id, action_id=queued_action_id or action.action.id, **kwargs)

                    # Store result in action payload
                    action.action.payload["result"] = result
                    action.action.payload = dict(action.action.payload)
                    flag_modified(action.action, "payload")
                    db.commit()

                    return result
            finally:
                db.close()

        return wrapper
    return decorator
