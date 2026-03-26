# Deploy Checklist — Capability Commons Full Stack

End-to-end deployment sequence for the Capability Commons backend (Linux server) and frontend (Replit). Follow phases in order.

For detailed instructions on each phase, see:
- **Backend:** [PRODUCTION_DEPLOY.md](PRODUCTION_DEPLOY.md)
- **Frontend:** [CapabilityCommonsSite Replit Guide](../../CapabilityCommonsSite/docs/REPLIT_DEPLOY.md)
- **Local dev / seeding:** [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)

---

## Phase 1: Backend on Linux Server

- [ ] **1.1** Clone the repo and create a deploy user
  ```bash
  git clone https://github.com/Granite-Labs-LLC/CapabilityCommons.git
  cd CapabilityCommons
  ```

- [ ] **1.2** Configure environment
  ```bash
  cp .env.production .env
  # Edit .env: set POSTGRES_PASSWORD, DOMAIN, CORS_ORIGINS, and API keys
  ```

- [ ] **1.3** Start all services (API + Postgres + Caddy TLS + backup — all in Docker Compose)
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  docker compose ps  # db, api, caddy, backup should all be running
  ```

- [ ] **1.5** Run migrations
  ```bash
  docker compose exec api alembic upgrade head
  ```

- [ ] **1.6** Seed pass 1 — 25 capability nodes
  ```bash
  docker compose exec api python -m capability_commons.cli.seed \
    --data-dir /app/expanded_seed
  # Expected: 25 objects created, 77 edges
  ```

- [ ] **1.7** Seed pass 2 — 24 curriculum nodes
  ```bash
  docker compose exec api python -m capability_commons.cli.seed \
    --data-dir /app/capability_commons_module_seed_pack_v1
  # Expected: 24 objects created, 98 edges
  ```

- [ ] **1.8** Verify Caddy is serving TLS (included in Docker Compose — no separate install needed)
  ```bash
  curl -sf https://your-domain.com/health
  # → {"status":"ok"}
  ```

- [ ] **1.9** Configure firewall
  ```bash
  sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
  sudo ufw enable
  # Do NOT expose port 8100 directly
  ```

- [ ] **1.10** Verify backend
  ```bash
  curl https://api.capabilitycommons.org/health
  # → {"status":"ok"}

  curl https://api.capabilitycommons.org/v1/public/objects | python3 -c \
    "import sys, json; print(f'{len(json.load(sys.stdin))} objects')"
  # → 49 objects

  curl https://api.capabilitycommons.org/v1/public/graph | python3 -c \
    "import sys, json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')"
  # → 49 nodes, 175 edges
  ```

- [ ] **1.11** Verify backups are running (automated via Docker Compose)
  ```bash
  docker compose logs backup --tail=5
  # Should show daily backup entries
  ```
  For manual backup: `./deploy/backup.sh`
  For restore: `./deploy/restore.sh backups/cc_YYYYMMDD_HHMMSS.sql.gz`

---

## Phase 2: Frontend on Replit

- [ ] **2.1** Import `CapabilityCommonsSite` repo into Replit (or upload files)

- [ ] **2.2** Set Secrets in Replit
  | Key | Value |
  |-----|-------|
  | `PUBLIC_API_URL` | `https://api.capabilitycommons.org` |
  | `SITE` | `https://your-repl-slug.replit.app` |

- [ ] **2.3** Configure `.replit` file
  ```toml
  run = "npm run build && npx serve dist -l 3000"
  [env]
  PUBLIC_API_URL = "https://api.capabilitycommons.org"
  SITE = "https://your-repl-slug.replit.app"
  [deployment]
  run = ["sh", "-c", "npm run build && npx serve dist -l 3000"]
  build = ["sh", "-c", "npm install"]
  ```

- [ ] **2.4** Update CORS on the backend to include the Replit URL
  ```bash
  # On the Linux server, edit .env:
  CORS_ORIGINS=["https://your-repl-slug.replit.app"]
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
  ```

- [ ] **2.5** Build and verify page count
  ```bash
  npm install
  npm run build
  # ~120+ pages = live API connected
  # ~70 pages = mock fallback (API unreachable — check CORS / URL)
  ```

- [ ] **2.6** Serve or deploy
  ```bash
  npx serve dist -l 3000          # Dev preview
  # Or use Replit Deployments → Static → build: "npm install && npm run build" → output: "dist"
  ```

---

## Phase 3: Verify End-to-End

- [ ] **3.1** Landing page — stats strip shows "49 capabilities"
  → `https://your-site/`

- [ ] **3.2** Graph explorer — 49 nodes with colored types (blue, green, amber, purple, orange) and edges
  → `https://your-site/explore`

- [ ] **3.3** Module detail page — structured data renders (week, learning objectives, delivery profile)
  → `https://your-site/explore/module.01-truth-tools-and-ai`

- [ ] **3.4** Skill guide page — prerequisites and next steps display with links
  → `https://your-site/explore/foundation.verify-and-cite`

- [ ] **3.5** Syllabus — week cards link to real module pages
  → `https://your-site/syllabus`

- [ ] **3.6** Search — returns live results from the API
  → `https://your-site/search` (try "water storage")

- [ ] **3.7** Domain pages — filtered objects per domain
  → `https://your-site/domains`

- [ ] **3.8** AI tutor — sends retrieval requests to backend
  → `https://your-site/ask`

---

## Post-Deploy

- **Custom domain:** Add to Replit Deployments, update `SITE` secret, add to `CORS_ORIGINS` on backend, rebuild frontend.
- **New data:** After seeding new objects, rebuild the frontend (`npm run build` on Replit) — static pages won't update automatically.
- **Updates:** `git pull && docker compose up -d --build && docker compose exec api alembic upgrade head` on the server. Rebuild frontend if API schema changed.
- **Monitoring:** Point an uptime monitor at `https://api.capabilitycommons.org/health`.
