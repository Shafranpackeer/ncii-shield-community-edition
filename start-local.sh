#!/bin/bash

echo "🚀 Starting NCII Shield locally..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env to add at least one search API key"
fi

# Stop any existing containers
echo "🧹 Cleaning up existing containers..."
docker compose down 2>/dev/null || true

# Build and start services
echo "🏗️  Building and starting services..."
docker compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to be ready (30 seconds)..."
sleep 30

# Run migrations
echo "🗃️  Running database migrations..."
docker compose exec backend alembic upgrade head

# Check service health
echo "🔍 Checking service health..."
echo ""

# Check postgres
if docker compose exec postgres pg_isready -U ncii_user >/dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Check redis
if docker compose exec redis redis-cli ping >/dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check backend
if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo "✅ Backend API is ready"
else
    echo "❌ Backend API is not ready"
fi

# Check if frontend is accessible
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 | grep -q "200\|304"; then
    echo "✅ Frontend is ready"
else
    echo "⚠️  Frontend is starting..."
fi

echo ""
echo "🎉 NCII Shield is starting!"
echo ""
echo "📱 Frontend: http://localhost:3001"
echo "🔧 API Docs: http://localhost:8001/docs"
echo "🗄️  Database: localhost:5434"
echo "📦 Redis: localhost:6380"
echo ""
echo "📋 To view logs: docker compose logs -f"
echo "🛑 To stop: docker compose down"
echo ""
echo "💡 First time setup:"
echo "   1. Edit .env to add search API keys"
echo "   2. Create a new case in the UI"
echo "   3. Upload a test image to see hashing"
echo ""