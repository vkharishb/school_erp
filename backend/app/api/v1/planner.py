from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_superuser
from app.db.session import get_db
from app.models.organization import Organization
from app.models.planner import PlatformPlannerItem
from app.models.school import School, SchoolConfiguration
from app.models.subscription import OrganizationSubscription, SchoolSubscription, SubscriptionPlan
from app.models.user import User
from app.schemas.planner import (
    PlannerAgendaItem,
    PlannerAgendaOut,
    PlannerItemCreate,
    PlannerItemOut,
    PlannerItemUpdate,
)
from app.services.audit import record_audit
from app.services.subscriptions import refresh_payment_status

router = APIRouter(prefix="/planner", tags=["Platform Planner"])


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalize_due(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _priority_for(due_at: datetime | None, *, urgent_if_past: bool = True) -> str:
    if due_at is None:
        return "normal"
    now = _utcnow()
    if urgent_if_past and due_at <= now:
        return "urgent"
    if due_at <= now + timedelta(days=7):
        return "high"
    return "normal"


def _item_action_path(item: PlatformPlannerItem) -> str | None:
    if item.school_subscription_id:
        return "/subscriptions?tab=keys"
    if item.organization_subscription_id:
        return "/subscriptions?tab=renewals"
    if item.school_id:
        return f"/schools/{item.school_id}"
    if item.organization_id:
        return f"/organizations?view=detail&organization={item.organization_id}"
    return None


async def _item_out(db: AsyncSession, item: PlatformPlannerItem) -> PlannerItemOut:
    organization_name = None
    school_name = None
    if item.organization_id:
        organization = await db.get(Organization, item.organization_id)
        organization_name = organization.name if organization else None
    if item.school_id:
        config = (
            await db.execute(
                select(SchoolConfiguration).where(SchoolConfiguration.school_id == item.school_id)
            )
        ).scalar_one_or_none()
        school = await db.get(School, item.school_id)
        school_name = config.name if config else (school.code if school else None)
    return PlannerItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        item_type=item.item_type,
        source=item.source,
        priority=item.priority,
        status=item.status,
        due_at=item.due_at,
        completed_at=item.completed_at,
        completed_by=item.completed_by,
        organization_id=item.organization_id,
        organization_name=organization_name,
        school_id=item.school_id,
        school_name=school_name,
        organization_subscription_id=item.organization_subscription_id,
        school_subscription_id=item.school_subscription_id,
        assigned_to=item.assigned_to,
        created_by=item.created_by,
        metadata_json=item.metadata_json or {},
        action_path=_item_action_path(item),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _validate_references(db: AsyncSession, payload: PlannerItemCreate | PlannerItemUpdate) -> None:
    organization_id = getattr(payload, "organization_id", None)
    school_id = getattr(payload, "school_id", None)
    organization_subscription_id = getattr(payload, "organization_subscription_id", None)
    school_subscription_id = getattr(payload, "school_subscription_id", None)
    assigned_to = getattr(payload, "assigned_to", None)

    organization = await db.get(Organization, organization_id) if organization_id else None
    if organization_id and not organization:
        raise HTTPException(status_code=404, detail="Society/Trust not found")

    school = await db.get(School, school_id) if school_id else None
    if school_id and not school:
        raise HTTPException(status_code=404, detail="School not found")
    if organization and school and school.organization_id != organization.id:
        raise HTTPException(status_code=422, detail="School does not belong to the selected Society/Trust")

    account = await db.get(OrganizationSubscription, organization_subscription_id) if organization_subscription_id else None
    if organization_subscription_id and not account:
        raise HTTPException(status_code=404, detail="Subscription account not found")
    if organization and account and account.organization_id != organization.id:
        raise HTTPException(status_code=422, detail="Subscription account does not belong to the selected Society/Trust")

    entitlement = await db.get(SchoolSubscription, school_subscription_id) if school_subscription_id else None
    if school_subscription_id and not entitlement:
        raise HTTPException(status_code=404, detail="School subscription not found")
    if school and entitlement and entitlement.school_id != school.id:
        raise HTTPException(status_code=422, detail="School subscription does not belong to the selected School")

    assignee = await db.get(User, assigned_to) if assigned_to else None
    if assigned_to and (not assignee or not assignee.is_superuser):
        raise HTTPException(status_code=422, detail="Planner tasks can only be assigned to a Platform Owner")


@router.get("/items", response_model=list[PlannerItemOut])
async def list_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_superuser)],
    status_filter: str | None = Query(None, alias="status"),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
):
    query = select(PlatformPlannerItem)
    if status_filter:
        query = query.where(PlatformPlannerItem.status == status_filter)
    if from_date:
        query = query.where(PlatformPlannerItem.due_at >= _normalize_due(from_date))
    if to_date:
        query = query.where(PlatformPlannerItem.due_at <= _normalize_due(to_date))
    rows = list((await db.execute(query.order_by(PlatformPlannerItem.due_at.asc(), PlatformPlannerItem.created_at.desc()))).scalars().all())
    return [await _item_out(db, row) for row in rows]


@router.post("/items", response_model=PlannerItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: PlannerItemCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    await _validate_references(db, payload)
    row = PlatformPlannerItem(
        **payload.model_dump(),
        source="manual",
        due_at=_normalize_due(payload.due_at),
        created_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(
        db,
        action="planner.item.created",
        user=user,
        module="planner",
        entity_type="PlatformPlannerItem",
        entity_id=row.id,
        after={"title": row.title, "due_at": row.due_at.isoformat() if row.due_at else None},
        request=request,
        target_organization_id=row.organization_id,
        target_school_id=row.school_id,
    )
    return await _item_out(db, row)


@router.patch("/items/{item_id}", response_model=PlannerItemOut)
async def update_item(
    item_id: UUID,
    payload: PlannerItemUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    row = await db.get(PlatformPlannerItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Planner item not found")
    await _validate_references(db, payload)
    changes = payload.model_dump(exclude_unset=True)
    if "due_at" in changes:
        changes["due_at"] = _normalize_due(changes["due_at"])
    for key, value in changes.items():
        setattr(row, key, value)
    if changes.get("status") == "completed" and not row.completed_at:
        row.completed_at = _utcnow()
        row.completed_by = user.id
    elif changes.get("status") in {"pending", "dismissed"}:
        row.completed_at = None
        row.completed_by = None
    await db.flush()
    await record_audit(
        db,
        action="planner.item.updated",
        user=user,
        module="planner",
        entity_type="PlatformPlannerItem",
        entity_id=row.id,
        after=changes,
        request=request,
        target_organization_id=row.organization_id,
        target_school_id=row.school_id,
    )
    return await _item_out(db, row)


@router.post("/items/{item_id}/complete", response_model=PlannerItemOut)
async def complete_item(
    item_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    row = await db.get(PlatformPlannerItem, item_id)
    if not row:
        raise HTTPException(status_code=404, detail="Planner item not found")
    row.status = "completed"
    row.completed_at = _utcnow()
    row.completed_by = user.id
    await db.flush()
    await record_audit(
        db,
        action="planner.item.completed",
        user=user,
        module="planner",
        entity_type="PlatformPlannerItem",
        entity_id=row.id,
        request=request,
        target_organization_id=row.organization_id,
        target_school_id=row.school_id,
    )
    return await _item_out(db, row)


@router.get("/agenda", response_model=PlannerAgendaOut)
async def planner_agenda(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_active_superuser)],
    days: int = Query(default=30, ge=1, le=180),
):
    now = _utcnow()
    horizon = now + timedelta(days=days)
    agenda: list[PlannerAgendaItem] = []

    manual_rows = list((await db.execute(
        select(PlatformPlannerItem)
        .where(PlatformPlannerItem.status != "dismissed")
        .order_by(PlatformPlannerItem.due_at.asc(), PlatformPlannerItem.created_at.desc())
    )).scalars().all())
    for row in manual_rows:
        item = await _item_out(db, row)
        agenda.append(PlannerAgendaItem(
            id=str(item.id),
            title=item.title,
            description=item.description,
            item_type=item.item_type,
            source=item.source,
            priority=item.priority,
            status=item.status,
            due_at=item.due_at,
            organization_id=item.organization_id,
            organization_name=item.organization_name,
            school_id=item.school_id,
            school_name=item.school_name,
            action_path=item.action_path,
            is_auto=False,
        ))

    accounts = list((await db.execute(
        select(OrganizationSubscription, Organization, SubscriptionPlan)
        .join(Organization, Organization.id == OrganizationSubscription.organization_id)
        .join(SubscriptionPlan, SubscriptionPlan.id == OrganizationSubscription.plan_id)
        .where(OrganizationSubscription.status.in_(["trial", "pending_payment", "active", "overdue"]))
    )).all())
    for account, organization, plan in accounts:
        refresh_payment_status(account)
        due_at = _normalize_due(account.due_at)
        if account.balance_amount > Decimal("0") and due_at and due_at <= horizon:
            agenda.append(PlannerAgendaItem(
                id=f"auto-payment-{account.id}",
                title="Payment follow-up due",
                description=f"{organization.name} has ₹{account.balance_amount} pending for {plan.name}.",
                item_type="follow_up",
                source="payment_due",
                priority=_priority_for(due_at),
                status="pending",
                due_at=due_at,
                organization_id=organization.id,
                organization_name=organization.name,
                action_path=f"/payments?tab=details&organization={organization.id}",
                is_auto=True,
            ))
        expires_at = _normalize_due(account.expires_at)
        if expires_at and expires_at <= horizon:
            title = "Trial conversion follow-up" if account.billing_cycle == "trial" else "Subscription renewal follow-up"
            agenda.append(PlannerAgendaItem(
                id=f"auto-expiry-{account.id}",
                title=title,
                description=f"{organization.name} {account.billing_cycle} subscription ends on {expires_at.date().isoformat()}.",
                item_type="reminder",
                source="subscription_expiry",
                priority=_priority_for(expires_at),
                status="pending",
                due_at=expires_at,
                organization_id=organization.id,
                organization_name=organization.name,
                action_path=f"/subscriptions?tab=renewals&organization={organization.id}",
                is_auto=True,
            ))

    pending_schools = list((await db.execute(
        select(SchoolSubscription, School, SchoolConfiguration, Organization)
        .join(School, School.id == SchoolSubscription.school_id)
        .join(OrganizationSubscription, OrganizationSubscription.id == SchoolSubscription.organization_subscription_id)
        .join(Organization, Organization.id == OrganizationSubscription.organization_id)
        .outerjoin(SchoolConfiguration, SchoolConfiguration.school_id == School.id)
        .where(SchoolSubscription.status == "pending_activation")
        .order_by(SchoolSubscription.created_at.asc())
    )).all())
    for entitlement, school, config, organization in pending_schools:
        due_at = _normalize_due(entitlement.created_at)
        school_name = config.name if config else school.code
        agenda.append(PlannerAgendaItem(
            id=f"auto-activation-{entitlement.id}",
            title="School activation pending",
            description=f"{school_name} is created but not activated for ERP use.",
            item_type="follow_up",
            source="pending_activation",
            priority="high",
            status="pending",
            due_at=due_at,
            organization_id=organization.id,
            organization_name=organization.name,
            school_id=school.id,
            school_name=school_name,
            action_path="/subscriptions?tab=keys",
            is_auto=True,
        ))

    agenda.sort(key=lambda item: (item.status == "completed", item.due_at is None, item.due_at or datetime.max.replace(tzinfo=UTC), item.title))
    return PlannerAgendaOut(generated_at=now, days=days, items=agenda)