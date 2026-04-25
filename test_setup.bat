@echo off
echo === NCII Shield Setup Test ===
echo.

echo 1. Starting Docker Compose stack...
docker compose up -d

echo.
echo 2. Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo 3. Checking service status...
docker compose ps

echo.
echo 4. Checking PostgreSQL migrations...
docker compose exec backend alembic current 2>nul || echo Migrations not yet applied

echo.
echo 5. Testing backend health endpoint...
curl -s http://localhost:8000/health || echo Backend not ready yet

echo.
echo 6. Checking Redis AOF persistence...
dir redis\appendonly.aof 2>nul || echo Redis AOF not yet created

echo.
echo === Setup test complete ===