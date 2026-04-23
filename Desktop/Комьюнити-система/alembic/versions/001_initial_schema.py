"""initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-22 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


funnelcrossentrybehavior = postgresql.ENUM(
    "allow",
    "deny",
    name="funnelcrossentrybehavior",
)
funnelstatus = postgresql.ENUM(
    "active",
    "paused",
    "completed",
    name="funnelstatus",
)
paymentstatus = postgresql.ENUM(
    "pending",
    "paid",
    "failed",
    "refunded",
    name="paymentstatus",
)
scheduledtaskstatus = postgresql.ENUM(
    "pending",
    "processing",
    "done",
    "failed",
    name="scheduledtaskstatus",
)


def upgrade() -> None:
    op.execute(sa.text("DROP TYPE IF EXISTS funnelcrossentrybehavior CASCADE"))
    op.execute(sa.text("DROP TYPE IF EXISTS funnelstatus CASCADE"))
    op.execute(sa.text("DROP TYPE IF EXISTS paymentstatus CASCADE"))
    op.execute(sa.text("DROP TYPE IF EXISTS scheduledtaskstatus CASCADE"))

    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("source_deeplink", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_users_source_deeplink"), "users", ["source_deeplink"], unique=False)

    op.create_table(
        "funnels",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("entry_key", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cross_entry_behavior", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("entry_key", name="uq_funnels_entry_key"),
    )
    op.create_index(op.f("ix_funnels_entry_key"), "funnels", ["entry_key"], unique=False)

    op.create_table(
        "user_tags",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("tag", sa.String(length=128), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "tag", name="pk_user_tags"),
        sa.UniqueConstraint("user_id", "tag", name="uq_user_tags"),
    )

    op.create_table(
        "funnel_steps",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("funnel_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("step_key", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["funnel_id"], ["funnels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("funnel_id", "step_key", name="uq_funnel_step_key"),
    )
    op.create_index("ix_funnel_steps_funnel_order", "funnel_steps", ["funnel_id", "order"], unique=False)

    op.create_table(
        "user_funnel_state",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("funnel_id", sa.Uuid(), nullable=False),
        sa.Column("current_step_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_step_id"], ["funnel_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["funnel_id"], ["funnels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_funnel_state_user_id"), "user_funnel_state", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_funnel_state_funnel_id"), "user_funnel_state", ["funnel_id"], unique=False)

    op.create_table(
        "purchases",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_provider_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("payment_provider_id", name="uq_purchases_payment_provider_id"),
    )
    op.create_index(op.f("ix_purchases_user_id"), "purchases", ["user_id"], unique=False)

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("execute_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_scheduled_tasks_user_id"), "scheduled_tasks", ["user_id"], unique=False)
    op.create_index(op.f("ix_scheduled_tasks_execute_at"), "scheduled_tasks", ["execute_at"], unique=False)

    op.execute(sa.text("CREATE TYPE funnelcrossentrybehavior AS ENUM ('allow', 'deny')"))
    op.execute(sa.text("CREATE TYPE funnelstatus AS ENUM ('active', 'paused', 'completed')"))
    op.execute(sa.text("CREATE TYPE paymentstatus AS ENUM ('pending', 'paid', 'failed', 'refunded')"))
    op.execute(sa.text("CREATE TYPE scheduledtaskstatus AS ENUM ('pending', 'processing', 'done', 'failed')"))

    op.execute(
        sa.text(
            "ALTER TABLE funnels ALTER COLUMN cross_entry_behavior TYPE funnelcrossentrybehavior "
            "USING cross_entry_behavior::text::funnelcrossentrybehavior"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE user_funnel_state ALTER COLUMN status TYPE funnelstatus "
            "USING status::text::funnelstatus"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE purchases ALTER COLUMN status TYPE paymentstatus "
            "USING status::text::paymentstatus"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE scheduled_tasks ALTER COLUMN status TYPE scheduledtaskstatus "
            "USING status::text::scheduledtaskstatus"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduled_tasks_execute_at"), table_name="scheduled_tasks")
    op.drop_index(op.f("ix_scheduled_tasks_user_id"), table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")

    op.drop_index(op.f("ix_purchases_user_id"), table_name="purchases")
    op.drop_table("purchases")

    op.drop_index(op.f("ix_user_funnel_state_funnel_id"), table_name="user_funnel_state")
    op.drop_index(op.f("ix_user_funnel_state_user_id"), table_name="user_funnel_state")
    op.drop_table("user_funnel_state")

    op.drop_index("ix_funnel_steps_funnel_order", table_name="funnel_steps")
    op.drop_table("funnel_steps")

    op.drop_table("user_tags")

    op.drop_index(op.f("ix_funnels_entry_key"), table_name="funnels")
    op.drop_table("funnels")

    op.drop_index(op.f("ix_users_source_deeplink"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    scheduledtaskstatus.drop(bind, checkfirst=True)
    paymentstatus.drop(bind, checkfirst=True)
    funnelstatus.drop(bind, checkfirst=True)
    funnelcrossentrybehavior.drop(bind, checkfirst=True)