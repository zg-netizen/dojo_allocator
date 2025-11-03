#!/bin/bash
# Mobile Access Setup Script
# This script sets up secure remote access to your Dojo Allocator dashboard

echo "🚀 Setting up mobile access for Dojo Allocator..."

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "📦 Installing ngrok..."
    
    # Detect OS and install ngrok
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install ngrok/ngrok/ngrok
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
        sudo apt update && sudo apt install ngrok
    else
        echo "❌ Unsupported OS. Please install ngrok manually from https://ngrok.com/"
        exit 1
    fi
fi

# Check if ngrok is authenticated
if ! ngrok config check &> /dev/null; then
    echo "🔐 Please authenticate ngrok:"
    echo "1. Go to https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "2. Copy your authtoken"
    echo "3. Run: ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    read -p "Press Enter after you've completed authentication..."
fi

# Create ngrok configuration
echo "⚙️ Creating ngrok configuration..."
mkdir -p ~/.config/ngrok
cat > ~/.config/ngrok/ngrok.yml << EOF
version: "2"
authtoken_from_env: true
tunnels:
  dashboard:
    addr: 8501
    proto: http
    subdomain: dojo-allocator-dashboard
  api:
    addr: 8000
    proto: http
    subdomain: dojo-allocator-api
EOF

# Create startup script
cat > start_mobile_access.sh << 'EOF'
#!/bin/bash
echo "🌐 Starting mobile access..."

# Start ngrok tunnels
echo "🔗 Starting ngrok tunnels..."
ngrok start --all --config ~/.config/ngrok/ngrok.yml &

# Wait for ngrok to start
sleep 5

# Get public URLs
DASHBOARD_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | grep dashboard | cut -d'"' -f4)
API_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | grep api | cut -d'"' -f4)

echo ""
echo "🎉 Mobile access is now available!"
echo "📱 Dashboard: $DASHBOARD_URL"
echo "🔌 API: $API_URL"
echo ""
echo "📲 Scan this QR code with your phone:"
qrencode -t ansiutf8 "$DASHBOARD_URL" 2>/dev/null || echo "Install qrencode for QR code: brew install qrencode"
echo ""
echo "🔒 Secure HTTPS access enabled"
echo "⏹️  Press Ctrl+C to stop"

# Keep script running
wait
EOF

chmod +x start_mobile_access.sh

# Create Streamlit config for mobile optimization
echo "📱 Creating mobile-optimized Streamlit config..."
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << EOF
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#2E7D32"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
EOF

echo "✅ Mobile access setup complete!"
echo ""
echo "🚀 To start mobile access, run:"
echo "   ./start_mobile_access.sh"
echo ""
echo "📱 Your dashboard will be available at:"
echo "   https://dojo-allocator-dashboard.ngrok.io"
echo ""
echo "🔌 Your API will be available at:"
echo "   https://dojo-allocator-api.ngrok.io"
