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
    # sa.false() is dialect-portable: renders `0` on SQLite (which has no native
    # boolean — a literal "false" would be stored as the STRING 'false' and never
    # match a `WHERE archived IS 0` filter, silently hiding every existing row)
    # and `false` on Postgres.
    op.add_column(
        "projects",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("projects", "archived")
