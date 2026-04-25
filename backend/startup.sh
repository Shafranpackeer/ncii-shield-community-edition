#!/bin/bash
# Startup script to wait for database and run migrations

echo "Waiting for PostgreSQL to be ready..."
while ! pg_isready -h postgres -p 5432 -U ncii_user -d ncii_shield; do
  sleep 1
done

echo "PostgreSQL is ready. Running migrations..."
alembic upgrade head

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload