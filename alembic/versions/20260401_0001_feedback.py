"""Add feedback table.

Revision ID: 20260401_0001
Revises: 20260331_0001
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260401_0001"
down_revision = "20260331_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    feedback_action = sa.Enum(
        "thumbs_up", "thumbs_down", "used_this", "report_issue",
        name="feedback_action",
    )

    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", feedback_action, nullable=False),
        sa.Column("answer_id", sa.Text, nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("object_slug", sa.Text, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ip_hash", sa.String(64), nullable=True),
    )
    op.create_index("idx_feedback_created", "feedback", ["created_at"])
    op.create_index("idx_feedback_object_slug", "feedback", ["object_slug"])


def downgrade() -> None:
    op.drop_index("idx_feedback_object_slug")
    op.drop_index("idx_feedback_created")
    op.drop_table("feedback")
    sa.Enum(name="feedback_action").drop(op.get_bind(), checkfirst=True)
