#!/bin/bash

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Start the Flask application
echo "Starting Flask application..."
python flask_app.py
