"""Add object_files table.

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "object_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "context_object_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("context_object_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_store_key", sa.Text, nullable=False),
        sa.Column("media_type", sa.Text, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=True),
        sa.Column("checksum", sa.Text, nullable=True),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="byte_size_non_negative"),
    )
    op.create_index("idx_object_files_version", "object_files", ["context_object_version_id"])


def downgrade() -> None:
    op.drop_index("idx_object_files_version", table_name="object_files")
    op.drop_table("object_files")
