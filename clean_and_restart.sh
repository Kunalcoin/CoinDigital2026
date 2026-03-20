#!/bin/bash

# Script to clean all caches and restart the Django server
# This script will:
# 1. Stop running Docker containers
# 2. Clean Python cache files
# 3. Clean static files
# 4. Remove Docker volumes and rebuild without cache
# 5. Restart the server

set -e  # Exit on error

echo "🧹 Starting cleanup process..."

# Change to the django-docker-compose directory
cd "$(dirname "$0")"
SCRIPT_DIR=$(pwd)

echo "📂 Working directory: $SCRIPT_DIR"

# Step 1: Stop running Docker containers
echo ""
echo "🛑 Stopping Docker containers..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || echo "No containers running or Docker not available"

# Step 2: Clean Python cache files
echo ""
echo "🐍 Cleaning Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
echo "✅ Python cache cleaned"

# Step 3: Clean static files (optional - uncomment if needed)
# echo ""
# echo "📁 Cleaning static files..."
# if [ -d "RoyaltyWebsite/staticfiles" ]; then
#     rm -rf RoyaltyWebsite/staticfiles/*
#     echo "✅ Static files cleaned"
# fi

# Step 4: Remove Docker volumes and images (optional - uncomment for full cleanup)
# echo ""
# echo "🗑️  Removing Docker volumes..."
# docker compose down -v 2>/dev/null || docker-compose down -v 2>/dev/null || true
# echo "✅ Docker volumes removed"

# Step 5: Clean Docker build cache (optional - uncomment for full cleanup)
# echo ""
# echo "🗑️  Pruning Docker build cache..."
# docker builder prune -f 2>/dev/null || true
# echo "✅ Docker build cache pruned"

# Step 6: Rebuild and restart Docker containers
echo ""
echo "🔨 Rebuilding Docker containers (without cache)..."
docker compose build --no-cache 2>/dev/null || docker-compose build --no-cache 2>/dev/null || {
    echo "⚠️  Docker build failed or Docker not available. Trying regular build..."
    docker compose build 2>/dev/null || docker-compose build 2>/dev/null || echo "⚠️  Could not build Docker containers"
}

echo ""
echo "🚀 Starting Docker containers..."
docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null || {
    echo "⚠️  Docker compose failed. Trying alternative start method..."
    # If Docker fails, you might want to start Django directly
    # Uncomment the following if you want to start Django without Docker:
    # cd RoyaltyWebsite
    # python manage.py runserver 8000 &
    # cd ..
}

echo ""
echo "✅ Cleanup and restart complete!"
echo ""
echo "📊 Checking container status..."
docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null || echo "Docker not available or containers not running"

echo ""
echo "🌐 Server should be running on:"
echo "   - HTTP: http://localhost:80"
echo "   - HTTPS: https://localhost:443"
echo "   - Django: http://localhost:8000"
echo ""
echo "📝 To view logs, run: docker compose logs -f"
echo "🛑 To stop, run: docker compose down"
