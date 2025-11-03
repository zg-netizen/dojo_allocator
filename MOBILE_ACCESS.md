# Mobile Access Configuration

## Option 1: Quick Setup with ngrok (Recommended)

### Step 1: Run the setup script
```bash
cd /Users/macbookpro/dojo_allocator
./setup_mobile_access.sh
```

### Step 2: Authenticate ngrok
1. Go to https://dashboard.ngrok.com/get-started/your-authtoken
2. Sign up for a free account
3. Copy your authtoken
4. Run: `ngrok config add-authtoken YOUR_TOKEN`

### Step 3: Start mobile access
```bash
./start_mobile_access.sh
```

### Step 4: Access from your phone
- Dashboard: `https://dojo-allocator-dashboard.ngrok.io`
- API: `https://dojo-allocator-api.ngrok.io`

---

## Option 2: Cloud Deployment (Permanent)

### Deploy to Railway (Free tier available)

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
```

2. **Login to Railway**
```bash
railway login
```

3. **Deploy the application**
```bash
railway init
railway up
```

4. **Access your app**
- Railway will provide a public URL
- Access from anywhere: `https://your-app-name.railway.app`

### Deploy to Render (Free tier available)

1. **Connect GitHub repository**
2. **Create new Web Service**
3. **Configure build settings**
4. **Deploy automatically**

---

## Option 3: VPS Deployment

### Deploy to DigitalOcean Droplet

1. **Create a $5/month droplet**
2. **Install Docker**
3. **Clone your repository**
4. **Run with docker-compose**
5. **Configure domain name**

---

## Mobile Optimization Features

### Responsive Design
- Mobile-first layout
- Touch-friendly controls
- Optimized for small screens

### Performance
- Fast loading
- Minimal data usage
- Offline capabilities

### Security
- HTTPS encryption
- Authentication required
- Secure API endpoints

---

## Troubleshooting

### Common Issues

1. **ngrok not working**
   - Check if port 8501 is available
   - Verify ngrok authentication
   - Try different subdomain

2. **Slow performance**
   - Check internet connection
   - Optimize dashboard components
   - Use mobile data saver

3. **Access denied**
   - Verify ngrok is running
   - Check firewall settings
   - Ensure ports are open

### Support
- Check ngrok status: https://status.ngrok.com/
- Railway status: https://status.railway.app/
- Render status: https://status.render.com/
