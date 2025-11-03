#!/bin/bash
# Keep ngrok running persistently

echo "🚀 Starting persistent ngrok tunnel..."

# Check if ngrok is already running
if pgrep -f "ngrok http 8501" > /dev/null; then
    echo "ngrok is already running"
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else 'No tunnels found')")
    echo "Current URL: $PUBLIC_URL"
    exit 0
fi

# Start ngrok in background
ngrok http 8501 --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 5

# Get the public URL
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data['tunnels'] else 'No tunnels found')")

if [ -n "$PUBLIC_URL" ] && [ "$PUBLIC_URL" != "No tunnels found" ]; then
    echo "✅ ngrok tunnel started successfully!"
    echo "📱 Public URL: $PUBLIC_URL"
    echo "🆔 Process ID: $NGROK_PID"
    echo ""
    echo "To stop ngrok: kill $NGROK_PID"
    echo "To check status: curl -s http://localhost:4040/api/tunnels"
    echo ""
    echo "This tunnel will stay active until you stop it or restart your computer."
else
    echo "❌ Failed to start ngrok tunnel"
    kill $NGROK_PID 2>/dev/null
    exit 1
fi
