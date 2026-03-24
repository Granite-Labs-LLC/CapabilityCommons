"""CLI entry point: python -m capability_commons.cli.ingest <command> <project>."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[4] / "ingestion" / "projects"


def get_llm_client(args, manifest_llm=None):
    """Build LLMClient from CLI args + manifest config."""
    from capability_commons.cli.ingest.llm_client import LLMClient

    llm = manifest_llm or {}

    def _pick(attr, fallback_attr, default):
        """Pick CLI arg if not None, else manifest value, else default."""
        val = getattr(args, attr, None)
        if val is not None:
            return val
        return getattr(llm, fallback_attr, default) if hasattr(llm, fallback_attr) else default

    return LLMClient(
        base_url=_pick("base_url", "base_url", "https://api.openai.com/v1"),
        api_key=getattr(args, "api_key", None),
        model=_pick("model", "model", "gpt-4o"),
        temperature=_pick("temperature", "temperature", 0.2),
    )


def add_llm_args(parser):
    """Add common LLM override flags to a subparser."""
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--base-url", help="Override LLM API base URL")
    parser.add_argument("--api-key", help="Override API key")
    parser.add_argument("--temperature", type=float, help="Override temperature")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")


def cmd_init(args):
    from capability_commons.cli.ingest.project import IngestProject
    import shutil
    sources = [{
        "id": args.source_id,
        "file": f"sources/{Path(args.source).name}",
        "title": args.source_title,
        "source_kind": args.source_kind,
    }]
    proj = IngestProject.init(PROJECTS_ROOT, args.project, sources)
    # Copy source file
    dest = proj.root / "sources" / Path(args.source).name
    shutil.copy2(args.source, dest)
    print(f"Project initialized: {proj.root}")


def cmd_parse(args):
    from capability_commons.cli.ingest.parse import run_parse
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    run_parse(proj)


def cmd_extract(args):
    from capability_commons.cli.ingest.extract import run_extract
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_extract(proj, client, sections_filter=args.sections, yes=args.yes))


def cmd_draft(args):
    from capability_commons.cli.ingest.draft import run_draft
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_draft(proj, client, skip_existing=args.skip_existing, slugs_filter=args.slugs, yes=args.yes))


def cmd_cite(args):
    from capability_commons.cli.ingest.cite import run_cite
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_cite(proj, client, slugs_filter=args.slugs, yes=args.yes))


def cmd_canonicalize(args):
    from capability_commons.cli.ingest.canonicalize import run_canonicalize
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_canonicalize(proj, client, yes=args.yes))


def cmd_edges(args):
    from capability_commons.cli.ingest.edges import run_edges
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_edges(proj, client, yes=args.yes))


def cmd_bundles(args):
    from capability_commons.cli.ingest.bundles import run_bundles
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_bundles(proj, client, skip_existing=args.skip_existing, slugs_filter=args.slugs, yes=args.yes))


def cmd_load(args):
    from capability_commons.cli.ingest.load import run_load
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    asyncio.run(run_load(proj, db_url=args.db_url, publish=args.publish, dry_run=args.dry_run))


def cmd_validate(args):
    from capability_commons.cli.ingest.project import IngestProject
    from capability_commons.cli.ingest.validate import print_validation_report, run_validate
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    report = run_validate(proj)
    print_validation_report(report)
    sys.exit(1 if report.errors else 0)


def cmd_status(args):
    from capability_commons.cli.ingest.project import IngestProject
    from capability_commons.cli.ingest.validate import run_status
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    run_status(proj)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m capability_commons.cli.ingest",
        description="Capability Commons ingestion pipeline — convert source documents into knowledge objects.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # init
    p = subs.add_parser("init", help="Initialize a new ingestion project")
    p.add_argument("project", help="Project name")
    p.add_argument("--source", required=True, help="Path to source PDF")
    p.add_argument("--source-id", required=True, help="Evidence source ID (e.g., src.permatil.refbook.2006)")
    p.add_argument("--source-title", required=True, help="Source document title")
    p.add_argument("--source-kind", default="BOOK", help="Source kind (BOOK, FILE, STANDARD, etc.)")
    p.set_defaults(func=cmd_init)

    # parse
    p = subs.add_parser("parse", help="Pass 0: Parse PDFs into segments")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_parse)

    # extract
    p = subs.add_parser("extract", help="Pass 1: Generate extraction matrix from segments")
    p.add_argument("project", help="Project name")
    p.add_argument("--sections", help="Filter to sections matching this string")
    add_llm_args(p)
    p.set_defaults(func=cmd_extract)

    # draft
    p = subs.add_parser("draft", help="Pass 2: Draft canonical YAML objects")
    p.add_argument("project", help="Project name")
    p.add_argument("--skip-existing", action="store_true", help="Skip slugs that already have draft files")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_draft)

    # cite
    p = subs.add_parser("cite", help="Pass 3: Link citations to source spans")
    p.add_argument("project", help="Project name")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_cite)

    # canonicalize
    p = subs.add_parser("canonicalize", help="Pass 4: Deduplicate and canonicalize drafts")
    p.add_argument("project", help="Project name")
    add_llm_args(p)
    p.set_defaults(func=cmd_canonicalize)

    # edges
    p = subs.add_parser("edges", help="Pass 5: Extract edges from object set")
    p.add_argument("project", help="Project name")
    add_llm_args(p)
    p.set_defaults(func=cmd_edges)

    # bundles
    p = subs.add_parser("bundles", help="Pass 6: Generate six-part bundles")
    p.add_argument("project", help="Project name")
    p.add_argument("--skip-existing", action="store_true", help="Skip objects that already have bundles")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_bundles)

    # load
    p = subs.add_parser("load", help="Pass 7: Validate and load to database")
    p.add_argument("project", help="Project name")
    p.add_argument("--publish", action="store_true", help="Set lifecycle_state to PUBLISHED")
    p.add_argument("--dry-run", action="store_true", help="Validate and write output only, no DB")
    p.add_argument("--db-url", help="Database URL (default: from .env)")
    p.set_defaults(func=cmd_load)

    # validate
    p = subs.add_parser("validate", help="Validate drafts and edges")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_validate)

    # status
    p = subs.add_parser("status", help="Show project status")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
