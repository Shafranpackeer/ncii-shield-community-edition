"""
Recovery worker for resuming interrupted actions and scheduling due targets.

This module implements boot-time recovery to ensure no actions are lost
during crashes or restarts.
"""

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.session import SessionLocal
from app.models.action import Action, ActionStatus, ActionType
from app.models.target import Target, TargetStatus
from app.celery_app import celery_app
from app.utils.audit import create_audit_log

logger = logging.getLogger(__name__)


class RecoveryWorker:
    """Handles recovery of interrupted actions and scheduling of due targets."""

    def __init__(self, db: Session):
        self.db = db

    def recover_pending_actions(self) -> List[int]:
        """
        Find and re-enqueue actions that were interrupted.

        Criteria:
        - Status is PENDING with scheduled_at < now() OR created_at > 5 minutes ago
        - Status is EXECUTING with:
          - last_heartbeat_at > 2 minutes ago (stuck with heartbeat)
          - OR last_heartbeat_at is NULL AND created_at > 5 minutes ago (never started heartbeat)

        Returns:
            List of action IDs that were recovered
        """
        now = datetime.utcnow()
        two_minutes_ago = now - timedelta(minutes=2)
        five_minutes_ago = now - timedelta(minutes=5)

        # Find PENDING actions that need recovery
        pending_actions = self.db.query(Action).filter(
            and_(
                Action.status == ActionStatus.PENDING,
                or_(
                    and_(Action.scheduled_at.isnot(None), Action.scheduled_at < now),
                    Action.created_at < five_minutes_ago
                )
            )
        ).all()

        # Find EXECUTING actions that are stuck
        executing_actions = self.db.query(Action).filter(
            and_(
                Action.status == ActionStatus.EXECUTING,
                or_(
                    # Has heartbeat but it's old
                    and_(
                        Action.last_heartbeat_at.isnot(None),
                        Action.last_heartbeat_at < two_minutes_ago
                    ),
                    # No heartbeat and created long ago
                    and_(
                        Action.last_heartbeat_at.is_(None),
                        Action.created_at < five_minutes_ago
                    )
                )
            )
        ).all()

        interrupted_actions = pending_actions + executing_actions

        recovered_ids = []

        for action in interrupted_actions:
            logger.info(f"Recovering action {action.id} (type: {action.type.value}, status: {action.status.value})")

            # Reset status to PENDING for re-execution
            old_status = action.status
            action.status = ActionStatus.PENDING

            # Create audit log
            create_audit_log(
                db=self.db,
                entity_type="action",
                entity_id=action.id,
                action="recovered",
                old_value={"status": old_status.value},
                new_value={"status": ActionStatus.PENDING.value, "reason": "boot_recovery"}
            )

            # Re-enqueue based on action type
            self._enqueue_action(action)
            recovered_ids.append(action.id)

        self.db.commit()

        if recovered_ids:
            logger.info(f"Recovered {len(recovered_ids)} interrupted actions: {recovered_ids}")
        else:
            logger.info("No interrupted actions found to recover")

        return recovered_ids

    def schedule_due_targets(self) -> List[int]:
        """
        Find targets that are due for their next action.

        Criteria:
        - next_action_at < now()
        - status NOT IN ('resolved', 'failed')

        Returns:
            List of target IDs that were scheduled
        """
        now = datetime.utcnow()

        # Find targets needing action
        due_targets = self.db.query(Target).filter(
            and_(
                Target.next_action_at.isnot(None),
                Target.next_action_at < now,
                ~Target.status.in_([TargetStatus.RESOLVED, TargetStatus.FALSE_POSITIVE])
            )
        ).all()

        scheduled_ids = []

        for target in due_targets:
            logger.info(f"Scheduling next action for target {target.id} (status: {target.status.value})")

            # Determine next action type based on current status and history
            next_action_type = self._determine_next_action(target)

            if next_action_type:
                # Create new action
                action = Action(
                    target_id=target.id,
                    type=next_action_type,
                    status=ActionStatus.PENDING,
                    scheduled_at=now,
                    payload={"auto_scheduled": True, "reason": "due_for_action"}
                )
                self.db.add(action)
                self.db.flush()

                # Create audit log
                create_audit_log(
                    db=self.db,
                    entity_type="action",
                    entity_id=action.id,
                    action="auto_scheduled",
                    new_value={
                        "target_id": target.id,
                        "type": next_action_type.value,
                        "reason": "next_action_due"
                    }
                )

                # Enqueue the action
                self._enqueue_action(action)
                scheduled_ids.append(target.id)

                # Update target's next_action_at
                target.next_action_at = None  # Will be set by the action handler

        self.db.commit()

        if scheduled_ids:
            logger.info(f"Scheduled actions for {len(scheduled_ids)} due targets: {scheduled_ids}")
        else:
            logger.info("No targets are due for action")

        return scheduled_ids

    def _enqueue_action(self, action: Action):
        """Enqueue an action to the appropriate Celery queue."""
        task_name = (action.payload or {}).get("task_name") or self._get_task_name(action.type)

        if task_name:
            # Extract idempotency key from payload
            idempotency_key = action.payload.get("idempotency_key", str(action.id))

            # Queue the task
            celery_app.send_task(
                task_name,
                kwargs={
                    "target_id": action.target_id,
                    "action_id": action.id,
                    "idempotency_key": idempotency_key,
                    **action.payload
                },
                queue="default"
            )
            logger.info(f"Enqueued task {task_name} for action {action.id}")
        else:
            logger.error(f"No task handler found for action type {action.type.value}")

    def _get_task_name(self, action_type: ActionType) -> str:
        """Map action type to Celery task name."""
        task_mapping = {
            ActionType.EMAIL_INITIAL: "app.tasks.email.send_initial_takedown",
            ActionType.EMAIL_FOLLOWUP: "app.tasks.email.send_followup",
            ActionType.EMAIL_HOSTING: "app.tasks.email.send_hosting_abuse",
            ActionType.EMAIL_REGISTRAR: "app.tasks.email.send_registrar_complaint",
            ActionType.CHECK_REMOVAL: "app.tasks.verification.check_content_removed",
            ActionType.MANUAL_ESCALATION: "app.tasks.escalation.flag_manual_review"
        }
        return task_mapping.get(action_type, "")

    def _determine_next_action(self, target: Target) -> ActionType:
        """Determine the appropriate next action for a target."""
        # Get the last completed action for this target
        last_action = self.db.query(Action).filter(
            and_(
                Action.target_id == target.id,
                Action.status == ActionStatus.COMPLETED
            )
        ).order_by(Action.executed_at.desc()).first()

        if not last_action:
            # No actions yet, start with initial email
            return ActionType.EMAIL_INITIAL

        # Escalation ladder based on last action
        escalation_ladder = {
            ActionType.EMAIL_INITIAL: ActionType.EMAIL_FOLLOWUP,
            ActionType.EMAIL_FOLLOWUP: ActionType.EMAIL_HOSTING,
            ActionType.EMAIL_HOSTING: ActionType.EMAIL_REGISTRAR,
            ActionType.EMAIL_REGISTRAR: ActionType.MANUAL_ESCALATION,
            ActionType.CHECK_REMOVAL: None,  # No auto-escalation after removal check
            ActionType.MANUAL_ESCALATION: None  # Terminal state
        }

        return escalation_ladder.get(last_action.type)


@celery_app.task(name="app.tasks.recovery.run_recovery")
def run_recovery_task():
    """
    Celery task to run recovery process.

    This task is triggered on worker startup and periodically
    to ensure no actions are lost.
    """
    logger.info("Starting recovery process")

    db = SessionLocal()
    try:
        worker = RecoveryWorker(db)

        # Recover interrupted actions
        recovered_actions = worker.recover_pending_actions()

        # Schedule targets due for action
        scheduled_targets = worker.schedule_due_targets()

        return {
            "recovered_actions": recovered_actions,
            "scheduled_targets": scheduled_targets,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Recovery process failed: {str(e)}", exc_info=True)
        raise

    finally:
        db.close()
