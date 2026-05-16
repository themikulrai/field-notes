"""add ui_filter to projects

Revision ID: 0002_project_ui_filter
Revises: 0001_initial
Create Date: 2026-05-15

Adds nullable `ui_filter` column on the projects table. Used by the MCP
`set_filter` tool + the web's Zustand store reacting to `ui.filter_changed`
SSE events. Values must be one of the literal CellStatus strings or "all".
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_project_ui_filter"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("ui_filter", sa.String(length=16), nullable=True),
    )
    # SQLite needs batch mode to add a CHECK constraint after the fact; on
    # Postgres this is a no-op via batch's "copy_from" pathway only when
    # render_as_batch is on. We rely on the bind dialect to skip the
    # check-add gracefully on dialects that already support it inline.
    with op.batch_alter_table("projects") as batch_op:
        batch_op.create_check_constraint(
            "ck_projects_ui_filter",
            "ui_filter IS NULL OR ui_filter IN ('all','in_progress','open','verified','rejected')",
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("ck_projects_ui_filter", type_="check")
    op.drop_column("projects", "ui_filter")
