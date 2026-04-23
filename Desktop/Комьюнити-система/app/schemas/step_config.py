from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActionUrl(BaseModel):
    type: Literal["url"]
    value: str


class ActionGotoStep(BaseModel):
    type: Literal["goto_step"]
    value: str


class ActionAddTag(BaseModel):
    type: Literal["add_tag"]
    value: str


class ActionPayProduct(BaseModel):
    type: Literal["pay_product"]
    value: str


ButtonAction = Annotated[Union[ActionUrl, ActionGotoStep, ActionAddTag, ActionPayProduct], Field(discriminator="type")]


class Button(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=1, max_length=64)
    action: ButtonAction


class TextMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["text"]
    content: str = Field(max_length=4000)
    delay_after: int = Field(ge=0, default=0)


class PhotoMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["photo"]
    file_id: str
    caption: Optional[str] = Field(default=None, max_length=1024)
    delay_after: int = Field(ge=0, default=0)


class DocumentMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["document"]
    file_id: str
    caption: Optional[str] = Field(default=None, max_length=1024)
    delay_after: int = Field(ge=0, default=0)


class ButtonGroup(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: Literal["buttons"]
    buttons: list[Button] = Field(default_factory=list)


Block = Annotated[Union[TextMessage, PhotoMessage, DocumentMessage, ButtonGroup], Field(discriminator="type")]


class StepConfig(BaseModel):
    delay_before_seconds: int = Field(ge=0, default=0)
    wait_for_payment: bool = False
    blocks: list[Block] = Field(default_factory=list)
    add_tags_after: list[str] = Field(default_factory=list)
    next_step: str = "auto"