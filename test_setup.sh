#!/bin/bash

echo "=== NCII Shield Setup Test ==="
echo

echo "1. Starting Docker Compose stack..."
docker compose up -d

echo
echo "2. Waiting for services to be healthy..."
sleep 10

echo
echo "3. Checking service status..."
docker compose ps

echo
echo "4. Checking PostgreSQL migrations..."
docker compose exec backend alembic current 2>/dev/null || echo "Migrations not yet applied"

echo
echo "5. Testing backend health endpoint..."
curl -s http://localhost:8000/health || echo "Backend not ready yet"

echo
echo "6. Checking Redis AOF persistence..."
ls -la redis/appendonly.aof 2>/dev/null || echo "Redis AOF not yet created"

echo
echo "=== Setup test complete ==="