FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Initialize database
RUN python -c "import flask_app; flask_app.init_db(); print('Database initialized')"

# Expose port
EXPOSE 5000

# Start the application
CMD ["python", "flask_app.py"]
