"""add archived flag to projects (soft-hide from the tab strip)

Revision ID: 0006_project_archived
Revises: 0005_project_position
Create Date: 2026-07-01

Adds a non-null boolean `archived` column (default false) so projects can be
hidden from the tab strip without deleting their data. Portable server_default
keeps it working on Postgres (prod) and SQLite (test fallback).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_project_archived"
down_revision = "0005_project_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("projects", "archived")
