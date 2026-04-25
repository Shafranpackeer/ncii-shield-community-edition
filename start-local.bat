@echo off
echo Starting NCII Shield locally...
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running. Please start Docker Desktop and try again.
    echo.
    echo Opening Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo Please wait for Docker to start, then run this script again.
    pause
    exit /b 1
)

echo Docker is running - proceeding...
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env to add at least one search API key
)

REM Stop existing containers
echo Cleaning up existing containers...
docker compose down 2>nul

REM Build and start services
echo Building and starting services...
docker compose up -d --build

REM Wait for services
echo Waiting for services to be ready (30 seconds)...
timeout /t 30 /nobreak >nul

REM Run migrations
echo Running database migrations...
docker compose exec backend alembic upgrade head

REM Check services
echo.
echo Checking service health...
echo ========================
docker compose ps
echo.

REM Display access URLs
echo NCII Shield is starting!
echo ========================
echo.
echo Frontend: http://localhost:3001
echo API Docs: http://localhost:8001/docs
echo.
echo Commands:
echo - View logs: docker compose logs -f
echo - Stop services: docker compose down
echo.
echo First time setup:
echo 1. Edit .env to add search API keys
echo 2. Create a new case in the UI
echo 3. Upload a test image to see hashing
echo.

REM Open browser
echo Opening browser...
timeout /t 3 /nobreak >nul
start http://localhost:3001

pause