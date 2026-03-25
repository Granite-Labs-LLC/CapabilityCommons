"""Add expire_at to api_keys table for key rotation support.

Revision ID: 20260325_0001
Revises: 20260323_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260325_0001"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "expire_at")
