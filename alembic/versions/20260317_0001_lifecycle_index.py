"""Add index on lifecycle_state for published-only queries.

Revision ID: 20260317_0001
Revises: 20260313_0002
"""
from alembic import op

revision = "20260317_0001"
down_revision = "20260313_0002"


def upgrade() -> None:
    op.create_index(
        "idx_context_objects_lifecycle_state",
        "context_objects",
        ["lifecycle_state"],
    )


def downgrade() -> None:
    op.drop_index("idx_context_objects_lifecycle_state", "context_objects")
