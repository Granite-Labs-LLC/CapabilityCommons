"""CLI for managing API keys."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.api.auth import generate_key
from capability_commons.db.models import ApiKey, Workspace


async def create_key(db_url: str, workspace_slug: str, name: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.slug == workspace_slug)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            print(f"ERROR: workspace '{workspace_slug}' not found")
            await engine.dispose()
            return

        raw_key, key_hash = generate_key()
        api_key = ApiKey(
            workspace_id=ws.id,
            key_hash=key_hash,
            name=name,
        )
        session.add(api_key)
        await session.commit()

    await engine.dispose()
    print(f"API key created for workspace '{workspace_slug}':")
    print(f"  Name: {name}")
    print(f"  Key:  {raw_key}")
    print(f"  ID:   {api_key.id}")
    print()
    print("Store this key securely — it cannot be retrieved again.")


async def revoke_key(db_url: str, key_id: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        api_key = await session.get(ApiKey, uuid.UUID(key_id))
        if api_key is None:
            print(f"ERROR: API key '{key_id}' not found")
            await engine.dispose()
            return
        if api_key.revoked_at is not None:
            print(f"API key '{key_id}' is already revoked")
            await engine.dispose()
            return

        api_key.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    await engine.dispose()
    print(f"API key '{key_id}' revoked successfully")


async def list_keys(db_url: str, workspace_slug: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.slug == workspace_slug)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            print(f"ERROR: workspace '{workspace_slug}' not found")
            await engine.dispose()
            return

        result = await session.execute(
            select(ApiKey).where(ApiKey.workspace_id == ws.id).order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()

    await engine.dispose()

    if not keys:
        print(f"No API keys for workspace '{workspace_slug}'")
        return

    print(f"API keys for workspace '{workspace_slug}':")
    for k in keys:
        status = "REVOKED" if k.revoked_at else "ACTIVE"
        print(f"  [{status}] {k.id}  {k.name}  (created {k.created_at.date()})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Manage API keys")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create")
    create_p.add_argument("--workspace", required=True, help="Workspace slug")
    create_p.add_argument("--name", required=True, help="Key name/description")
    create_p.add_argument("--db-url", default=None)

    revoke_p = sub.add_parser("revoke")
    revoke_p.add_argument("--key-id", required=True, help="API key UUID to revoke")
    revoke_p.add_argument("--db-url", default=None)

    list_p = sub.add_parser("list")
    list_p.add_argument("--workspace", required=True, help="Workspace slug")
    list_p.add_argument("--db-url", default=None)

    args = parser.parse_args()

    if args.db_url is None:
        from capability_commons.config import get_settings
        db_url = get_settings().database_url
    else:
        db_url = args.db_url

    if args.command == "create":
        asyncio.run(create_key(db_url, args.workspace, args.name))
    elif args.command == "revoke":
        asyncio.run(revoke_key(db_url, args.key_id))
    elif args.command == "list":
        asyncio.run(list_keys(db_url, args.workspace))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
