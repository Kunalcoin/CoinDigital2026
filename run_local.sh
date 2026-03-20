#!/bin/bash

# Script to run Django application locally for testing.
# Uses coin.env (and .env) for DB connection and all config.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DJANGO_DIR="$SCRIPT_DIR/RoyaltyWebsite"

# Load coin.env first, then .env so local overrides win (DB, SERVER, S3, etc.)
if [ -f "$SCRIPT_DIR/coin.env" ]; then
  set -a
  source "$SCRIPT_DIR/coin.env"
  set +a
  echo "Loaded coin.env for DB and config."
fi
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
  echo "Loaded .env overrides."
fi

echo "=========================================="
echo "Starting Django Application Locally"
echo "=========================================="
echo ""

# Check if at least one env file exists
if [ ! -f "$SCRIPT_DIR/coin.env" ] && [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "Warning: No .env file found. Creating symlink from coin.env..."
    if [ -f "$SCRIPT_DIR/coin.env" ]; then
        ln -sf "$SCRIPT_DIR/coin.env" "$SCRIPT_DIR/.env"
        echo "Created symlink: .env -> coin.env"
    else
        echo "Error: coin.env file not found!"
        exit 1
    fi
fi

# Navigate to Django directory
cd "$DJANGO_DIR" || exit 1

echo "Current directory: $(pwd)"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d "../venv" ]; then
    echo "Note: No virtual environment found. Using system Python."
    echo "Make sure required packages are installed."
    echo ""
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "Activating virtual environment..."
    source ../venv/bin/activate
fi

# Check if Python dependencies are installed
echo "Checking Python dependencies..."
python3 -c "import django" 2>/dev/null || {
    echo "Error: Django is not installed!"
    echo "Please install dependencies: pip install -r ../requirements.txt"
    exit 1
}

echo "Django is installed."
echo ""

# Run migrations
echo "Running database migrations..."
python3 manage.py migrate --no-input

# Collect static files
echo ""
echo "Collecting static files..."
python3 manage.py collectstatic --no-input

# Start Django development server
echo ""
echo "=========================================="
echo "Starting Django development server..."
echo "Access the application at: http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

python3 manage.py runserver 8000
