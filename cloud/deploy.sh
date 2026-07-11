#!/bin/bash
# ============================================================
# JusAds — Deploy / Redeploy script
# Run from the cloud/ directory on the server.
# ============================================================

set -e

echo "=== JusAds Deployment ==="
echo ""

# Navigate to project root (one level up from cloud/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Pull latest code
echo "[1/4] Pulling latest code..."
git pull origin main

# Enter cloud directory
cd cloud

# Check secrets exist
if [ ! -f .env.production ]; then
    echo "ERROR: .env.production not found!"
    echo "Copy the template: cp .env.production.template .env.production"
    echo "Then fill in your real values."
    exit 1
fi

# Build and deploy
echo "[2/4] Building containers..."
docker compose build --no-cache

echo "[3/4] Starting services..."
docker compose up -d

echo "[4/4] Checking health..."
sleep 5
docker compose ps

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Services running at:"
echo "  Frontend: http://$(curl -s ifconfig.me)"
echo "  API:      http://$(curl -s ifconfig.me)/api/"
echo ""
