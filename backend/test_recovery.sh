#!/bin/bash

echo "=== NCII Shield Recovery System Test ==="
echo
echo "This script demonstrates the recovery system by:"
echo "1. Starting a long-running task"
echo "2. Killing the worker mid-execution"
echo "3. Restarting the worker"
echo "4. Verifying the task completes without duplication"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure we're in the backend directory
cd "$(dirname "$0")"

# Check if services are running
echo -e "${YELLOW}Checking services...${NC}"
if ! docker compose ps | grep -q "postgres.*running"; then
    echo -e "${RED}Error: PostgreSQL is not running. Start services with: docker compose up -d${NC}"
    exit 1
fi

# Run integration tests
echo -e "\n${YELLOW}Running integration tests...${NC}"

# Test 1: Idempotency tests
echo -e "\n${GREEN}Test 1: Idempotency${NC}"
docker compose exec backend pytest tests/integration/test_recovery.py::TestIdempotency -v -s

# Test 2: Recovery worker tests
echo -e "\n${GREEN}Test 2: Recovery Worker${NC}"
docker compose exec backend pytest tests/integration/test_recovery.py::TestRecoveryWorker -v -s

# Test 3: Worker crash recovery (if not skipped)
if [ "$SKIP_INTEGRATION_TESTS" != "true" ]; then
    echo -e "\n${GREEN}Test 3: Worker Crash Recovery${NC}"
    echo "This test will:"
    echo "  - Start a 30-second task"
    echo "  - Kill the worker after 3 seconds"
    echo "  - Restart the worker"
    echo "  - Verify task completes"
    echo

    docker compose exec backend pytest tests/integration/test_recovery.py::TestCeleryWorkerRecovery::test_worker_crash_recovery -v -s
else
    echo -e "\n${YELLOW}Test 3: Worker Crash Recovery - SKIPPED${NC}"
fi

# Summary
echo -e "\n${GREEN}=== Test Summary ===${NC}"
echo "The recovery system ensures:"
echo "✓ Idempotent execution - no duplicate side effects"
echo "✓ Automatic recovery - interrupted tasks resume"
echo "✓ Graceful shutdown - in-flight work is preserved"
echo "✓ Boot-time scanning - nothing is lost"

# Show example usage
echo -e "\n${GREEN}=== Example Usage ===${NC}"
cat << 'EOF'
# Using idempotent action in your code:

from app.persistence import idempotent_action
from app.models.action import ActionType

with idempotent_action(
    target_id=target.id,
    action_type=ActionType.EMAIL_INITIAL,
    idempotency_key=f"email-{target.id}-initial"
) as action:
    if action.is_already_completed():
        return action.get_result()

    # Your actual work here
    result = send_email(...)
    action.action.payload["result"] = result
EOF

echo -e "\n${GREEN}Tests completed!${NC}"