"""Test task for integration testing the recovery system."""

import time
import logging
from datetime import datetime

from app.celery_app import celery_app
from app.persistence.idempotent import idempotent_task
from app.models.action import ActionType

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.test_task.long_running_task")
@idempotent_task(ActionType.EMAIL_INITIAL)
def long_running_task(target_id: int, action_id: int, duration: int = 10, **kwargs):
    """
    A test task that simulates a long-running operation.

    This task can be interrupted mid-execution to test recovery.

    Args:
        target_id: Target ID
        action_id: Action ID
        duration: How long to run (seconds)
    """
    logger.info(f"Starting long-running task for action {action_id}, will run for {duration}s")

    # Simulate work being done
    start_time = datetime.utcnow()
    work_iterations = 0

    for i in range(duration):
        # Check if we should stop (in real task, check for cancellation)
        logger.info(f"Working... iteration {i+1}/{duration}")
        time.sleep(1)
        work_iterations += 1

    end_time = datetime.utcnow()
    execution_time = (end_time - start_time).total_seconds()

    result = {
        "success": True,
        "message": f"Task completed successfully after {work_iterations} iterations",
        "execution_time": execution_time,
        "completed_at": end_time.isoformat()
    }

    logger.info(f"Long-running task completed: {result}")
    return result