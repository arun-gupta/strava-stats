#!/bin/bash
# Activation script for Strava Stats virtual environment

echo "🏃‍♂️ Activating Strava Stats virtual environment..."
source venv/bin/activate

echo "✅ Virtual environment activated!"
echo "📦 Python version: $(python --version)"
echo "📍 Virtual environment location: $(which python)"
echo ""
echo "🚀 To run the application:"
echo "   python app.py"
echo ""
echo "🛑 To deactivate the virtual environment:"
echo "   deactivate"
