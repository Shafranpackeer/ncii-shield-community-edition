@echo off
echo === NCII Shield Recovery System Test ===
echo.
echo This script demonstrates the recovery system by:
echo 1. Starting a long-running task
echo 2. Killing the worker mid-execution
echo 3. Restarting the worker
echo 4. Verifying the task completes without duplication
echo.

REM Check if services are running
echo Checking services...
docker compose ps | findstr "postgres.*running" >nul
if errorlevel 1 (
    echo Error: PostgreSQL is not running. Start services with: docker compose up -d
    exit /b 1
)

REM Run integration tests
echo.
echo Running integration tests...

REM Test 1: Idempotency tests
echo.
echo Test 1: Idempotency
docker compose exec backend pytest tests/integration/test_recovery.py::TestIdempotency -v -s

REM Test 2: Recovery worker tests
echo.
echo Test 2: Recovery Worker
docker compose exec backend pytest tests/integration/test_recovery.py::TestRecoveryWorker -v -s

REM Test 3: Worker crash recovery (if not skipped)
if "%SKIP_INTEGRATION_TESTS%"=="true" (
    echo.
    echo Test 3: Worker Crash Recovery - SKIPPED
) else (
    echo.
    echo Test 3: Worker Crash Recovery
    echo This test will:
    echo   - Start a 30-second task
    echo   - Kill the worker after 3 seconds
    echo   - Restart the worker
    echo   - Verify task completes
    echo.

    docker compose exec backend pytest tests/integration/test_recovery.py::TestCeleryWorkerRecovery::test_worker_crash_recovery -v -s
)

REM Summary
echo.
echo === Test Summary ===
echo The recovery system ensures:
echo - Idempotent execution - no duplicate side effects
echo - Automatic recovery - interrupted tasks resume
echo - Graceful shutdown - in-flight work is preserved
echo - Boot-time scanning - nothing is lost

echo.
echo === Example Usage ===
echo.
echo # Using idempotent action in your code:
echo.
echo from app.persistence import idempotent_action
echo from app.models.action import ActionType
echo.
echo with idempotent_action(
echo     target_id=target.id,
echo     action_type=ActionType.EMAIL_INITIAL,
echo     idempotency_key=f"email-{target.id}-initial"
echo ) as action:
echo     if action.is_already_completed():
echo         return action.get_result()
echo.
echo     # Your actual work here
echo     result = send_email(...)
echo     action.action.payload["result"] = result
echo.
echo Tests completed!