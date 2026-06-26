"""add position to projects (manual drag-reorder ordering)

Revision ID: 0005_project_position
Revises: 0004_coerce_ready_to_open
Create Date: 2026-06-26

Adds a non-null integer `position` column to projects so the web UI can persist
a manual left-to-right tab order (drag to reorder). Existing rows are backfilled
to dense 0..N-1 in `created_at` order — the order they rendered in before this
change — using a portable per-row loop so it works on Postgres (prod) and SQLite
(test fallback) alike. list_projects orders by (position, created_at).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_project_position"
down_revision = "0004_coerce_ready_to_open"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill dense positions in created_at order (the prior implicit order).
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM projects ORDER BY created_at")).fetchall()
    for i, row in enumerate(rows):
        bind.execute(
            sa.text("UPDATE projects SET position = :pos WHERE id = :id"),
            {"pos": i, "id": row[0]},
        )


def downgrade() -> None:
    op.drop_column("projects", "position")
