# Remaining Tier 1 Items — Operator Walkthrough

Everything automated is already in place (CI/CD, HTTPS, backups, rate limits, auth, observability). These three items require human judgment and can't be fully automated. This guide walks through each one end to end.

---

## 1. First Real Ingestion Run

**Goal:** Take one source PDF through the full 8-pass pipeline, review the output, and load it into the database — proving the pipeline works on real content.

### 1.1 Prerequisites

```bash
# From the project root, with venv active
pip install -e '.[ingest]'

# You need an OpenAI API key for LLM passes
export OPENAI_API_KEY="sk-..."
```

The `[ingest]` extra installs: marker-pdf, polars, rich, aiofiles, tiktoken, rapidfuzz.

### 1.2 Choose a Source Document

Pick something:
- **Short** (50–150 pages) to keep costs and review time manageable
- **Practical** — contains actionable skills, not just theory
- **Structured** — has headings, chapters, or sections (helps the parser)
- **Domain-relevant** — fits one of the 7 domains (water, food, shelter, power, repair, gardening, epistemics)

Good first choices: a permaculture manual chapter, a FEMA preparedness guide, a workshop handout collection.

### 1.3 Initialize the Project

```bash
python -m capability_commons.cli.ingest init my-first-source \
  --source path/to/document.pdf \
  --source-id src.author.title.year \
  --source-title "The Document Title" \
  --source-kind BOOK
```

This creates `ingestion/projects/my-first-source/` with the source copied in and a `manifest.yaml`.

### 1.4 Run Passes 0–1 (Parse and Extract)

```bash
# Pass 0: PDF → segments
python -m capability_commons.cli.ingest parse my-first-source

# Check segment count
python -m capability_commons.cli.ingest status my-first-source
```

**Review checkpoint:** Open `ingestion/projects/my-first-source/segments/segments.jsonl`. Check:
- Are headings captured correctly?
- Are page numbers preserved?
- Any garbled OCR or missing sections?

If the PDF parsed poorly, you may need to manually fix segments before continuing.

```bash
# Pass 1: Segments → extraction matrix
# For a first run, scope to one section to limit cost
python -m capability_commons.cli.ingest extract my-first-source \
  --sections "Chapter 1"
```

Each LLM pass shows estimated token count and asks for confirmation before proceeding.

**Review checkpoint:** Open `ingestion/projects/my-first-source/matrix/extraction_matrix.csv`. Check:
- Do the candidate slugs make sense?
- Are types correct (concept_note vs skill_guide vs project_blueprint)?
- Remove or edit low-confidence rows (< 0.7) before drafting

### 1.5 Run Passes 2–4 (Draft, Cite, Canonicalize)

```bash
# Pass 2: Matrix rows → full YAML objects
python -m capability_commons.cli.ingest draft my-first-source

# Pass 3: Link claims to source spans
python -m capability_commons.cli.ingest cite my-first-source

# Pass 4: Deduplicate / merge / split
python -m capability_commons.cli.ingest canonicalize my-first-source
```

**Review checkpoint:** Read 2–3 draft YAML files in `drafts/`. Check:
- Is the `markdown_body` accurate and readable?
- Are `structured_data` fields filled in (goal, deliverables, acceptance_criteria)?
- Do citations point to real segments? Is `support_strength` reasonable?
- Check `canonicalization_log.json` — were any merges/splits surprising?

### 1.6 Run Passes 5–6 (Edges and Bundles)

```bash
# Pass 5: Infer relationships between objects
python -m capability_commons.cli.ingest edges my-first-source

# Pass 6: Generate six-part learning bundles
python -m capability_commons.cli.ingest bundles my-first-source
```

**Review checkpoint:** Open `edges/edges.csv`. Check:
- Do prerequisite chains make sense? (A `prerequisite_for` B means B is unsafe/impossible without A)
- Are there obvious missing edges?
- Are there hallucinated edges between unrelated objects?

### 1.7 Validate

```bash
python -m capability_commons.cli.ingest validate my-first-source
```

This checks: required fields, valid enum values, edge integrity (source/target exist), citation coverage. Fix any errors before loading.

### 1.8 Dry Run

```bash
python -m capability_commons.cli.ingest load my-first-source --dry-run
```

This writes seed-compatible output to `output/` without touching the database. Inspect the output directory to verify everything looks right.

### 1.9 Load to Database

```bash
# Load as DRAFT (recommended for first run — review before publishing)
python -m capability_commons.cli.ingest load my-first-source

# Or load and publish immediately (only if you've reviewed everything)
python -m capability_commons.cli.ingest load my-first-source --publish
```

### 1.10 Verify in the API

```bash
# Check object count increased
curl http://localhost:8100/v1/public/objects | python3 -c \
  "import sys, json; print(f'{len(json.load(sys.stdin))} objects')"

# Check graph grew
curl http://localhost:8100/v1/public/graph | python3 -c \
  "import sys, json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')"
```

### 1.11 Cost Reference

Rough cost guidance for GPT-4o at ~$2.50/1M input tokens:

| Pass | Tokens per object | 20 objects estimate |
|------|-------------------|---------------------|
| Extract | 2,000–5,000 | $0.10–$0.25 |
| Draft | 3,000–8,000 | $0.15–$0.40 |
| Cite | 5,000–15,000 | $0.25–$0.75 |
| Canonicalize | 2,000–5,000 | $0.10–$0.25 |
| Edges | 5,000–20,000 | $0.01–$0.05 (single call) |
| Bundles | 3,000–8,000 | $0.15–$0.40 |
| **Total** | | **~$0.75–$2.10 for 20 objects** |

Use `--model gpt-4o-mini` for cheaper exploratory runs. Use `gpt-4o` for final quality.

---

## 2. Safety Review for High-Risk Content

**Goal:** Ensure objects with `risk_band: high` or `risk_band: expert_only` receive human review before being published to the public API.

### 2.1 Why This Matters

Capability Commons covers practical skills that can involve physical safety risks — water treatment, structural building, electrical work, food preservation. Objects flagged as high-risk or expert-only contain information that could cause harm if followed incorrectly. These must be reviewed by someone with domain expertise before publishing.

### 2.2 Identify Objects Needing Review

After loading ingested content (or at any time), query for unpublished high-risk objects:

```bash
# Via the API (requires auth)
curl -H "X-API-Key: YOUR_KEY" \
  "http://localhost:8100/v1/objects?lifecycle_state=draft" | \
  python3 -c "
import sys, json
objects = json.load(sys.stdin)
for obj in objects:
    rb = obj.get('risk_band', 'low')
    if rb in ('high', 'expert_only'):
        print(f\"  {rb:12s}  {obj['slug']}  —  {obj.get('canonical_title', '')}\")
"
```

Or query the database directly:

```sql
SELECT cov.slug, cov.canonical_title, cov.risk_band, cov.lifecycle_state
FROM context_object_versions cov
WHERE cov.risk_band IN ('high', 'expert_only')
  AND cov.lifecycle_state != 'published'
ORDER BY cov.risk_band DESC, cov.slug;
```

### 2.3 Review Checklist

For each high-risk or expert-only object, a reviewer with domain knowledge should verify:

| Check | Question |
|-------|----------|
| **Accuracy** | Are the procedural steps correct? Would following them produce the claimed result? |
| **Safety boundaries** | Are warnings, contraindications, and failure modes clearly stated? |
| **Prerequisites** | Are prerequisite skills correctly identified? Could someone without them hurt themselves? |
| **Risk band accuracy** | Is the risk_band rating appropriate? Should it be higher or lower? |
| **Expert-only justification** | If `expert_only`, is this truly beyond what a careful beginner should attempt? |
| **Local adaptation** | Are there climate/region/context assumptions that could be dangerous elsewhere? |
| **Citation support** | Do safety claims have source citations? Are they from authoritative sources? |
| **Missing warnings** | Are there known hazards in this domain that the object doesn't mention? |

### 2.4 Review Workflow

The system supports these lifecycle states: `DRAFT` → `IN_REVIEW` → `REVIEWED` → `VERIFIED` → `PUBLISHED`.

**Step 1: Move to IN_REVIEW**

Use the review API endpoint to submit a review:

```bash
curl -X POST -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  "http://localhost:8100/v1/reviews" \
  -d '{
    "version_id": "VERSION_UUID",
    "reviewer_note": "Starting safety review",
    "verdict": "needs_changes"
  }'
```

**Step 2: Make corrections**

If the review finds issues, edit the object's YAML source and re-load, or update via the API.

**Step 3: Verify and publish**

```bash
# Mark as verified after review passes
curl -X POST -H "X-API-Key: YOUR_KEY" \
  "http://localhost:8100/v1/reviews/VERSION_UUID/verify"

# Publish
curl -X POST -H "X-API-Key: YOUR_KEY" \
  "http://localhost:8100/v1/objects/OBJECT_UUID/versions/VERSION_UUID/publish"
```

### 2.5 Policy Recommendations

- **Never auto-publish** `risk_band: high` or `expert_only` objects. Load them as `DRAFT` and require manual review.
- **Two-reviewer rule** for `expert_only` — have two independent reviewers with domain expertise sign off.
- **Document reviewer identity** — use the `reviewer_note` field to record who reviewed and their qualifications.
- **Re-review on edit** — if a published high-risk object is edited, it should return to `IN_REVIEW` before re-publishing.

---

## 3. Secret Management

**Goal:** Move sensitive values out of `.env` files on the server and into a secrets manager, so secrets aren't stored in plaintext on disk.

### 3.1 What Needs to Be a Secret

| Value | Risk if leaked |
|-------|---------------|
| `POSTGRES_PASSWORD` | Full database access |
| `DATABASE_URL` | Contains the Postgres password |
| `OPENAI_API_KEY` | Billing charges on your OpenAI account |
| `SENTRY_DSN` | Can send fake errors to your Sentry project |
| API keys (created via CLI) | Full authenticated access to the API |
| `DEPLOY_SSH_KEY` (GitHub secret) | SSH access to your server |

### 3.2 Current State

Right now, secrets live in:
- `.env` file on each server (gitignored, but plaintext on disk)
- GitHub Actions secrets (encrypted at rest, injected as env vars at runtime)

The GitHub Actions secrets are already reasonably secure. The `.env` file on the server is the weak link.

### 3.3 Options by Complexity

#### Option A: Minimal (File Permissions)

If you're on a single VPS and don't want to add infrastructure:

```bash
# Restrict .env to the deploy user only
chmod 600 /home/deploy/CapabilityCommons/.env
chown deploy:deploy /home/deploy/CapabilityCommons/.env

# Verify
ls -la .env
# -rw------- 1 deploy deploy ... .env
```

This doesn't prevent a root compromise, but it stops other users on the server from reading secrets.

**When this is enough:** Single server, single operator, no compliance requirements.

#### Option B: Docker Secrets (No External Dependencies)

Docker Compose supports secrets natively. Secrets are stored as files, mounted read-only into containers.

**Step 1:** Create secret files:

```bash
mkdir -p /home/deploy/secrets
echo "your_strong_password" > /home/deploy/secrets/postgres_password
echo "sk-your-openai-key" > /home/deploy/secrets/openai_api_key
chmod 600 /home/deploy/secrets/*
```

**Step 2:** Reference in `docker-compose.prod.yml`:

```yaml
services:
  db:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password

  api:
    secrets:
      - postgres_password
      - openai_api_key

secrets:
  postgres_password:
    file: /home/deploy/secrets/postgres_password
  openai_api_key:
    file: /home/deploy/secrets/openai_api_key
```

**Caveat:** This requires the application to read `_FILE` suffixed env vars. Postgres supports this natively (`POSTGRES_PASSWORD_FILE`). The Capability Commons API currently reads env vars directly via pydantic-settings, so you'd need a small wrapper script or config change to read from files. For now, this is noted as a future improvement.

**When this is enough:** Single server, want secrets off disk in plaintext, no external services.

#### Option C: Cloud Secrets Manager

If you're on a cloud provider or need audit trails:

| Provider | Service | CLI |
|----------|---------|-----|
| AWS | SSM Parameter Store or Secrets Manager | `aws ssm get-parameter` |
| GCP | Secret Manager | `gcloud secrets versions access` |
| Azure | Key Vault | `az keyvault secret show` |
| Self-hosted | HashiCorp Vault | `vault kv get` |

**Pattern:** A startup script fetches secrets and writes `.env` before starting Docker Compose:

```bash
#!/usr/bin/env bash
# deploy/fetch-secrets.sh — run before docker compose up
set -euo pipefail

# Example with AWS SSM
POSTGRES_PASSWORD=$(aws ssm get-parameter --name /cc/prod/postgres_password --with-decryption --query Parameter.Value --output text)
OPENAI_API_KEY=$(aws ssm get-parameter --name /cc/prod/openai_api_key --with-decryption --query Parameter.Value --output text)
SENTRY_DSN=$(aws ssm get-parameter --name /cc/prod/sentry_dsn --with-decryption --query Parameter.Value --output text)

# Write .env from template
sed \
  -e "s|CHANGE_ME_POSTGRES|$POSTGRES_PASSWORD|g" \
  -e "s|CHANGE_ME_OPENAI|$OPENAI_API_KEY|g" \
  -e "s|CHANGE_ME_SENTRY|$SENTRY_DSN|g" \
  .env.production > .env

chmod 600 .env
echo "Secrets fetched and .env written."
```

Then update the CD workflow to call this before `docker compose up`.

**When this is right:** Multiple environments, compliance requirements, team access control needed, or you're already on a cloud provider.

### 3.4 Recommendation

For a first production deployment on a single VPS:

1. **Start with Option A** (file permissions) — it's immediate and sufficient for launch
2. **Move to Option B** (Docker secrets) when you have time — better isolation
3. **Move to Option C** (cloud secrets) if/when you add team members or compliance requirements

The important thing is that `.env` is never committed to git (it's in `.gitignore`) and that the server itself has restricted access.

---

## Checklist Summary

### First Ingestion Run
- [ ] Install ingest extras (`pip install -e '.[ingest]'`)
- [ ] Set `OPENAI_API_KEY`
- [ ] Choose and obtain source PDF
- [ ] `ingest init` — create project
- [ ] `ingest parse` — PDF to segments; review segment quality
- [ ] `ingest extract` — segments to matrix; review candidates
- [ ] `ingest draft` — matrix to YAML objects; review 2-3 drafts
- [ ] `ingest cite` — link claims to sources; check coverage
- [ ] `ingest canonicalize` — deduplicate; review merge log
- [ ] `ingest edges` — infer relationships; review edge CSV
- [ ] `ingest bundles` — generate learning bundles
- [ ] `ingest validate` — fix any errors
- [ ] `ingest load --dry-run` — inspect output
- [ ] `ingest load` — load to database
- [ ] Verify via API

### Safety Review
- [ ] Query for `risk_band: high` and `expert_only` objects in DRAFT state
- [ ] Assign domain-qualified reviewer(s)
- [ ] Complete review checklist for each object
- [ ] Submit review verdicts via API
- [ ] Publish only after review passes
- [ ] Document reviewer identity in review notes

### Secret Management
- [ ] Restrict `.env` file permissions (`chmod 600`)
- [ ] Verify `.env` is in `.gitignore`
- [ ] GitHub Actions secrets configured for CD
- [ ] (Future) Evaluate Docker secrets or cloud secrets manager
