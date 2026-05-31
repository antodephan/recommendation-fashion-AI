"""Revision: sync_runs table + H&M product index on outfits.meta"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_hm_sync"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "job_type",
            sa.Enum("hm_catalog", "hm_trends", name="sync_job_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failed", name="sync_status"),
            nullable=False,
        ),
        sa.Column("region", sa.String(32), nullable=True),
        sa.Column("items_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_job_type", "sync_runs", ["job_type"])
    op.create_index("ix_sync_runs_created_at", "sync_runs", ["created_at"])
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_outfits_hm_product_id
        ON outfits ((meta->>'hm_product_id'))
        WHERE meta->>'hm_product_id' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outfits_hm_product_id")
    op.drop_index("ix_sync_runs_created_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_job_type", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.execute("DROP TYPE IF EXISTS sync_status")
    op.execute("DROP TYPE IF EXISTS sync_job_type")
