# 🚀 AWS Deployment - Step-by-Step Guide

Follow these steps to deploy Dojo Allocator on AWS.

## 📋 Prerequisites Checklist

- [ ] AWS account with EC2 access
- [ ] Domain name (optional, but recommended)
- [ ] Alpaca API keys (for paper trading)
- [ ] FRED API key (optional, for economic data)

## Step 1: Launch AWS EC2 Instance

### 1.1 Create EC2 Instance

1. **Go to AWS Console** → EC2 → Launch Instance
2. **Configure instance:**
   - **Name**: `dojo-allocator`
   - **AMI**: Ubuntu 22.04 LTS (free tier eligible)
   - **Instance type**: `t3.medium` (2 vCPU, 4 GB RAM) or larger
   - **Key pair**: Create new or select existing (download `.pem` file!)
   - **Network settings**: 
     - Create security group or use existing
     - **Allow SSH** (port 22) from your IP
     - **Allow HTTP** (port 80) from anywhere
     - **Allow HTTPS** (port 443) from anywhere
   - **Storage**: 20 GB minimum (gp3 SSD recommended)
3. **Launch instance**

### 1.2 Get Your Instance Details

Note down:
- **Public IP address** (e.g., `54.123.45.67`)
- **Private key location** (e.g., `~/Downloads/dojo-allocator.pem`)

### 1.3 Test SSH Connection

```bash
# Make key file executable
chmod 400 ~/Downloads/dojo-allocator.pem

# Connect to your server
ssh -i ~/Downloads/dojo-allocator.pem ubuntu@YOUR_PUBLIC_IP
```

✅ **Test**: You should be able to SSH into your server

---

## Step 2: Initial Server Setup

### 2.1 Run Initial Setup Script

Once connected to your server via SSH:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker (this will be automated in next step)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install additional tools
sudo apt install -y git openssl htop

# Log out and back in to apply Docker group changes
exit
```

### 2.2 Reconnect to Server

```bash
ssh -i ~/Downloads/dojo-allocator.pem ubuntu@YOUR_PUBLIC_IP
```

✅ **Test**: Run `docker --version` and `docker-compose --version` (both should work)

---

## Step 3: Clone Your Repository

### 3.1 Clone from GitHub

```bash
cd ~
git clone https://github.com/zg-netizen/dojo_allocator.git
cd dojo_allocator
```

✅ **Test**: Run `ls -la` - you should see all project files

---

## Step 4: Configure Environment Variables

### 4.1 Create Production Environment File

```bash
# Copy the example file
cp env.prod.example .env.prod

# Edit the file
nano .env.prod
```

### 4.2 Fill in Required Values

Edit the file with your actual credentials:

```bash
# Database Configuration
POSTGRES_PASSWORD=YourSecurePassword123!  # CHANGE THIS!

# Alpaca Trading API (Paper Trading)
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here

# Federal Reserve Economic Data API (optional)
FRED_API_KEY=your_fred_api_key_here

# Optional: Custom domain (if you have one)
DOMAIN_NAME=your-domain.com
```

**Save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`

✅ **Test**: Run `cat .env.prod` (verify it doesn't show your password accidentally)

---

## Step 5: Deploy the Application

### 5.1 Run Deployment Script

```bash
# Make scripts executable
chmod +x deploy.sh manage.sh aws-setup.sh

# Run deployment
./deploy.sh
```

This will:
- Generate SSL certificates (self-signed initially)
- Build Docker images
- Start all services
- Wait for services to be healthy

⏳ **Wait**: This takes 5-10 minutes on first run

### 5.2 Verify Deployment

```bash
# Check if all services are running
./manage.sh status

# Check logs
./manage.sh logs -f
```

Press `Ctrl+C` to exit logs view

✅ **Test**: Open `https://YOUR_PUBLIC_IP` in your browser (ignore SSL warning for now)

---

## Step 6: Configure SSL (Optional but Recommended)

### Option A: Use Let's Encrypt (Free SSL - Recommended)

**Prerequisites**: You need a domain name pointing to your server

```bash
# Install Certbot
sudo apt install -y certbot

# Get SSL certificate (replace with your domain)
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to application
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown ubuntu:ubuntu ssl/*.pem

# Restart services
./manage.sh restart
```

### Option B: Keep Self-Signed (For Testing)

Self-signed certificates are already generated. Your browser will show a security warning - this is normal for testing.

---

## Step 7: Configure Domain (Optional)

### 7.1 Point Domain to Server

1. Go to your domain registrar (GoDaddy, Namecheap, etc.)
2. Find DNS settings
3. Create/Edit **A Record**:
   - **Name**: `@` (or leave blank for root domain)
   - **Value**: Your EC2 public IP address
   - **TTL**: 3600 (or default)

### 7.2 Wait for DNS Propagation

DNS changes can take up to 24 hours, but usually propagate within 1-2 hours.

✅ **Test**: Run `nslookup your-domain.com` - should return your server IP

---

## Step 8: Set Up Auto-Start (Systemd Service)

### 8.1 Create Systemd Service

```bash
# Copy service file
sudo cp dojo-allocator.service /etc/systemd/system/

# Edit service file (update path if needed)
sudo nano /etc/systemd/system/dojo-allocator.service
```

Make sure the paths in the file match your installation directory.

### 8.2 Enable Auto-Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable dojo-allocator
sudo systemctl start dojo-allocator
```

✅ **Test**: Reboot server (`sudo reboot`) - services should start automatically

---

## Step 9: Set Up Automatic Backups

### 9.1 Create Backup Script

The backup script is already included. Set up a cron job:

```bash
# Edit crontab
crontab -e

# Add this line for daily backups at 2 AM UTC
0 2 * * * cd /home/ubuntu/dojo_allocator && ./manage.sh backup

# Save and exit
```

### 9.2 Test Backup

```bash
# Manual backup
./manage.sh backup

# Verify backup was created
ls -lh backups/
```

---

## Step 10: Configure Firewall

### 10.1 Set Up UFW Firewall

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

✅ **Test**: Your server should still be accessible via SSH and web

---

## Step 11: Access Your Deployment

### 11.1 Access Points

- **Dashboard**: `https://YOUR_PUBLIC_IP` or `https://your-domain.com`
- **API**: `https://YOUR_PUBLIC_IP/api/` or `https://your-domain.com/api/`
- **API Docs**: `https://YOUR_PUBLIC_IP/api/docs`
- **Health Check**: `https://YOUR_PUBLIC_IP/health`

### 11.2 Test the Application

1. Open dashboard in browser
2. Check all pages load correctly
3. Verify API endpoints respond
4. Monitor logs: `./manage.sh logs -f`

---

## Step 12: Ongoing Management

### Useful Commands

```bash
# View service status
./manage.sh status

# View logs
./manage.sh logs -f

# Restart services
./manage.sh restart

# Update application (pull latest code)
git pull
./manage.sh update

# Create backup
./manage.sh backup

# Check health
./manage.sh health

# Stop services
./manage.sh stop

# Start services
./manage.sh start
```

---

## 🔍 Troubleshooting

### Services Won't Start

```bash
# Check logs
./manage.sh logs

# Check Docker status
docker ps -a

# Restart Docker
sudo systemctl restart docker
```

### Database Connection Issues

```bash
# Check database container
docker-compose -f docker-compose.prod.yml logs postgres

# Test database connection
./manage.sh db-shell
```

### SSL Certificate Issues

```bash
# Check certificate
openssl x509 -in ssl/cert.pem -text -noout

# Regenerate self-signed
rm ssl/cert.pem ssl/key.pem
./deploy.sh
```

### Memory/Resource Issues

```bash
# Check resource usage
docker stats

# Clean up unused resources
./manage.sh clean

# Consider upgrading instance size
```

---

## 📊 Monitoring Recommendations

1. **AWS CloudWatch**: Monitor CPU, memory, disk usage
2. **Uptime Monitoring**: Set up uptime monitoring (UptimeRobot, etc.)
3. **Application Logs**: Regularly check `./manage.sh logs`
4. **Database Backups**: Verify backups are running

---

## ✅ Deployment Checklist

- [ ] EC2 instance launched
- [ ] Security groups configured
- [ ] SSH access working
- [ ] Docker and Docker Compose installed
- [ ] Repository cloned
- [ ] Environment variables configured
- [ ] Application deployed
- [ ] Services running and healthy
- [ ] SSL certificates configured
- [ ] Domain configured (optional)
- [ ] Auto-start enabled
- [ ] Backups configured
- [ ] Firewall configured
- [ ] Dashboard accessible
- [ ] API accessible

---

## 🎉 You're Done!

Your Dojo Allocator is now running 24/7 on AWS!

**Next Steps:**
- Monitor the dashboard regularly
- Set up alerts for errors
- Review logs weekly
- Keep backups current
- Update the application as needed

**Need Help?**
- Check `AWS_DEPLOYMENT.md` for detailed documentation
- Review logs: `./manage.sh logs`
- Check service health: `./manage.sh health`

