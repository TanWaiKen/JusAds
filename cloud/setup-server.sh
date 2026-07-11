#!/bin/bash
# ============================================================
# JusAds — One-time server setup for Ubuntu (Lightsail)
# Run this ONCE after creating the instance.
# ============================================================

set -e

echo "=== JusAds Server Setup ==="
echo ""

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
echo "[2/5] Installing Docker..."
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin
echo "[3/5] Installing Docker Compose..."
sudo apt-get install -y docker-compose-plugin

# Install AWS CLI (for SSM Parameter Store if needed)
echo "[4/5] Installing AWS CLI..."
sudo apt-get install -y awscli

# Create project directory
echo "[5/5] Setting up project directory..."
sudo mkdir -p /opt/jusads
sudo chown $USER:$USER /opt/jusads

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Log out and back in (for Docker group to take effect)"
echo "  2. Clone your repo:  cd /opt/jusads && git clone <your-repo-url> ."
echo "  3. Copy secrets:     cp cloud/.env.production.template cloud/.env.production"
echo "  4. Edit secrets:     nano cloud/.env.production"
echo "  5. Deploy:           cd cloud && ./deploy.sh"
echo ""
