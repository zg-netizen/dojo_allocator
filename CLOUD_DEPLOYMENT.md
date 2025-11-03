# Railway Deployment Configuration

## railway.json
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "docker-compose up",
    "healthcheckPath": "/",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Dockerfile for Railway
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /mnt/user-data/backups

# Expose ports
EXPOSE 8000 8501

# Start both services
CMD ["sh", "-c", "python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 & streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0"]
```

## Environment Variables for Railway
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Redis
REDIS_HOST=redis.railway.internal
REDIS_PORT=6379

# Alpaca API
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret

# Security
SECRET_KEY=your_secret_key
```

## Railway CLI Commands
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Deploy
railway up

# View logs
railway logs

# Open in browser
railway open
```

## Render Deployment Configuration

## render.yaml
```yaml
services:
  - type: web
    name: dojo-allocator
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: ALPACA_API_KEY
        sync: false
      - key: ALPACA_API_SECRET
        sync: false

  - type: web
    name: dojo-dashboard
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
```

## DigitalOcean Droplet Setup

## setup_droplet.sh
```bash
#!/bin/bash

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/yourusername/dojo_allocator.git
cd dojo_allocator

# Create environment file
cat > .env << EOF
DATABASE_URL=postgresql://dojo:password@localhost:5432/dojo_allocator
REDIS_HOST=localhost
REDIS_PORT=6379
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
SECRET_KEY=your_secret_key
EOF

# Start services
docker-compose up -d

# Setup firewall
ufw allow 22
ufw allow 80
ufw allow 443
ufw allow 8000
ufw allow 8501
ufw --force enable

# Setup SSL with Let's Encrypt
apt install certbot python3-certbot-nginx -y

# Configure Nginx reverse proxy
cat > /etc/nginx/sites-available/dojo << EOF
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/dojo /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Get SSL certificate
certbot --nginx -d yourdomain.com
```

## Mobile Access URLs

### ngrok (Development)
- Dashboard: `https://dojo-allocator-dashboard.ngrok.io`
- API: `https://dojo-allocator-api.ngrok.io`

### Railway (Production)
- Dashboard: `https://dojo-dashboard-production.up.railway.app`
- API: `https://dojo-api-production.up.railway.app`

### Render (Production)
- Dashboard: `https://dojo-dashboard.onrender.com`
- API: `https://dojo-api.onrender.com`

### DigitalOcean (Production)
- Dashboard: `https://yourdomain.com`
- API: `https://yourdomain.com/api`

## Security Considerations

1. **HTTPS Only**: All mobile access should use HTTPS
2. **Authentication**: Add login system for production
3. **Rate Limiting**: Implement API rate limiting
4. **CORS**: Configure CORS for mobile apps
5. **Firewall**: Restrict access to necessary ports only

## Performance Optimizations

1. **CDN**: Use CloudFlare for static assets
2. **Caching**: Implement Redis caching
3. **Database**: Use connection pooling
4. **Monitoring**: Add performance monitoring
5. **Scaling**: Auto-scale based on demand
