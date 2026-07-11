# JusAds Cloud Deployment — Amazon Lightsail

Production deployment for the JusAds platform on Amazon Lightsail.

**Live URL:** https://jusads.com

## Architecture

```
Internet → Nginx (port 80/443)
              ├── /          → Frontend (React static build)
              ├── /api/      → FastAPI backend (port 8000 internal)
              ├── /ws/       → WebSocket (backend)
              └── HTTP → 301 redirect to HTTPS
```

## Current Setup

| Resource | Details |
|----------|---------|
| Instance | Lightsail `small_3_0` (2 GB RAM, 2 vCPU, 60 GB SSD) |
| Region | ap-southeast-1 (Singapore) |
| Static IP | 13.229.193.5 |
| Domain | jusads.com (Namecheap DNS → A record to 13.229.193.5) |
| SSL | Let's Encrypt (expires Oct 9, 2026, auto-renews) |
| Cost | ~$10/month |

## File Structure

```
cloud/
├── README.md                  # This file
├── docker-compose.yml         # Production compose (backend + frontend + nginx)
├── nginx.conf                 # Nginx reverse proxy with HTTPS
├── Dockerfile.backend         # Backend production build
├── Dockerfile.frontend        # Frontend multi-stage build (npm → nginx)
├── .env.production.template   # Template for secrets (never commit real values)
├── .env.production            # Real secrets (gitignored, server-only)
├── setup-server.sh            # One-time server setup script
├── deploy.sh                  # Deployment script (pull + rebuild + restart)
├── pull-secrets.sh            # Optional: pull secrets from AWS SSM
├── setup-https.sh             # Let's Encrypt HTTPS setup
├── certbot/                   # SSL certificates (gitignored, server-only)
└── .gitignore                 # Ignore .env.production and certbot/
```

---

## Setup From Scratch (full walkthrough)

### Prerequisites

- AWS CLI configured (`aws configure` with your access key)
- GitHub Personal Access Token (for private repo clone)
- Domain name with DNS pointed to server IP

### 1. Create Lightsail Instance

From **local PowerShell**:

```powershell
# Create instance (Singapore, $10/month plan)
aws lightsail create-instances --instance-names jusads-prod --availability-zone ap-southeast-1a --blueprint-id ubuntu_22_04 --bundle-id small_3_0 --key-pair-name jusads-key
```

> **SSH Key Note:** See the "SSH Key Gotchas" section below if creating keys via CLI.
> The easiest path is to create the instance from the **Lightsail web console** and
> download the default `.pem` key from Account → SSH Keys.

### 2. Attach Static IP & Open Ports

```powershell
aws lightsail allocate-static-ip --static-ip-name jusads-ip
aws lightsail attach-static-ip --static-ip-name jusads-ip --instance-name jusads-prod
aws lightsail open-instance-public-ports --instance-name jusads-prod --port-info fromPort=80,toPort=80,protocol=tcp
aws lightsail open-instance-public-ports --instance-name jusads-prod --port-info fromPort=443,toPort=443,protocol=tcp
```

Get the IP:
```powershell
aws lightsail get-static-ip --static-ip-name jusads-ip --query "staticIp.ipAddress" --output text
```

### 3. Point DNS

In **Namecheap** → Domain List → Manage → Advanced DNS:

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A Record | `@` | `13.229.193.5` | Automatic |
| A Record | `www` | `13.229.193.5` | Automatic |

Wait 5-10 minutes, verify: `nslookup jusads.com`

### 4. SSH into the Server

**Easiest method:** Lightsail console → click instance → orange "Connect using SSH" button.

Or from local terminal:
```powershell
ssh -i C:\Users\tanwa\.ssh\ken.pem ubuntu@13.229.193.5
```

### 5. Install Docker (on the server)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo apt-get install -y docker-compose-plugin
newgrp docker
docker --version
docker compose version
```

### 6. Clone the Repo

```bash
sudo mkdir -p /opt/jusads
sudo chown $USER:$USER /opt/jusads
cd /opt/jusads
git clone https://TanWaiKen:<GITHUB_TOKEN>@github.com/TanWaiKen/FYP.git .
```

> Replace `<GITHUB_TOKEN>` with a Personal Access Token (repo scope).
> Generate at: https://github.com/settings/tokens
> **REVOKE the token after cloning** if you used it inline.

### 7. Configure Secrets

```bash
cd cloud
cp .env.production.template .env.production
nano .env.production   # Fill in real API keys from your local backend/.env
```

### 8. Get HTTPS Certificate

```bash
docker compose stop nginx   # Free up port 80
sudo apt-get update && sudo apt-get install -y certbot
sudo certbot certonly --standalone -d jusads.com -d www.jusads.com --non-interactive --agree-tos --email your-email@gmail.com
sudo mkdir -p /opt/jusads/FYP/cloud/certbot/conf
sudo cp -rL /etc/letsencrypt/ /opt/jusads/FYP/cloud/certbot/conf/
sudo chmod -R 755 /opt/jusads/FYP/cloud/certbot/
```

### 9. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

### 10. Verify

```bash
docker compose ps          # All 3 containers should be "Up"
curl -I https://jusads.com # Should return HTTP/1.1 200 OK
```

---

## Redeploying After Code Changes

After pushing to `main` on GitHub:

```bash
ssh -i C:\Users\tanwa\.ssh\ken.pem ubuntu@13.229.193.5
cd /opt/jusads/FYP/cloud
git pull origin main
docker compose up -d --build
```

Or use the deploy script:
```bash
./deploy.sh
```

---

## SSL Certificate Renewal

The cert auto-renews via certbot's systemd timer. But after renewal, you need to
recopy the certs to the Docker-accessible path and restart nginx:

```bash
sudo cp -rL /etc/letsencrypt/ /opt/jusads/FYP/cloud/certbot/conf/
sudo chmod -R 755 /opt/jusads/FYP/cloud/certbot/
cd /opt/jusads/FYP/cloud
docker compose restart nginx
```

> TODO: Automate this with a cron job or post-renewal hook.

---

## SSH Key Gotchas (Windows + Lightsail)

This section documents issues encountered during initial setup:

### Problem: `Load key "...jusads-key.pem": invalid format`

**Root cause:** PowerShell's `>` redirect operator writes files in UTF-16 encoding.
SSH requires UTF-8/ASCII. The key file looks correct when opened but has invisible
BOM (Byte Order Mark) characters that corrupt the format.

**What doesn't work:**
```powershell
# BAD — writes UTF-16
aws lightsail create-key-pair --key-pair-name jusads-key --query "privateKeyBase64" --output text > ~/.ssh/jusads-key.pem
```

**What works:**
```powershell
# GOOD — forces ASCII encoding
$key = aws lightsail create-key-pair --key-pair-name jusads-key --query "privateKeyBase64" --output text
[System.IO.File]::WriteAllText("$HOME\.ssh\jusads-key.pem", $key)
```

### Problem: `UNPROTECTED PRIVATE KEY FILE` in WSL

**Root cause:** Windows `/mnt/c/` filesystem doesn't support Linux `chmod`.
All files show as 0555 regardless of chmod attempts.

**Fix:** Copy the key to WSL's native filesystem:
```bash
mkdir -p ~/.ssh
cp /mnt/c/Users/tanwa/.ssh/jusads-key.pem ~/.ssh/jusads-key.pem
chmod 400 ~/.ssh/jusads-key.pem
ssh -i ~/.ssh/jusads-key.pem ubuntu@13.229.193.5
```

### Problem: `REMOTE HOST IDENTIFICATION HAS CHANGED`

**Root cause:** You recreated the instance (same IP, different host key).

**Fix:**
```powershell
ssh-keygen -R 13.229.193.5
```

### Recommendation

**Skip all of this.** The simplest SSH approach:
1. Create instance from the **Lightsail web console**
2. Download the default `.pem` from Account → SSH Keys
3. Save it to `C:\Users\tanwa\.ssh\ken.pem` (or wherever)
4. Use the **browser-based SSH** (orange button in console) for setup
5. Use local SSH only when you need it later:
   ```powershell
   ssh -i C:\Users\tanwa\.ssh\ken.pem ubuntu@13.229.193.5
   ```

---

## Troubleshooting

### Backend shows "unhealthy"

```bash
docker logs jusads-backend --tail 50
```

Common causes:
- Missing secrets in `.env.production` (check SUPABASE_URL, SUPABASE_KEY)
- No `/health` endpoint in the FastAPI app
- Import errors due to missing Python packages in requirements.txt

### Port 443 connection timeout

Check Lightsail firewall:
```powershell
aws lightsail get-instance-port-states --instance-name jusads-prod
```

If 443 is missing:
```powershell
aws lightsail open-instance-public-ports --instance-name jusads-prod --port-info fromPort=443,toPort=443,protocol=tcp
```

### Docker permission denied

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Nginx cert path error

Certs are mapped as: `./certbot/conf` → `/etc/letsencrypt` in the container.
Since we copied `/etc/letsencrypt/` INTO `certbot/conf/`, the actual path inside
the container is:
```
/etc/letsencrypt/letsencrypt/live/jusads.com/fullchain.pem
```

Verify on server:
```bash
ls /opt/jusads/FYP/cloud/certbot/conf/letsencrypt/live/jusads.com/
```

### `libgl1-mesa-glx` not found during Docker build

Package was removed in Debian Trixie. Use `libgl1` instead in Dockerfile.

---

## Costs

| Resource | Cost |
|----------|------|
| Lightsail small_3_0 | ~$10/month |
| Static IP (attached) | Free |
| Domain (Namecheap) | ~$10/year |
| SSL (Let's Encrypt) | Free |
| SSM Parameter Store | Free (standard) |
| **Total** | **~$11/month** |
