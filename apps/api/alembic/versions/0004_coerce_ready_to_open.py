"""coerce deprecated cells.status='ready' rows to 'open'

Revision ID: 0004_coerce_ready_to_open
Revises: 0003_cells_status_ready
Create Date: 2026-05-29

`ready` was set by append_visual_sandbox(finalize=True) but the web UI never
learned to render it (STATUSES had no 'ready' key), so opening any project with
a finalized chunked-sandbox cell threw and white-screened the whole app.

finalize now sets 'open' (a content write returning the cell to the review
queue), so 'ready' is deprecated and no longer emitted. This migration coerces
any lingering 'ready' rows to 'open' to match the new behavior and unblock the
UI. The CHECK constraint is intentionally LEFT as-is (still allows 'ready') so
the deprecated enum value stays valid and this migration is a pure, reversible
data fix with no constraint churn.
"""

from __future__ import annotations

from alembic import op

revision = "0004_coerce_ready_to_open"
down_revision = "0003_cells_status_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE cells SET status = 'open' WHERE status = 'ready'")


def downgrade() -> None:
    # One-way data fix: 'ready' is deprecated and the original status is not
    # recoverable, so downgrade is a no-op. The constraint still permits
    # 'ready', so nothing breaks.
    pass
