"""
Integration tests for the persistence and recovery system.

Tests:
1. Idempotency - duplicate calls don't re-execute
2. Recovery after crash - interrupted tasks resume
3. Graceful shutdown - tasks marked pending
4. Boot recovery - finds and re-queues tasks
"""

import os
import time
import signal
import subprocess
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Case, Target, Action
from app.models.case import CaseStatus
from app.models.target import TargetStatus
from app.models.action import ActionType, ActionStatus
from app.persistence.idempotent import idempotent_action, IdempotentActionError
from app.persistence.recovery import RecoveryWorker
from app.celery_app import celery_app

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://ncii_user:ncii_password@postgres:5432/ncii_shield"
)


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    yield engine


@pytest.fixture
def test_db(test_engine):
    """Create test database session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()

    # Clean up any existing data
    session.execute(text("""
        TRUNCATE TABLE
            review_thumbnails,
            target_hashes,
            contacts,
            actions,
            audit_log,
            identifiers,
            reference_hashes,
            targets,
            cases
        RESTART IDENTITY CASCADE
    """))
    session.commit()

    yield session

    # Cleanup after test
    session.rollback()
    session.execute(text("""
        TRUNCATE TABLE
            review_thumbnails,
            target_hashes,
            contacts,
            actions,
            audit_log,
            identifiers,
            reference_hashes,
            targets,
            cases
        RESTART IDENTITY CASCADE
    """))
    session.commit()
    session.close()


@pytest.fixture
def test_case(test_db):
    """Create a test case."""
    case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
    test_db.add(case)
    test_db.commit()
    return case


@pytest.fixture
def test_target(test_db, test_case):
    """Create a test target."""
    target = Target(
        case_id=test_case.id,
        url="https://example.com/test",
        status=TargetStatus.DISCOVERED
    )
    test_db.add(target)
    test_db.commit()
    return target


class TestIdempotency:
    """Test idempotent action wrapper."""

    def test_idempotent_action_success(self, test_db, test_target):
        """Test successful idempotent action execution."""
        idempotency_key = "test-key-001"

        # First execution
        with idempotent_action(
            target_id=test_target.id,
            action_type=ActionType.EMAIL_INITIAL,
            idempotency_key=idempotency_key,
            db=test_db
        ) as action:
            assert not action.is_already_completed()
            action.mark_executing()

            # Simulate work
            result = {"message_id": "msg-123", "sent_at": datetime.utcnow().isoformat()}
            action.action.payload["result"] = result

        # Verify action was created and completed
        saved_action = test_db.query(Action).filter(
            Action.payload["idempotency_key"].as_string() == idempotency_key
        ).first()

        assert saved_action is not None
        assert saved_action.status == ActionStatus.COMPLETED
        assert saved_action.payload["result"]["message_id"] == "msg-123"

    def test_idempotent_action_duplicate(self, test_db, test_target):
        """Test that duplicate calls don't re-execute."""
        idempotency_key = "test-key-002"

        # First execution
        with idempotent_action(
            target_id=test_target.id,
            action_type=ActionType.EMAIL_INITIAL,
            idempotency_key=idempotency_key,
            db=test_db
        ) as action:
            action.mark_executing()
            action.action.payload["result"] = {"message_id": "msg-456"}

        # Second execution with same key
        with idempotent_action(
            target_id=test_target.id,
            action_type=ActionType.EMAIL_INITIAL,
            idempotency_key=idempotency_key,
            db=test_db
        ) as action:
            assert action.is_already_completed()
            assert action.get_result()["message_id"] == "msg-456"

        # Verify only one action exists
        count = test_db.query(Action).filter(
            Action.payload["idempotency_key"].as_string() == idempotency_key
        ).count()
        assert count == 1

    def test_idempotent_action_failure_retry(self, test_db, test_target):
        """Test that failed actions can be retried."""
        idempotency_key = "test-key-003"

        # First execution fails
        with pytest.raises(ValueError):
            with idempotent_action(
                target_id=test_target.id,
                action_type=ActionType.EMAIL_INITIAL,
                idempotency_key=idempotency_key,
                db=test_db
            ) as action:
                action.mark_executing()
                raise ValueError("Simulated failure")

        # Verify action is marked as failed
        failed_action = test_db.query(Action).filter(
            Action.payload["idempotency_key"].as_string() == idempotency_key
        ).first()
        assert failed_action.status == ActionStatus.FAILED

        # Second execution should succeed
        with idempotent_action(
            target_id=test_target.id,
            action_type=ActionType.EMAIL_INITIAL,
            idempotency_key=idempotency_key,
            db=test_db
        ) as action:
            assert not action.is_already_completed()
            action.mark_executing()
            action.action.payload["result"] = {"message_id": "msg-789"}

        # Verify action is now completed
        test_db.refresh(failed_action)
        assert failed_action.status == ActionStatus.COMPLETED

    def test_heartbeat_functionality(self, test_db, test_target):
        """Test that heartbeat is updated while action is executing."""
        idempotency_key = "test-heartbeat-001"

        with idempotent_action(
            target_id=test_target.id,
            action_type=ActionType.EMAIL_INITIAL,
            idempotency_key=idempotency_key,
            db=test_db
        ) as action:
            # Get initial state
            action_id = action.action.id
            initial_heartbeat = action.action.last_heartbeat_at

            # Mark as executing (starts heartbeat)
            action.mark_executing()

            # Verify initial heartbeat was set
            test_db.refresh(action.action)
            assert action.action.last_heartbeat_at is not None
            first_heartbeat = action.action.last_heartbeat_at

            # Wait a bit and verify heartbeat updates
            time.sleep(2)
            test_db.refresh(action.action)
            assert action.action.last_heartbeat_at > first_heartbeat

        # After exit, verify action completed and heartbeat stopped
        final_action = test_db.query(Action).get(action_id)
        assert final_action.status == ActionStatus.COMPLETED


class TestRecoveryWorker:
    """Test recovery worker functionality."""

    def test_recover_pending_actions(self, test_db, test_target):
        """Test recovery of pending actions."""
        # Create old pending action
        old_action = Action(
            target_id=test_target.id,
            type=ActionType.EMAIL_INITIAL,
            status=ActionStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=10),
            payload={"idempotency_key": "old-pending"}
        )
        test_db.add(old_action)

        # Create executing action
        executing_action = Action(
            target_id=test_target.id,
            type=ActionType.EMAIL_FOLLOWUP,
            status=ActionStatus.EXECUTING,
            created_at=datetime.utcnow() - timedelta(minutes=15),
            payload={"idempotency_key": "old-executing"}
        )
        test_db.add(executing_action)

        # Create recent pending action (should not be recovered)
        recent_action = Action(
            target_id=test_target.id,
            type=ActionType.CHECK_REMOVAL,
            status=ActionStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(minutes=2),
            payload={"idempotency_key": "recent-pending"}
        )
        test_db.add(recent_action)

        test_db.commit()

        # Run recovery
        worker = RecoveryWorker(test_db)

        with patch.object(worker, '_enqueue_action') as mock_enqueue:
            recovered_ids = worker.recover_pending_actions()

        # Verify correct actions were recovered
        assert len(recovered_ids) == 2
        assert old_action.id in recovered_ids
        assert executing_action.id in recovered_ids
        assert recent_action.id not in recovered_ids

        # Verify enqueue was called
        assert mock_enqueue.call_count == 2

        # Verify statuses were reset
        test_db.refresh(executing_action)
        assert executing_action.status == ActionStatus.PENDING

    def test_schedule_due_targets(self, test_db, test_target):
        """Test scheduling of targets due for action."""
        # Set target as due for action
        test_target.next_action_at = datetime.utcnow() - timedelta(hours=1)
        test_target.status = TargetStatus.CONTACTED
        test_db.commit()

        # Run recovery
        worker = RecoveryWorker(test_db)

        with patch.object(worker, '_enqueue_action') as mock_enqueue:
            scheduled_ids = worker.schedule_due_targets()

        # Verify target was scheduled
        assert len(scheduled_ids) == 1
        assert test_target.id in scheduled_ids

        # Verify new action was created
        new_action = test_db.query(Action).filter(
            Action.target_id == test_target.id,
            Action.payload["auto_scheduled"].as_string() == "true"
        ).first()

        assert new_action is not None
        assert new_action.type == ActionType.EMAIL_INITIAL  # First action

        # Verify enqueue was called
        assert mock_enqueue.call_count == 1

    def test_heartbeat_based_recovery(self, test_db, test_target):
        """Test recovery based on heartbeat age."""
        # Create executing action with old heartbeat
        stuck_action = Action(
            target_id=test_target.id,
            type=ActionType.EMAIL_INITIAL,
            status=ActionStatus.EXECUTING,
            created_at=datetime.utcnow() - timedelta(minutes=10),
            last_heartbeat_at=datetime.utcnow() - timedelta(minutes=3),  # > 2 minutes old
            payload={"idempotency_key": "stuck-heartbeat"}
        )
        test_db.add(stuck_action)

        # Create executing action with recent heartbeat (should NOT be recovered)
        active_action = Action(
            target_id=test_target.id,
            type=ActionType.EMAIL_FOLLOWUP,
            status=ActionStatus.EXECUTING,
            created_at=datetime.utcnow() - timedelta(minutes=10),
            last_heartbeat_at=datetime.utcnow() - timedelta(seconds=30),  # Recent
            payload={"idempotency_key": "active-heartbeat"}
        )
        test_db.add(active_action)

        # Create executing action with no heartbeat but old (should be recovered)
        no_heartbeat_action = Action(
            target_id=test_target.id,
            type=ActionType.CHECK_REMOVAL,
            status=ActionStatus.EXECUTING,
            created_at=datetime.utcnow() - timedelta(minutes=6),
            last_heartbeat_at=None,  # Never started heartbeat
            payload={"idempotency_key": "no-heartbeat"}
        )
        test_db.add(no_heartbeat_action)

        test_db.commit()

        # Run recovery
        worker = RecoveryWorker(test_db)
        with patch.object(worker, '_enqueue_action') as mock_enqueue:
            recovered_ids = worker.recover_pending_actions()

        # Verify only stuck actions were recovered
        assert len(recovered_ids) == 2
        assert stuck_action.id in recovered_ids
        assert no_heartbeat_action.id in recovered_ids
        assert active_action.id not in recovered_ids  # Recent heartbeat, not recovered


class TestCeleryWorkerRecovery:
    """Test Celery worker crash recovery."""

    @pytest.mark.skipif(
        os.getenv("RUN_CELERY_CRASH_TEST") != "true",
        reason="Requires a standalone Celery worker process with reliable signal handling; set RUN_CELERY_CRASH_TEST=true to run"
    )
    def test_worker_crash_recovery(self, test_db, test_target, tmp_path):
        """
        Test that a task interrupted by worker crash is recovered.

        This test:
        1. Starts a long-running task
        2. Kills the worker mid-execution
        3. Restarts the worker
        4. Verifies the task is recovered and completed
        """
        from app.tasks.test_task import long_running_task

        # Create action
        action = Action(
            target_id=test_target.id,
            type=ActionType.EMAIL_INITIAL,
            status=ActionStatus.PENDING,
            payload={
                "idempotency_key": "crash-test",
                "task_name": "app.tasks.test_task.long_running_task",
                "duration": 30  # 30 second task
            }
        )
        test_db.add(action)
        test_db.commit()

        # Start worker process
        worker_cmd = [
            "celery", "-A", "app.celery_app", "worker",
            "--loglevel=info",
            "--concurrency=1"
        ]

        worker_proc = subprocess.Popen(
            worker_cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for worker to start
            time.sleep(5)

            # Queue the task
            result = long_running_task.apply_async(
                kwargs={
                    "target_id": test_target.id,
                    "action_id": action.id,
                    "idempotency_key": "crash-test",
                    "duration": 30
                }
            )

            # Wait for task to start executing
            time.sleep(3)

            # Verify task is executing
            test_db.refresh(action)
            assert action.status in [ActionStatus.PENDING, ActionStatus.EXECUTING]

            # Kill the worker (simulate crash)
            worker_proc.terminate()
            worker_proc.wait(timeout=5)

            # Verify task is still not completed
            test_db.refresh(action)
            assert action.status != ActionStatus.COMPLETED

            # Start new worker
            new_worker_proc = subprocess.Popen(
                worker_cmd,
                cwd=os.path.dirname(os.path.abspath(__file__)) + "/../..",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            try:
                # Wait for recovery to run
                time.sleep(10)

                # Check that task was recovered and completed
                test_db.refresh(action)

                # Task should eventually complete
                max_wait = 40  # seconds
                start_time = time.time()

                while action.status != ActionStatus.COMPLETED and (time.time() - start_time) < max_wait:
                    time.sleep(2)
                    test_db.refresh(action)

                assert action.status == ActionStatus.COMPLETED
                assert action.payload.get("result") is not None

            finally:
                new_worker_proc.terminate()
                new_worker_proc.wait(timeout=5)

        finally:
            # Cleanup
            if worker_proc.poll() is None:
                worker_proc.terminate()
                worker_proc.wait(timeout=5)


# Integration test runner script
if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([
        __file__,
        "-v",
        "--cov=app.persistence",
        "--cov-report=term-missing",
        "-s"  # Show print statements
    ])
