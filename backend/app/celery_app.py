from celery import Celery, signals
from celery.signals import worker_ready, worker_shutdown, task_prerun
import os
import logging
import signal
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "ncii_shield",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)

# Configure Celery
celery_app.conf.update(
    imports=(
        "app.tasks.test_task",
        "app.persistence.recovery",
        "app.discovery.jobs.discovery",
        "app.confirmation.tasks",
    ),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,

    # Graceful shutdown settings
    worker_term_hard_timeout=30,  # Force kill after 30s
    task_soft_time_limit=300,     # Soft limit 5 minutes
    task_time_limit=600,          # Hard limit 10 minutes
    task_acks_late=True,          # Acknowledge after completion
    task_reject_on_worker_lost=True,  # Requeue tasks on worker death

    # Result backend settings
    result_expires=3600,          # Results expire after 1 hour
    result_persistent=True,       # Store results persistently
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "check-scheduled-actions": {
        "task": "app.tasks.check_scheduled_actions",
        "schedule": 60.0,  # Every minute
    },
    "run-recovery": {
        "task": "app.tasks.recovery.run_recovery",
        "schedule": 300.0,  # Every 5 minutes
    },
}


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Run recovery task when worker starts up."""
    logger.info("Worker ready, running recovery task")

    # Import here to avoid circular imports
    from app.persistence.recovery import run_recovery_task

    # Run recovery synchronously on startup
    try:
        result = run_recovery_task()
        logger.info(f"Startup recovery completed: {result}")
    except Exception as e:
        logger.error(f"Startup recovery failed: {str(e)}", exc_info=True)


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Handle graceful shutdown."""
    logger.info("Worker shutting down gracefully")

    # Mark any in-flight actions back to pending
    from app.db.session import SessionLocal
    from app.models.action import Action, ActionStatus
    from app.utils.audit import create_audit_log

    db = SessionLocal()
    try:
        # Find actions marked as executing by this worker
        executing_actions = db.query(Action).filter(
            Action.status == ActionStatus.EXECUTING
        ).all()

        for action in executing_actions:
            logger.info(f"Resetting action {action.id} to PENDING due to shutdown")
            action.status = ActionStatus.PENDING
            action.scheduled_at = datetime.utcnow()

            create_audit_log(
                db=db,
                entity_type="action",
                entity_id=action.id,
                action="reset_on_shutdown",
                old_value={"status": ActionStatus.EXECUTING.value},
                new_value={"status": ActionStatus.PENDING.value}
            )

        db.commit()
        logger.info(f"Reset {len(executing_actions)} executing actions to pending")

    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {str(e)}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# Handle SIGTERM gracefully
def handle_sigterm(signum, frame):
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info("Received SIGTERM, initiating graceful shutdown")
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)
