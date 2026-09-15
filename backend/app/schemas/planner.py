from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

PlannerItemType = Literal["task", "reminder", "follow_up", "meeting"]
PlannerPriority = Literal["low", "normal", "high", "urgent"]
PlannerStatus = Literal["pending", "completed", "dismissed"]


class PlannerItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(None, max_length=4000)
    item_type: PlannerItemType = "task"
    priority: PlannerPriority = "normal"
    due_at: datetime | None = None
    organization_id: UUID | None = None
    school_id: UUID | None = None
    organization_subscription_id: UUID | None = None
    school_subscription_id: UUID | None = None
    assigned_to: UUID | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class PlannerItemUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = Field(None, max_length=4000)
    item_type: PlannerItemType | None = None
    priority: PlannerPriority | None = None
    status: PlannerStatus | None = None
    due_at: datetime | None = None
    organization_id: UUID | None = None
    school_id: UUID | None = None
    organization_subscription_id: UUID | None = None
    school_subscription_id: UUID | None = None
    assigned_to: UUID | None = None
    metadata_json: dict[str, Any] | None = None


class PlannerItemOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    item_type: str
    source: str
    priority: str
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    completed_by: UUID | None
    organization_id: UUID | None
    organization_name: str | None = None
    school_id: UUID | None
    school_name: str | None = None
    organization_subscription_id: UUID | None
    school_subscription_id: UUID | None
    assigned_to: UUID | None
    created_by: UUID | None
    metadata_json: dict[str, Any]
    action_path: str | None = None
    created_at: datetime
    updated_at: datetime


class PlannerAgendaItem(BaseModel):
    id: str
    title: str
    description: str | None = None
    item_type: str
    source: str
    priority: str
    status: str
    due_at: datetime | None
    organization_id: UUID | None = None
    organization_name: str | None = None
    school_id: UUID | None = None
    school_name: str | None = None
    action_path: str | None = None
    is_auto: bool = False


class PlannerAgendaOut(BaseModel):
    generated_at: datetime
    days: int
    items: list[PlannerAgendaItem]