"""Add metadata_json to evidence_spans for citation provenance.

Revision ID: 20260329_0001
Revises: 20260325_0001
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260329_0001"
down_revision = "20260325_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_spans",
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("evidence_spans", "metadata")
