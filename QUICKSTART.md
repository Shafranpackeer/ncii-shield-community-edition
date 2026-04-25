# Quick Start Testing Guide

## Prerequisites Check

1. Ensure Docker and Docker Compose are installed:
```bash
docker --version
docker compose version
```

2. Ensure ports 3001, 8001, 5434, and 6380 are available:
```bash
# Check if ports are in use
netstat -an | grep -E "3001|8001|5434|6380"
```

## Step 1: Setup Environment

```bash
# Copy environment template
cp .env.example .env

# For testing, you can use minimal configuration
# Just add any search API key (at least one):
# BING_API_KEY=your-key-here
# or
# SERPAPI_KEY=your-key-here
# or
# SERPER_API_KEY=your-key-here
```

## Step 2: Start Services

```bash
# Build and start all services
docker compose up -d --build

# Wait for services to be ready (about 30 seconds)
sleep 30

# Run database migrations
docker compose exec backend alembic upgrade head
```

## Step 3: Verify Services

```bash
# Check all services are running
docker compose ps

# Check backend health
curl http://localhost:8001/health

# Check API docs
# Open in browser: http://localhost:8001/docs
```

## Step 4: Access the Application

1. **Frontend**: Open http://localhost:3001 in your browser
2. **API Docs**: Open http://localhost:8001/docs

## Step 5: Basic Testing Workflow

1. **Create a case**:
   - Click "New Case" on the dashboard
   - Enter victim ID and authorization note

2. **Add identifiers**:
   - Add names, usernames, or email addresses

3. **Upload reference image**:
   - Drag and drop an image
   - Watch it hash client-side
   - Confirm "Original Discarded"

4. **Run discovery** (requires search API key):
   - Click "Run Discovery"
   - Review discovered URLs

5. **Test other features**:
   - Settings page
   - Case timeline
   - Manual URL addition

## Troubleshooting

### Services not starting?
```bash
# Check logs
docker compose logs -f

# Restart specific service
docker compose restart backend
docker compose restart frontend
```

### Database connection issues?
```bash
# Check postgres is running
docker compose exec postgres psql -U ncii_user -d ncii_shield -c "SELECT 1;"
```

### Frontend not loading?
```bash
# Check frontend logs
docker compose logs frontend

# Rebuild frontend
docker compose up -d --build frontend
```

### Missing face detection models?
The app will work without face models - it will just skip facial recognition.
To add them later, see frontend/public/models/README.md

## Stop Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (careful - deletes data!)
docker compose down -v
```

## Next Steps

- Add search API keys for discovery features
- Configure Resend for email sending
- See DEPLOYMENT.md for production setup