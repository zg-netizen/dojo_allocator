# 🚀 AWS Deployment Guide for Dojo Allocator

This guide will help you deploy the Dojo Allocator to your AWS server for 24/7 operation.

## 📋 Prerequisites

### AWS Server Requirements
- **Instance Type**: t3.medium or larger (2+ vCPUs, 4+ GB RAM)
- **Storage**: 20+ GB SSD storage
- **OS**: Ubuntu 20.04 LTS or newer
- **Security Groups**: Open ports 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Required Software
- Docker
- Docker Compose
- Git
- OpenSSL (for SSL certificates)

## 🛠️ Step 1: Prepare Your AWS Server

### 1.1 Connect to Your Server
```bash
ssh -i your-key.pem ubuntu@your-server-ip
```

### 1.2 Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install Docker
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in to apply group changes
exit
ssh -i your-key.pem ubuntu@your-server-ip
```

### 1.4 Install Additional Tools
```bash
sudo apt install -y git openssl
```

## 📦 Step 2: Deploy the Application

### 2.1 Clone the Repository
```bash
git clone https://github.com/your-username/dojo_allocator.git
cd dojo_allocator
```

### 2.2 Configure Environment Variables
```bash
# Copy the example environment file
cp env.prod.example .env.prod

# Edit the environment file with your actual values
nano .env.prod
```

**Required Environment Variables:**
```bash
# Database Configuration
POSTGRES_PASSWORD=your_secure_database_password_here

# Alpaca Trading API (Paper Trading)
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_API_SECRET=your_alpaca_api_secret_here

# Federal Reserve Economic Data API
FRED_API_KEY=your_fred_api_key_here
```

### 2.3 Deploy the Application
```bash
# Make deployment script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

## 🔒 Step 3: Configure SSL (Optional but Recommended)

### 3.1 Using Let's Encrypt (Free SSL)
```bash
# Install Certbot
sudo apt install -y certbot

# Get SSL certificate (replace with your domain)
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates to the ssl directory
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown ubuntu:ubuntu ssl/*.pem

# Restart services
./manage.sh restart
```

### 3.2 Using Self-Signed Certificates (Development)
The deployment script automatically generates self-signed certificates if none exist.

## 🌐 Step 4: Configure Domain (Optional)

### 4.1 Point Your Domain to Your Server
1. Go to your domain registrar's DNS settings
2. Create an A record pointing to your server's IP address
3. Wait for DNS propagation (up to 24 hours)

### 4.2 Update Nginx Configuration
If you have a custom domain, update the `nginx.conf` file:
```nginx
server_name your-domain.com;
```

## 📊 Step 5: Monitor Your Deployment

### 5.1 Check Service Status
```bash
./manage.sh status
```

### 5.2 View Logs
```bash
# View all logs
./manage.sh logs

# Follow logs in real-time
./manage.sh logs -f
```

### 5.3 Health Check
```bash
./manage.sh health
```

## 🔧 Step 6: Ongoing Management

### 6.1 Available Management Commands
```bash
# Start services
./manage.sh start

# Stop services
./manage.sh stop

# Restart services
./manage.sh restart

# Update application
./manage.sh update

# Create database backup
./manage.sh backup

# Restore from backup
./manage.sh restore backup_file.sql

# Open shell in API container
./manage.sh shell

# Open database shell
./manage.sh db-shell

# Clean up unused Docker resources
./manage.sh clean
```

### 6.2 Automatic Backups
Set up a cron job for automatic daily backups:
```bash
# Edit crontab
crontab -e

# Add this line for daily backups at 2 AM
0 2 * * * cd /home/ubuntu/dojo_allocator && ./manage.sh backup
```

### 6.3 Monitoring and Alerts
Consider setting up monitoring with:
- **AWS CloudWatch**: Monitor server resources
- **Uptime monitoring**: Services like UptimeRobot
- **Log aggregation**: ELK stack or similar

## 🔐 Step 7: Security Considerations

### 7.1 Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### 7.2 Regular Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update application
git pull
./manage.sh update
```

### 7.3 Database Security
- Use strong passwords
- Regular backups
- Consider database encryption at rest

## 🚨 Troubleshooting

### Common Issues

#### Services Won't Start
```bash
# Check logs
./manage.sh logs

# Check Docker status
docker ps -a

# Restart Docker service
sudo systemctl restart docker
```

#### Database Connection Issues
```bash
# Check database container
docker-compose -f docker-compose.prod.yml logs postgres

# Test database connection
./manage.sh db-shell
```

#### SSL Certificate Issues
```bash
# Check certificate validity
openssl x509 -in ssl/cert.pem -text -noout

# Regenerate self-signed certificate
rm ssl/cert.pem ssl/key.pem
./deploy.sh
```

#### Memory Issues
```bash
# Check memory usage
docker stats

# Clean up unused resources
./manage.sh clean
```

## 📈 Performance Optimization

### 7.1 Resource Monitoring
```bash
# Monitor resource usage
htop
docker stats

# Check disk usage
df -h
du -sh /var/lib/docker
```

### 7.2 Scaling Considerations
- **CPU**: Monitor CPU usage, consider upgrading instance type
- **Memory**: Ensure sufficient RAM for all services
- **Storage**: Monitor disk usage, implement log rotation
- **Network**: Consider using a load balancer for high traffic

## 🎯 Access Your Deployment

Once deployed, your Dojo Allocator will be available at:

- **Dashboard**: `https://your-server-ip/` or `https://your-domain.com/`
- **API**: `https://your-server-ip/api/` or `https://your-domain.com/api/`
- **Health Check**: `https://your-server-ip/health`

## 📞 Support

If you encounter issues:

1. Check the logs: `./manage.sh logs`
2. Verify service health: `./manage.sh health`
3. Check system resources: `htop`, `df -h`
4. Review this documentation
5. Contact support if needed

## 🎉 Congratulations!

Your Dojo Allocator is now running 24/7 on AWS! The system will automatically:
- Process trading signals
- Execute trades across 5 scenarios
- Manage risk and position sizing
- Update the dashboard in real-time
- Handle market data and API calls

Monitor the dashboard regularly to track performance and adjust settings as needed.
