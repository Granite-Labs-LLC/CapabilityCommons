# Production Deployment — Linux Server

This guide deploys the CapabilityCommons backend (FastAPI + Postgres 16 + pgvector) on a dedicated Linux machine, with the frontend (CapabilityCommonsSite) deployed separately on Replit or another static host.

## Prerequisites

- Ubuntu 22.04+ or Debian 12+ (any Linux with Docker works)
- Docker Engine 24+ and Docker Compose v2 (`docker compose` subcommand)
- At least 2 GB RAM, 10 GB disk
- A domain name pointed to the server (recommended for SSL)
- Firewall access to ports 22, 80, 443

## 1. Server Setup

```bash
# Create a deploy user (optional but recommended)
sudo adduser deploy
sudo usermod -aG docker deploy
su - deploy

# Clone the repo
git clone https://github.com/Granite-Labs-LLC/CapabilityCommons.git
cd CapabilityCommons

# Install Docker if not present
# See https://docs.docker.com/engine/install/ubuntu/
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with production values:

```bash
APP_ENV=production
APP_NAME=Capability Commons API
API_V1_PREFIX=/v1

# Use a strong password — this overrides the docker-compose default
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD@db:5432/capability_commons
DATABASE_ECHO=false

# Auth — enable in production
AUTH_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PUBLIC_PER_MINUTE=300

# CORS — set to your frontend URL(s)
CORS_ORIGINS=["https://your-site.replit.app"]

# Embeddings — optional, leave empty for FTS-only search
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
```

Generate an API key for the frontend (if auth is enabled):

```bash
docker compose exec api python -m capability_commons.cli.keys create --name prod-site
# Save the key — it's shown only once
```

## 3. Docker Compose Production Override

Create `docker-compose.prod.yml` alongside the existing `docker-compose.yml`:

```yaml
# docker-compose.prod.yml — production overrides
services:
  db:
    environment:
      POSTGRES_PASSWORD: YOUR_STRONG_PASSWORD
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G

  api:
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD@db:5432/capability_commons
      AUTH_ENABLED: "true"
      CORS_ORIGINS: '["https://your-site.replit.app"]'
    restart: always
    deploy:
      resources:
        limits:
          memory: 512M
```

## 4. Start Services

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Wait for healthy status:

```bash
docker compose ps
# Both db and api should show "healthy"
```

## 5. Run Migrations and Seed

```bash
# Apply all database migrations
docker compose exec api alembic upgrade head

# Seed pass 1: 25 capability nodes
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/expanded_seed

# Seed pass 2: 24 curriculum nodes (12 modules + 12 assessments)
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/capability_commons_module_seed_pack_v1
```

Expected output:
```
Seed complete: 25 objects created, 0 skipped, 50 prerequisite edges (from YAML), 27 CSV edges created, 0 CSV edges skipped (duplicates)
Seed complete: 24 objects created, 0 skipped, 0 prerequisite edges (from YAML), 98 CSV edges created, 0 CSV edges skipped (duplicates)
```

## 6. Reverse Proxy with Caddy (Auto-SSL)

Caddy automatically provisions and renews HTTPS certificates.

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```
api.capabilitycommons.org {
    reverse_proxy localhost:8100
}
```

Replace `api.capabilitycommons.org` with your domain. Start Caddy:

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
```

Caddy will automatically obtain an SSL certificate from Let's Encrypt.

### Alternative: nginx + certbot

```bash
sudo apt install nginx certbot python3-certbot-nginx

# Create /etc/nginx/sites-available/capabilitycommons:
```

```nginx
server {
    server_name api.capabilitycommons.org;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/capabilitycommons /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.capabilitycommons.org
```

## 7. Firewall

```bash
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP (Caddy redirect)
sudo ufw allow 443/tcp    # HTTPS (Caddy)
# Do NOT expose 8100 — only the reverse proxy should reach it
sudo ufw enable
```

## 8. Verify

```bash
# Health check
curl https://api.capabilitycommons.org/health
# → {"status":"ok"}

# Object count (should return 49 objects)
curl https://api.capabilitycommons.org/v1/public/objects | python3 -c \
  "import sys, json; print(f'{len(json.load(sys.stdin))} objects')"

# Graph endpoint
curl https://api.capabilitycommons.org/v1/public/graph | python3 -c \
  "import sys, json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')"
```

## 9. Backups

### Automated daily backup script

Create `/home/deploy/backup-db.sh`:

```bash
#!/bin/bash
BACKUP_DIR=/home/deploy/backups
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

docker compose -f /home/deploy/CapabilityCommons/docker-compose.yml \
  exec -T db pg_dump -U postgres capability_commons \
  | gzip > "$BACKUP_DIR/cc_$TIMESTAMP.sql.gz"

# Keep only the last 14 days
find "$BACKUP_DIR" -name "cc_*.sql.gz" -mtime +14 -delete

echo "Backup complete: cc_$TIMESTAMP.sql.gz"
```

```bash
chmod +x /home/deploy/backup-db.sh
```

### Cron job (daily at 2 AM)

```bash
crontab -e
# Add:
0 2 * * * /home/deploy/backup-db.sh >> /home/deploy/backups/backup.log 2>&1
```

### Restore from backup

```bash
gunzip -c backups/cc_20260319_020000.sql.gz | \
  docker compose exec -T db psql -U postgres capability_commons
```

## 10. Monitoring

### Logs

```bash
# Follow all logs
docker compose logs -f

# API logs only
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

### Health check for uptime monitoring

Point any uptime monitor (UptimeRobot, Healthchecks.io, etc.) at:

```
GET https://api.capabilitycommons.org/health
```

Expected response: `{"status":"ok"}` with HTTP 200.

### Disk space

```bash
# Check pgdata volume size
docker system df -v | grep pgdata

# Overall disk usage
df -h /
```

## 11. Updating

```bash
cd /home/deploy/CapabilityCommons
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run any new migrations
docker compose exec api alembic upgrade head
```

## 12. Connecting the Frontend

The CapabilityCommonsSite (Astro static site) connects to this API at build time and at runtime.

**Build time:** Astro fetches all objects and graph data to generate static pages.

**Runtime:** React islands (search, graph explorer, AI tutor) make client-side API calls.

This means the API must be accessible:
1. From the Replit build environment (build time)
2. From users' browsers (runtime)

On the frontend, set the environment variable:

```bash
PUBLIC_API_URL=https://api.capabilitycommons.org
```

See the [CapabilityCommonsSite Replit deployment guide](../../CapabilityCommonsSite/docs/REPLIT_DEPLOY.md) for full frontend deployment instructions.

### CORS checklist

Ensure your production `.env` includes the frontend URL:

```bash
CORS_ORIGINS=["https://your-site.replit.app"]
```

If you add a custom domain to the frontend, add it too:

```bash
CORS_ORIGINS=["https://your-site.replit.app","https://capabilitycommons.org"]
```

Restart the API after changing CORS settings:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
```
