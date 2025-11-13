#!/bin/bash

echo "🏃‍♂️ Strava Stats - Quick Start Setup"
echo "===================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo ""
    echo "📝 Please edit .env file and add your Strava credentials:"
    echo "   1. STRAVA_CLIENT_ID"
    echo "   2. STRAVA_CLIENT_SECRET"
    echo "   3. FLASK_SECRET_KEY (generate with: python3 -c 'import secrets; print(secrets.token_hex(32))')"
    echo ""
    echo "After updating .env, run this script again."
    exit 0
fi

# Check if required variables are set in .env
source .env
if [ -z "$STRAVA_CLIENT_ID" ] || [ -z "$STRAVA_CLIENT_SECRET" ] || [ -z "$FLASK_SECRET_KEY" ]; then
    echo "⚠️  .env file is incomplete!"
    echo ""
    echo "Please ensure all variables are set:"
    echo "   - STRAVA_CLIENT_ID"
    echo "   - STRAVA_CLIENT_SECRET"
    echo "   - FLASK_SECRET_KEY"
    echo ""
    echo "Generate Flask secret key with:"
    echo "   python3 -c 'import secrets; print(secrets.token_hex(32))'"
    exit 1
fi

echo "✅ .env file configured"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
else
    echo "✅ Virtual environment already exists"
    echo ""
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Stop any existing Flask processes
echo "🛑 Stopping any existing Flask processes..."
pkill -f "python app.py" 2>/dev/null || true
sleep 1
echo "✅ Ready to start"
echo ""

# Display final instructions
echo "🚀 Starting Flask application..."
echo ""
echo "The application will be available at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""
echo "===================================="
echo ""

# Run the application
python app.py
