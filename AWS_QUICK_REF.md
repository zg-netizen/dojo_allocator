# 🚀 AWS Quick Reference Card

## Initial Setup (One-Time)

```bash
# 1. SSH to server
ssh -i your-key.pem ubuntu@YOUR_IP

# 2. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone repository
cd ~
git clone https://github.com/zg-netizen/dojo_allocator.git
cd dojo_allocator

# 5. Configure environment
cp env.prod.example .env.prod
nano .env.prod  # Fill in your API keys

# 6. Deploy
chmod +x *.sh
./deploy.sh
```

## Daily Commands

```bash
# Status check
./manage.sh status

# View logs
./manage.sh logs -f

# Restart services
./manage.sh restart

# Backup database
./manage.sh backup

# Health check
./manage.sh health
```

## Update Application

```bash
git pull
./manage.sh update
```

## Access Points

- Dashboard: `https://YOUR_IP`
- API: `https://YOUR_IP/api/`
- API Docs: `https://YOUR_IP/api/docs`

## Emergency Commands

```bash
# Stop everything
./manage.sh stop

# Start everything
./manage.sh start

# View all logs
./manage.sh logs

# Database shell
./manage.sh db-shell
```

