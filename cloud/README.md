# JusAds Cloud Deployment — Amazon Lightsail

Production deployment for the JusAds platform on Amazon Lightsail 2 GB Ubuntu.

## Architecture

```
Internet → Nginx (port 80/443)
              ├── /          → Frontend (static files served by Nginx)
              └── /api/      → FastAPI backend (Docker, port 8000 internal)
```

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- SSH key pair for Lightsail access
- Domain name (optional, for HTTPS)

## Quick Start (from PowerShell on Windows)

### 1. Create SSH Key Pair (already done ✓)

```powershell
# You already ran this — key saved at ~/.ssh/jusads-key.pem
aws lightsail create-key-pair --key-pair-name jusads-key --query "privateKeyBase64" --output text > ~/.ssh/jusads-key.pem
```

### 2. Create Lightsail Instance

```powershell
# Create instance (Singapore region, small_3_0 = 2GB RAM / 2 vCPU / 60GB SSD — ~$10/month)
aws lightsail create-instances --instance-names jusads-prod --availability-zone ap-southeast-1a --blueprint-id ubuntu_22_04 --bundle-id small_3_0 --key-pair-name jusads-key
```

### 3. Attach Static IP

```powershell
aws lightsail allocate-static-ip --static-ip-name jusads-ip
aws lightsail attach-static-ip --static-ip-name jusads-ip --instance-name jusads-prod
```

### 4. Open Ports (HTTP + HTTPS)

```powershell
aws lightsail open-instance-public-ports --instance-name jusads-prod --port-info fromPort=80,toPort=80,protocol=tcp
aws lightsail open-instance-public-ports --instance-name jusads-prod --port-info fromPort=443,toPort=443,protocol=tcp
```

### 5. Get Your Static IP

```powershell
aws lightsail get-static-ip --static-ip-name jusads-ip --query "staticIp.ipAddress" --output text
```

### 6. SSH into the Instance

```powershell
ssh -i ~/.ssh/jusads-key.pem ubuntu@<STATIC_IP>
```

### 7. Run Server Setup (on the Ubuntu server via SSH)

```bash
# Clone your repo
cd /opt
sudo mkdir -p jusads && sudo chown $USER:$USER jusads
git clone https://github.com/YOUR_USERNAME/Langhub-main.git jusads
cd jusads/cloud

# Run one-time setup
chmod +x setup-server.sh deploy.sh pull-secrets.sh setup-https.sh
./setup-server.sh
```

Then log out and back in (for Docker group), and continue:

### 8. Configure Secrets (on the server)

```bash
cd /opt/jusads/cloud
cp .env.production.template .env.production
nano .env.production   # Fill in real values
```

### 9. Deploy

```bash
./deploy.sh
```

## File Structure

```
cloud/
├── README.md                  # This file
├── docker-compose.yml         # Production compose (backend + nginx)
├── nginx.conf                 # Nginx reverse proxy config
├── Dockerfile.backend         # Backend production Dockerfile
├── Dockerfile.frontend        # Frontend build + Nginx serve
├── .env.production.template   # Template for secrets (never commit real values)
├── setup-server.sh            # One-time server setup script
├── deploy.sh                  # Deployment script (pull + rebuild + restart)
└── .gitignore                 # Ignore .env.production
```

## Secrets Management

Secrets are stored in `.env.production` on the server only — never committed to Git.

### Option A: Server-local .env (simple)

1. Copy `.env.production.template` → `.env.production`
2. Fill in real values
3. `docker compose up -d`

### Option B: AWS SSM Parameter Store (more secure)

```bash
# Store secrets
aws ssm put-parameter --name "/jusads/SUPABASE_URL" --value "https://..." --type SecureString
aws ssm put-parameter --name "/jusads/SUPABASE_KEY" --value "eyJ..." --type SecureString
# ... repeat for each secret

# Pull secrets into .env.production (run on server)
./pull-secrets.sh
```

## Updating

After pushing code to GitHub:

```bash
ssh ubuntu@<STATIC_IP>
cd /opt/jusads
./deploy.sh
```

## Costs

| Resource | Cost |
|----------|------|
| Lightsail 2 GB (small_3_0) | ~$10/month |
| Static IP (attached) | Free |
| SSM Parameter Store (Standard) | Free |
| **Total** | **~$12/month** |
