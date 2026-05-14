# Capability Commons retrieval eval (EVAL-1)

A small harness that runs a curated set of gold queries against the
backend and scores whether the system surfaces the expected
capabilities. Designed to be cheap enough to run on every PR.

## Files

- `gold/queries.yaml` — the gold query set. Add entries here; the
  schema is documented in the file header.
- `reports/` — markdown reports written by the harness (gitignored).

## Run

```bash
# Against a local backend
python -m capability_commons.cli.eval run \
    --gold eval/gold/queries.yaml \
    --api  http://127.0.0.1:8100 \
    --out  eval/reports/$(date +%Y-%m-%d).md

# Print to stdout instead of writing a file
python -m capability_commons.cli.eval run --api http://127.0.0.1:8100
```

Exits non-zero when any query fails — suitable for CI gating once we
trust the gold set.

## What gets scored

Per query:

- **Search top-N** — does at least one of `expects_any` appear in
  `/v1/search` hits? Are all of `expects_all` present?
- **Ask citations** — does `/v1/public/ask` return at least
  `min_citations` (default 2)?
- **Ask action_now** — did the composer produce a smallest-viable
  starting action? (Informational; not a hard gate.)
- **Intent match** — does `resolved_intent` match the gold `intent`?
  (Informational; surfaces in the failure block.)

## Adding queries

Pick the gold answer slugs from `/v1/public/objects` or by clicking
through `/explore` on the site. Use `expects_any` for queries with
several reasonable answers; use `expects_all` only when there's a
specific shortlist the system must return.
