"""add funnel provenance to purchases

Revision ID: 002_purchase_funnel_id
Revises: 001_initial_schema
Create Date: 2026-04-22 00:00:00.000001
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002_purchase_funnel_id"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchases",
        sa.Column("funnel_id", sa.Uuid(), nullable=True),
    )
    op.create_index(op.f("ix_purchases_funnel_id"), "purchases", ["funnel_id"], unique=False)
    op.create_foreign_key(
        "fk_purchases_funnel_id_funnels",
        "purchases",
        "funnels",
        ["funnel_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_purchases_funnel_id_funnels", "purchases", type_="foreignkey")
    op.drop_index(op.f("ix_purchases_funnel_id"), table_name="purchases")
    op.drop_column("purchases", "funnel_id")