"""Add external_id to evidence_sources for ingestion pipeline.

Revision ID: 20260323_0001
Revises: 20260317_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260323_0001"
down_revision = "20260317_0001"


def upgrade() -> None:
    op.add_column(
        "evidence_sources",
        sa.Column("external_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_evidence_sources_external_id",
        "evidence_sources",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_sources_external_id", "evidence_sources")
    op.drop_column("evidence_sources", "external_id")
