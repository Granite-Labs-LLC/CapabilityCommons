"""Add version index on object_files.

The object_files table itself ships with the initial schema
(migrations/sql/0001_initial.sql); this migration only adds the
lookup index used by list-files queries.

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02
"""
from __future__ import annotations

from alembic import op

revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_object_files_version "
        "ON object_files(context_object_version_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_object_files_version")
