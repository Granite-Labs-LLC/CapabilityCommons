"""Gold-query evaluation harness (EVAL-1).

Hits POST /v1/public/ask and POST /v1/search against a running backend for
each entry in the gold YAML, scores top-N recall and answer-citation
precision, and writes a markdown report. Designed to be cheap enough to
run on every PR and informative enough to spot regressions.

Usage:
    python -m capability_commons.cli.eval run \\
        --gold eval/gold/queries.yaml \\
        --api  http://127.0.0.1:8100 \\
        --out  eval/reports/2026-05-14.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml


@dataclass
class GoldEntry:
    query: str
    intent: str | None = None
    expects_any: list[str] = field(default_factory=list)
    expects_all: list[str] = field(default_factory=list)
    min_citations: int = 2
    language: str = "en"
    top_n: int = 5


@dataclass
class QueryResult:
    entry: GoldEntry
    ask_ok: bool
    ask_intent_match: bool | None
    ask_has_action_now: bool
    ask_citation_count: int
    ask_top_slugs: list[str]
    search_ok: bool
    search_top_slugs: list[str]
    error: str | None = None

    @property
    def expects_any_hit(self) -> bool:
        if not self.entry.expects_any:
            return True  # no constraint
        return any(s in self.search_top_slugs for s in self.entry.expects_any)

    @property
    def expects_all_hit(self) -> bool:
        if not self.entry.expects_all:
            return True
        return all(s in self.search_top_slugs for s in self.entry.expects_all)

    @property
    def passed(self) -> bool:
        return (
            self.ask_ok
            and self.search_ok
            and self.expects_any_hit
            and self.expects_all_hit
            and self.ask_citation_count >= self.entry.min_citations
        )


def _load_gold(path: Path) -> list[GoldEntry]:
    raw = yaml.safe_load(path.read_text())
    return [GoldEntry(**r) for r in raw]


async def _run_one(client: httpx.AsyncClient, entry: GoldEntry) -> QueryResult:
    ask_top: list[str] = []
    search_top: list[str] = []
    ask_intent_match: bool | None = None
    ask_has_action_now = False
    ask_citation_count = 0
    ask_ok = search_ok = False
    error: str | None = None

    try:
        ask_resp = await client.post("/v1/public/ask", json={"query": entry.query, "max_results": entry.top_n})
        ask_resp.raise_for_status()
        data = ask_resp.json()
        ask_ok = True
        ask_has_action_now = bool(data.get("action_now"))
        ask_citation_count = len(data.get("citations") or [])
        ask_top = [r.get("slug", "") for r in (data.get("related_objects") or [])]
        # Pull citation slugs too — they're typically the strongest signal.
        ask_top += [c.get("slug", "") for c in (data.get("citations") or [])]
        ask_top = list(dict.fromkeys(s for s in ask_top if s))  # de-dup, preserve order
        if entry.intent:
            ask_intent_match = data.get("resolved_intent") == entry.intent
    except Exception as e:  # noqa: BLE001
        error = f"ask: {type(e).__name__}: {e}"

    try:
        search_resp = await client.post(
            "/v1/search",
            json={"query": entry.query, "top_k": entry.top_n, "only_published": True},
        )
        search_resp.raise_for_status()
        data = search_resp.json()
        search_ok = True
        search_top = [h.get("slug", "") for h in (data.get("hits") or [])]
    except Exception as e:  # noqa: BLE001
        error = (error + " | " if error else "") + f"search: {type(e).__name__}: {e}"

    return QueryResult(
        entry=entry,
        ask_ok=ask_ok,
        ask_intent_match=ask_intent_match,
        ask_has_action_now=ask_has_action_now,
        ask_citation_count=ask_citation_count,
        ask_top_slugs=ask_top,
        search_ok=search_ok,
        search_top_slugs=search_top,
        error=error,
    )


def _render_report(results: list[QueryResult], api_base: str) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    intent_checked = [r for r in results if r.entry.intent]
    intent_correct = sum(1 for r in intent_checked if r.ask_intent_match)
    cited = sum(1 for r in results if r.ask_citation_count >= 2)
    with_action_now = sum(1 for r in results if r.ask_has_action_now)

    lines = [
        "# Capability Commons retrieval eval",
        "",
        f"- Run at: {datetime.now(timezone.utc).isoformat()}",
        f"- API: `{api_base}`",
        f"- Queries: {total}",
        f"- **Passed: {passed} / {total}** ({passed / total * 100:.0f}%)",
        f"- Intent correct: {intent_correct} / {len(intent_checked)}",
        f"- ≥2 citations: {cited} / {total}",
        f"- Has action_now: {with_action_now} / {total}",
        "",
        "## Per-query results",
        "",
        "| ✓ | Query | Intent | Citations | action_now | Top hits |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r.passed else "❌"
        intent_cell = (
            "—" if r.entry.intent is None
            else ("✓" if r.ask_intent_match else f"✗ ({r.entry.intent})")
        )
        action = "yes" if r.ask_has_action_now else "—"
        top = ", ".join(r.search_top_slugs[:3]) or "—"
        lines.append(
            f"| {mark} | {r.entry.query[:60]} | {intent_cell} | "
            f"{r.ask_citation_count} | {action} | `{top}` |"
        )

    failures = [r for r in results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines.append(f"### {r.entry.query}")
            lines.append(f"- error: `{r.error or 'none'}`")
            if not r.expects_any_hit:
                lines.append(
                    f"- expects_any missed: `{r.entry.expects_any}`; "
                    f"got `{r.search_top_slugs[:r.entry.top_n]}`"
                )
            if not r.expects_all_hit:
                lines.append(
                    f"- expects_all missed: `{r.entry.expects_all}`; "
                    f"got `{r.search_top_slugs[:r.entry.top_n]}`"
                )
            if r.ask_citation_count < r.entry.min_citations:
                lines.append(
                    f"- citations: {r.ask_citation_count} < {r.entry.min_citations}"
                )
            if r.ask_intent_match is False:
                lines.append(
                    f"- intent mismatch: expected `{r.entry.intent}`"
                )
            lines.append("")

    return "\n".join(lines)


async def _run(api_base: str, gold: Path, out: Path | None) -> int:
    entries = _load_gold(gold)
    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as client:
        results = await asyncio.gather(*[_run_one(client, e) for e in entries])

    report = _render_report(results, api_base)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"Wrote {out}")
    else:
        print(report)

    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} passed", file=sys.stderr)
    return 0 if passed == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cc-eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run the gold-query eval against a backend")
    run.add_argument("--gold", type=Path, default=Path("eval/gold/queries.yaml"))
    run.add_argument("--api", type=str, default="http://127.0.0.1:8100")
    run.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return asyncio.run(_run(args.api, args.gold, args.out))
    return 1


if __name__ == "__main__":
    sys.exit(main())
