# Recovery System Demonstration

## Idempotent Action Wrapper

The system implements a write-before-act pattern that ensures exactly-once execution:

```python
from app.persistence import idempotent_action
from app.models.action import ActionType

# Example: Sending an email with idempotency
def send_takedown_email(target_id: int, content: str):
    idempotency_key = f"email-{target_id}-{hash(content)}"

    with idempotent_action(
        target_id=target_id,
        action_type=ActionType.EMAIL_INITIAL,
        idempotency_key=idempotency_key
    ) as action:
        if action.is_already_completed():
            # Return cached result - no duplicate send
            return action.get_result()

        action.mark_executing()

        # Perform the actual work
        result = email_api.send(...)

        # Store result for future calls
        action.action.payload["result"] = result
        return result
```

## Recovery Worker

The recovery worker automatically handles:

1. **Interrupted Actions**: Finds PENDING/EXECUTING actions older than 5 minutes
2. **Due Targets**: Schedules next actions for targets with `next_action_at < now()`

```python
# Recovery runs automatically on:
# - Worker startup (via Celery signal)
# - Every 5 minutes (via Celery beat)

# Manual trigger:
from app.persistence.recovery import run_recovery_task
result = run_recovery_task()
```

## Running the Integration Tests

### Option 1: Docker Compose (Recommended)

```bash
# From the ncii-shield directory
cd backend

# Run all recovery tests
docker compose exec backend pytest tests/integration/test_recovery.py -v

# Or use the test script
./test_recovery.sh      # Linux/Mac
test_recovery.bat       # Windows
```

### Option 2: Direct Python

```bash
# Set test database URL
export TEST_DATABASE_URL=postgresql://ncii_user:ncii_password@localhost:5432/ncii_shield_test

# Run tests
cd backend
python -m pytest tests/integration/test_recovery.py -v -s
```

## Test Output Example

```
=== NCII Shield Recovery System Test ===

Test 1: Idempotency
tests/integration/test_recovery.py::TestIdempotency::test_idempotent_action_success PASSED
tests/integration/test_recovery.py::TestIdempotency::test_idempotent_action_duplicate PASSED
tests/integration/test_recovery.py::TestIdempotency::test_idempotent_action_failure_retry PASSED

Test 2: Recovery Worker
tests/integration/test_recovery.py::TestRecoveryWorker::test_recover_pending_actions PASSED
tests/integration/test_recovery.py::TestRecoveryWorker::test_schedule_due_targets PASSED

Test 3: Worker Crash Recovery
Starting long-running task for action 123, will run for 30s
Working... iteration 1/30
Working... iteration 2/30
[Worker killed]
Worker ready, running recovery task
Recovering action 123 (type: email_initial, status: executing)
Task completed successfully after 30 iterations
PASSED
```

## Crash Recovery Simulation

The integration test simulates a real crash scenario:

1. **Start Task**: A 30-second task begins execution
2. **Kill Worker**: After 3 seconds, worker is terminated (SIGTERM)
3. **Task Interrupted**: Action remains in EXECUTING state
4. **Restart Worker**: New worker starts, recovery runs
5. **Resume Task**: Task is re-queued and completes
6. **No Duplication**: Original idempotency key prevents duplicate execution

## Redis AOF Verification

Check that Redis persistence is working:

```bash
# Check AOF file exists and is being written
ls -la redis/appendonly.aof

# View Redis config
docker compose exec redis redis-cli CONFIG GET appendonly
# Should return: appendonly yes

docker compose exec redis redis-cli CONFIG GET appendfsync
# Should return: appendfsync everysec
```

## Monitoring Recovery

### Check for stuck actions:
```sql
-- Connect to database
docker compose exec postgres psql -U ncii_user -d ncii_shield

-- Find stuck actions
SELECT id, target_id, type, status, created_at
FROM actions
WHERE status IN ('pending', 'executing')
  AND created_at < NOW() - INTERVAL '30 minutes';
```

### View recovery logs:
```bash
# Worker logs show recovery on startup
docker compose logs celery-worker | grep -i recovery

# Example output:
# celery-worker-1  | [2024-04-24 12:00:00] INFO Worker ready, running recovery task
# celery-worker-1  | [2024-04-24 12:00:01] INFO Recovered 2 interrupted actions: [123, 124]
# celery-worker-1  | [2024-04-24 12:00:01] INFO Scheduled actions for 1 due targets: [456]
```

### Manual recovery trigger:
```bash
docker compose exec celery-worker python -c "
from app.persistence.recovery import run_recovery_task
import json
result = run_recovery_task()
print(json.dumps(result, indent=2))
"
```

## Graceful Shutdown Test

Test graceful shutdown handling:

```bash
# Start a long task
docker compose exec backend python -c "
from app.tasks.test_task import long_running_task
result = long_running_task.apply_async(kwargs={
    'target_id': 1,
    'action_id': 1,
    'duration': 60
})
print(f'Task ID: {result.id}')
"

# Gracefully stop the worker
docker compose stop celery-worker

# Check logs - should show graceful shutdown
docker compose logs celery-worker --tail 20

# Restart and verify task resumes
docker compose start celery-worker
```

## Key Features Demonstrated

✅ **Idempotency**: Same key = same result, no duplicate execution
✅ **Write-Before-Act**: Database record created before any side effects
✅ **Crash Recovery**: Interrupted tasks automatically resume
✅ **Graceful Shutdown**: In-flight work preserved on SIGTERM
✅ **AOF Persistence**: Redis queue survives restarts
✅ **Audit Trail**: Every state change logged for debugging

## Troubleshooting

If tests fail:

1. **Database not ready**: Ensure PostgreSQL is running
   ```bash
   docker compose up -d postgres
   docker compose exec postgres pg_isready
   ```

2. **Celery not starting**: Check broker connection
   ```bash
   docker compose logs celery-worker
   docker compose exec redis redis-cli ping
   ```

3. **Recovery not running**: Check Celery beat
   ```bash
   docker compose logs celery-beat
   ```

4. **Reset test state**: Clear test data
   ```sql
   DELETE FROM actions;
   DELETE FROM targets;
   DELETE FROM cases;
   ```