"""Add conversation_turns table for multi-turn ask conversations.

Revision ID: 20260330_0001
Revises: 20260329_0001
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260330_0001"
down_revision = "20260329_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_number", sa.Integer, nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("resolved_intent", sa.Text, nullable=False),
        sa.Column("retrieval_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("answer_summary", sa.Text, nullable=True),
        sa.Column("context_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_conversation_turns_conversation", "conversation_turns", ["conversation_id", "turn_number"])
    op.create_index("idx_conversation_turns_workspace", "conversation_turns", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_conversation_turns_workspace")
    op.drop_index("idx_conversation_turns_conversation")
    op.drop_table("conversation_turns")
