#!/bin/bash
# Quick mobile access script

echo "🚀 Starting mobile access for Dojo Allocator..."

# Check if ngrok is authenticated
if ! ngrok config check &> /dev/null; then
    echo "🔐 ngrok needs authentication:"
    echo "1. Go to https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "2. Sign up for a free account"
    echo "3. Copy your authtoken"
    echo "4. Run: ngrok config add-authtoken YOUR_TOKEN"
    echo ""
    read -p "Press Enter after you've completed authentication..."
fi

# Start ngrok tunnel for dashboard
echo "🔗 Starting ngrok tunnel for dashboard (port 8501)..."
ngrok http 8501 --log=stdout &

# Wait for ngrok to start
sleep 3

# Get the public URL
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$PUBLIC_URL" ]; then
    echo "❌ Failed to get ngrok URL. Trying alternative method..."
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else '')")
fi

if [ -n "$PUBLIC_URL" ]; then
    echo ""
    echo "🎉 Mobile access is now available!"
    echo "📱 Dashboard: $PUBLIC_URL"
    echo ""
    echo "📲 Open this URL on your phone:"
    echo "   $PUBLIC_URL"
    echo ""
    echo "🔒 Secure HTTPS access enabled"
    echo "⏹️  Press Ctrl+C to stop"
    
    # Try to generate QR code if qrencode is available
    if command -v qrencode &> /dev/null; then
        echo ""
        echo "📲 Scan this QR code with your phone:"
        qrencode -t ansiutf8 "$PUBLIC_URL"
    else
        echo "💡 Install qrencode for QR code: brew install qrencode"
    fi
else
    echo "❌ Failed to get ngrok URL"
    echo "Try running: ngrok http 8501"
fi

# Keep script running
wait
