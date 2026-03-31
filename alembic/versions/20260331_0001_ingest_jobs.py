"""Add ingest_jobs and ingest_job_passes tables for DB-backed ingest tracking.

Revision ID: 20260331_0001
Revises: 20260330_0001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260331_0001"
down_revision = "20260330_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_ingest_jobs_workspace_status", "ingest_jobs", ["workspace_id", "status"])
    op.create_index("idx_ingest_jobs_created", "ingest_jobs", ["created_at"])

    op.create_table(
        "ingest_job_passes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingest_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_name", sa.Text, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("output_path", sa.Text, nullable=True),
        sa.Column("artifact_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_ingest_job_pass", "ingest_job_passes", ["ingest_job_id", "pass_name"])
    op.create_index("idx_ingest_job_passes_job", "ingest_job_passes", ["ingest_job_id", "ordinal"])


def downgrade() -> None:
    op.drop_index("idx_ingest_job_passes_job")
    op.drop_constraint("uq_ingest_job_pass", "ingest_job_passes")
    op.drop_table("ingest_job_passes")
    op.drop_index("idx_ingest_jobs_created")
    op.drop_index("idx_ingest_jobs_workspace_status")
    op.drop_table("ingest_jobs")
