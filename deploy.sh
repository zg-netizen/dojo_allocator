#!/bin/bash

# Dojo Allocator AWS Deployment Script
# This script deploys the Dojo Allocator to your AWS server

set -e

echo "🥋 Deploying Dojo Allocator to AWS..."

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo "❌ Error: .env.prod file not found!"
    echo "Please copy env.prod.example to .env.prod and fill in your values:"
    echo "cp env.prod.example .env.prod"
    echo "nano .env.prod"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed!"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed!"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create SSL directory if it doesn't exist
mkdir -p ssl

# Check if SSL certificates exist
if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
    echo "⚠️  SSL certificates not found. Generating self-signed certificates..."
    echo "For production, you should replace these with real SSL certificates."
    
    # Generate self-signed certificate
    openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    
    echo "✅ Self-signed SSL certificates generated."
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down || true

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 30

# Check service health
echo "🔍 Checking service health..."

# Check API
if curl -f http://localhost/api/health > /dev/null 2>&1; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
fi

# Check Dashboard
if curl -f http://localhost/ > /dev/null 2>&1; then
    echo "✅ Dashboard is healthy"
else
    echo "❌ Dashboard health check failed"
fi

# Show running containers
echo "📊 Running containers:"
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "🌐 Your Dojo Allocator is now running at:"
echo "   Dashboard: https://your-server-ip/"
echo "   API: https://your-server-ip/api/"
echo ""
echo "📋 Next steps:"
echo "   1. Update your domain DNS to point to this server"
echo "   2. Replace self-signed SSL certificates with real ones"
echo "   3. Configure firewall rules (ports 80, 443)"
echo "   4. Set up monitoring and backups"
echo ""
echo "🔧 Management commands:"
echo "   View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "   Stop: docker-compose -f docker-compose.prod.yml down"
echo "   Restart: docker-compose -f docker-compose.prod.yml restart"
echo "   Update: ./deploy.sh"
