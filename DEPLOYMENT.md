# Production Deployment Guide

This guide helps you deploy NCII Shield to a production VPS with SSL certificates.

## Prerequisites

- Ubuntu 20.04+ VPS with at least 2GB RAM
- Domain name pointed to your VPS
- SSH access to the server

## Step 1: Initial Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose-plugin -y

# Install nginx
sudo apt install nginx certbot python3-certbot-nginx -y
```

## Step 2: Clone and Configure

```bash
# Clone the repository
cd /opt
sudo git clone https://github.com/Shafranpackeer/ncii-shield-community-edition.git ncii-shield
cd ncii-shield

# Copy and edit environment variables
sudo cp .env.example .env
sudo nano .env

# Update these values:
# - API keys for search providers
# - Resend API key for email
# - Database passwords
# - NEXT_PUBLIC_API_URL=https://api.yourdomain.com
# - APP_PUBLIC_URL=https://app.yourdomain.com
```

## Step 3: Nginx Configuration

Create nginx config for the frontend:

```nginx
# /etc/nginx/sites-available/ncii-shield-app
server {
    listen 80;
    server_name app.yourdomain.com;

    location / {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Create nginx config for the API:

```nginx
# /etc/nginx/sites-available/ncii-shield-api
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the sites:

```bash
sudo ln -s /etc/nginx/sites-available/ncii-shield-app /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/ncii-shield-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Step 4: SSL Certificates

```bash
# Get SSL certificates
sudo certbot --nginx -d app.yourdomain.com -d api.yourdomain.com
```

## Step 5: Start the Application

```bash
cd /opt/ncii-shield

# Start in production mode
sudo docker compose -f docker-compose.yml up -d

# Run database migrations
sudo docker compose exec backend alembic upgrade head

# Check logs
sudo docker compose logs -f
```

## Step 6: Security Hardening

### Firewall Setup
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Database Backups
Create a backup script:

```bash
#!/bin/bash
# /opt/ncii-shield/backup.sh
BACKUP_DIR="/opt/ncii-shield/backups"
mkdir -p $BACKUP_DIR

# Backup database
docker compose exec -T postgres pg_dump -U ncii_user ncii_shield > "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"

# Keep only last 7 days
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

Add to crontab:
```bash
# Daily backups at 3 AM
0 3 * * * /opt/ncii-shield/backup.sh
```

## Step 7: Monitoring

### Health Check Script
```bash
#!/bin/bash
# /opt/ncii-shield/healthcheck.sh

# Check if services are running
if ! curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "API is down! Restarting..."
    cd /opt/ncii-shield && docker compose restart backend
fi

if ! curl -f http://localhost:3001 > /dev/null 2>&1; then
    echo "Frontend is down! Restarting..."
    cd /opt/ncii-shield && docker compose restart frontend
fi
```

Add to crontab:
```bash
# Check every 5 minutes
*/5 * * * * /opt/ncii-shield/healthcheck.sh
```

## Updates

To update to the latest version:

```bash
cd /opt/ncii-shield
sudo git pull
sudo docker compose down
sudo docker compose up -d --build
sudo docker compose exec backend alembic upgrade head
```

## Troubleshooting

### Check logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
```

### Restart services
```bash
docker compose restart
```

### Database connection issues
```bash
# Check if postgres is running
docker compose ps postgres

# Test connection
docker compose exec postgres psql -U ncii_user -d ncii_shield
```

## Support

For issues, check:
- GitHub Issues: https://github.com/Shafranpackeer/ncii-shield-community-edition/issues
- Logs: `docker compose logs`
- Health endpoints: https://api.yourdomain.com/health