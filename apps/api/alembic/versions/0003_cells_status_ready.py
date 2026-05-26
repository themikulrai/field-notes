"""extend cells.status check constraint with 'ready'

Revision ID: 0003_cells_status_ready
Revises: 0002_project_ui_filter
Create Date: 2026-05-26

`append_visual_sandbox(finalize=True)` flips a cell to status='ready'
once the chunked sandbox upload completes. The existing ck_cells_status
constraint allows ('in_progress','open','verified','rejected') only,
so we drop and recreate it with 'ready' included.
"""

from __future__ import annotations

from alembic import op

revision = "0003_cells_status_ready"
down_revision = "0002_project_ui_filter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cells") as batch_op:
        batch_op.drop_constraint("ck_cells_status", type_="check")
        batch_op.create_check_constraint(
            "ck_cells_status",
            "status IS NULL OR status IN ('in_progress','open','verified','rejected','ready')",
        )


def downgrade() -> None:
    # Coerce any 'ready' rows back to 'verified' before reinstating the
    # narrower constraint, otherwise the downgrade fails on real data.
    op.execute("UPDATE cells SET status = 'verified' WHERE status = 'ready'")
    with op.batch_alter_table("cells") as batch_op:
        batch_op.drop_constraint("ck_cells_status", type_="check")
        batch_op.create_check_constraint(
            "ck_cells_status",
            "status IS NULL OR status IN ('in_progress','open','verified','rejected')",
        )
