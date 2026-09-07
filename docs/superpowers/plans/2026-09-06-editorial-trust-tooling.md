# Plan: Editorial & Trust Tooling

Combined spec + plan. Groups three related TODO items that all serve the same purpose: giving a human reviewer real leverage over what the corpus says, ahead of the ingestion volume the resilience-corpus plan is about to add.

## 1. Editorial auth flow

**Problem:** `/review` and `/ingest` on the frontend are bearer-token surfaces gated by a paste-the-key login. Workable for a single operator, not for outside reviewers.

**Plan:**
1. Decide the minimum viable model: reuse the existing `api_keys` table (it already has `expire_at`/rotation) with a `role`/`scope` column added, rather than building a new auth system. Check `src/capability_commons/db/models.py`'s `ApiKey` model for what's already there before adding anything.
2. Add a real sign-in form on the frontend that exchanges credentials (or an invite-issued key) for a session, rather than requiring a reviewer to know and paste a raw bearer token.
3. Display the current key's scope/role in the UI so a reviewer knows what they can and can't do (e.g., "can approve reviews" vs. "can only comment").
4. This is a prerequisite for opening `/review` to anyone outside the current single-operator workflow — sequence it before inviting outside reviewers, not after.

## 2. Citation QA dashboard

**Problem:** citation precision is only visible in aggregate, via `/v1/public/metrics`. There's no per-object view where a reviewer can see a specific citation, jump to the source excerpt, and mark it good/bad.

**Plan:**
1. Backend: a route (likely under `/v1/reviews/` or a new `/v1/audit/citations`) that lists an object's evidence spans alongside the source excerpt they cite, joined from `evidence_spans`/`evidence_sources`.
2. Frontend: a reviewer-facing page — one row per citation, source excerpt inline, approve/flag action.
3. This becomes directly relevant once the resilience-corpus ingestion plan lands new sources: use the first FEMA/USDA/OSHA batch as the dogfooding case for this dashboard rather than building it against synthetic data.

## 3. Contradiction detection pipeline

**Problem:** schema and endpoints for contradictions exist (`contradiction_cases` table, review routes), but nothing opens a contradiction automatically — it's fully manual today.

**Plan (scoped narrow on purpose — this is a Tier 3 item, not urgent):**
1. Start with same-domain, same-slug-prefix heuristic: when a new object is published with claims that numerically or categorically conflict with an existing published object in the same domain (e.g. two different recommended chlorine-treatment ratios for `water.treatment-selection`), flag for review rather than trying full semantic contradiction detection.
2. This is naturally exercised by the corpus-ingestion plan too — FEMA and USDA may describe water treatment or food safety slightly differently; that's a real, low-stakes test case rather than a synthetic one.
3. Do not attempt cross-source LLM-judged contradiction detection in this pass — that's the Tier 4 "cross-source contradiction detection" item, deliberately later.

## Sequencing note

All three are more useful *after* the resilience-corpus ingestion plan produces real reviewable content than before it. If prioritizing, do editorial auth first (it gates who can even use the other two), then citation QA (dogfood it on the new ingestion batch), then contradiction detection last.
