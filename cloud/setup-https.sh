#!/bin/bash
# ============================================================
# JusAds — Set up HTTPS with Let's Encrypt (Certbot)
# Run AFTER the initial deployment is working on HTTP.
# ============================================================

set -e

DOMAIN=${1:-""}

if [ -z "$DOMAIN" ]; then
    echo "Usage: ./setup-https.sh yourdomain.com"
    exit 1
fi

echo "=== Setting up HTTPS for ${DOMAIN} ==="

# Install certbot
sudo apt-get install -y certbot

# Stop nginx temporarily
docker compose stop nginx

# Get certificate
sudo certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email admin@${DOMAIN}

# Copy certs to Docker-accessible location
sudo mkdir -p certbot/conf
sudo cp -rL /etc/letsencrypt/ certbot/conf/

echo ""
echo "=== Certificate obtained! ==="
echo ""
echo "Next steps:"
echo "  1. Edit nginx.conf — uncomment the HTTPS server block"
echo "  2. Replace 'yourdomain.com' with '${DOMAIN}' in nginx.conf"
echo "  3. Run: docker compose up -d"
echo ""
echo "Auto-renewal is handled by certbot's systemd timer."
echo "Run 'sudo certbot renew --dry-run' to verify."
