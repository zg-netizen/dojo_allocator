#!/bin/bash

# Quick AWS Setup Script for Dojo Allocator
# Run this script on your fresh AWS Ubuntu server

set -e

echo "🥋 Setting up Dojo Allocator on AWS..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
echo "🔧 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install additional tools
echo "🛠️ Installing additional tools..."
sudo apt install -y git openssl htop

# Create application directory
echo "📁 Creating application directory..."
mkdir -p /home/ubuntu/dojo_allocator
cd /home/ubuntu/dojo_allocator

# Note: You'll need to upload your code or clone from repository
echo "⚠️  Next steps:"
echo "1. Upload your Dojo Allocator code to this directory"
echo "2. Copy env.prod.example to .env.prod and configure it"
echo "3. Run ./deploy.sh to start the application"
echo ""
echo "Or clone from repository:"
echo "git clone https://github.com/your-username/dojo_allocator.git ."
echo "cd dojo_allocator"
echo "cp env.prod.example .env.prod"
echo "nano .env.prod  # Configure your environment variables"
echo "./deploy.sh"

echo ""
echo "✅ AWS server setup complete!"
echo "📋 Don't forget to:"
echo "   - Configure your environment variables"
echo "   - Set up SSL certificates"
echo "   - Configure your domain DNS"
echo "   - Set up monitoring and backups"
