from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FunnelCrossEntryBehavior(str, enum.Enum):
    allow = "allow"
    deny = "deny"


class FunnelStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


class ScheduledTaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_deeplink: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tags: Mapped[list[UserTag]] = relationship(back_populates="user", cascade="all, delete-orphan")
    funnel_states: Mapped[list[UserFunnelState]] = relationship(back_populates="user", cascade="all, delete-orphan")
    purchases: Mapped[list[Purchase]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserTag(Base):
    __tablename__ = "user_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag", name="uq_user_tags"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="tags")


class Funnel(Base):
    __tablename__ = "funnels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_key: Mapped[str | None] = mapped_column(String(120), unique=True, index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cross_entry_behavior: Mapped[FunnelCrossEntryBehavior] = mapped_column(
        SAEnum(FunnelCrossEntryBehavior, name="funnelcrossentrybehavior"),
        default=FunnelCrossEntryBehavior.deny,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    steps: Mapped[list[FunnelStep]] = relationship(
        back_populates="funnel",
        cascade="all, delete-orphan",
        order_by="FunnelStep.order",
    )


class FunnelStep(Base):
    __tablename__ = "funnel_steps"
    __table_args__ = (
        UniqueConstraint("funnel_id", "step_key", name="uq_funnel_step_key"),
        Index("ix_funnel_steps_funnel_order", "funnel_id", "order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    funnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funnels.id", ondelete="CASCADE"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    funnel: Mapped[Funnel] = relationship(back_populates="steps")


class UserFunnelState(Base):
    __tablename__ = "user_funnel_state"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True, nullable=False)
    funnel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funnels.id", ondelete="CASCADE"), index=True, nullable=False)
    current_step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("funnel_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[FunnelStatus] = mapped_column(
        SAEnum(FunnelStatus, name="funnelstatus"),
        default=FunnelStatus.active,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="funnel_states")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True, nullable=False)
    funnel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("funnels.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="paymentstatus"),
        default=PaymentStatus.pending,
        nullable=False,
    )
    payment_provider_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="purchases")
    funnel: Mapped[Funnel | None] = relationship()


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[ScheduledTaskStatus] = mapped_column(
        SAEnum(ScheduledTaskStatus, name="scheduledtaskstatus"),
        default=ScheduledTaskStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)