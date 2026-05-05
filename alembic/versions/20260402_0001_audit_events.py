"""Add audit_events table.

Revision ID: 20260402_0001
Revises: 20260401_0001
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260402_0001"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


AUDIT_EVENT_VALUES = (
    "object_created",
    "version_created",
    "version_published",
    "version_deprecated",
    "edge_created",
    "edge_removed",
    "review_submitted",
    "object_edited",
)


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(*AUDIT_EVENT_VALUES, name="audit_event_type"),
            nullable=False,
        ),
        sa.Column(
            "actor_key_id",
            UUID(as_uuid=True),
            sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_object_id",
            UUID(as_uuid=True),
            sa.ForeignKey("context_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("context_object_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_edge_id",
            UUID(as_uuid=True),
            sa.ForeignKey("edges.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "idx_audit_workspace_created",
        "audit_events",
        ["workspace_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_audit_object_created",
        "audit_events",
        ["target_object_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_object_created", table_name="audit_events")
    op.drop_index("idx_audit_workspace_created", table_name="audit_events")
    op.drop_table("audit_events")
    sa.Enum(name="audit_event_type").drop(op.get_bind(), checkfirst=True)
