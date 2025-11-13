#!/bin/bash

echo "🛑 Stopping any existing Flask processes..."
pkill -f "python app.py" 2>/dev/null || true

# Wait a moment for processes to stop
sleep 1

echo "🚀 Starting Flask application..."
python app.py
