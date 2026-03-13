"""Initial Capability Commons Agentic Data Lite schema."""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20260313_0001"
down_revision = None
branch_labels = None
depends_on = None


def _sql_file() -> str:
    return (Path(__file__).resolve().parents[2] / "migrations" / "sql" / "0001_initial.sql").read_text()


def upgrade() -> None:
    op.execute(_sql_file())


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally manual for the initial schema migration.")
