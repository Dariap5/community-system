from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.step_config import StepConfig


class FunnelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entry_key: str | None = Field(default=None, max_length=120, pattern=r"^[a-z0-9_]+$")
    cross_entry_behavior: Literal["allow", "deny"] = "deny"


class FunnelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    entry_key: str | None = Field(default=None, max_length=120, pattern=r"^[a-z0-9_]+$")
    is_active: bool | None = None
    is_archived: bool | None = None
    cross_entry_behavior: Literal["allow", "deny"] | None = None


class StepSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order: int
    name: str
    step_key: str
    is_active: bool
    first_message_preview: str


class FunnelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    entry_key: str | None
    is_active: bool
    is_archived: bool
    cross_entry_behavior: str
    created_at: datetime
    updated_at: datetime
    steps_count: int
    active_users_count: int


class FunnelDetail(FunnelRead):
    steps: list[StepSummary] = Field(default_factory=list)


class StepCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    step_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    order: int | None = Field(default=None, ge=1)
    config: StepConfig = Field(default_factory=StepConfig)


class StepUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    step_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    is_active: bool = True
    config: StepConfig


class StepReorder(BaseModel):
    step_ids_in_order: list[UUID] = Field(min_length=1)


class StepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    funnel_id: UUID
    order: int
    name: str
    step_key: str
    is_active: bool
    config: StepConfig
    created_at: datetime
    updated_at: datetime


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    username: str | None
    first_name: str | None
    current_funnel_name: str | None
    current_step_name: str | None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class AnalyticsSummary(BaseModel):
    new_users_count: int
    total_users_count: int
    payments_count: int
    revenue_total: float
    conversion_percent: float


class FunnelAnalytics(BaseModel):
    funnel_id: UUID
    funnel_name: str
    steps_stats: list[dict[str, object]] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
