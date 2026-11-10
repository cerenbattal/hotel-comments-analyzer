"""Initial schema: reports and daily score snapshots.

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.String(300), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_hotel_id", "reports", ["hotel_id"])

    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hotel_id", sa.String(300), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("scale_max", sa.Float(), nullable=False),
        sa.Column("score_10", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("hotel_id", "source", "day"),
    )
    op.create_index("ix_score_snapshots_hotel_id", "score_snapshots", ["hotel_id"])


def downgrade() -> None:
    op.drop_table("score_snapshots")
    op.drop_table("reports")
