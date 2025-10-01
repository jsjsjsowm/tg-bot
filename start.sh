#!/bin/bash
set -e

echo "Starting deployment process..."

# Install Python dependencies
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Initialize database
echo "Initializing database..."
python -c "from flask_app import init_db; init_db()"

# Start the Flask application
echo "Starting Flask application..."
exec python flask_app.py
