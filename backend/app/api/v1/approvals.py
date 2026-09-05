from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permissions
from app.db.session import get_db
from app.models.approval import ApprovalRequest
from app.models.fee import Payment
from app.models.user import User
from app.services.audit import record_audit

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _permission_codes(user: User) -> set[str]:
    return {rp.permission.code for ur in user.roles for rp in ur.role.permissions if rp.permission}


class ApprovalCreate(BaseModel):
    request_type: str = Field(min_length=2, max_length=100)
    entity_type: str | None = None
    entity_id: str | None = None
    reason: str | None = None
    payload: dict = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = Field(min_length=2, max_length=2000)


class ApprovalOut(BaseModel):
    id: UUID
    request_type: str
    entity_type: str | None
    entity_id: str | None
    status: str
    reason: str | None
    payload: dict
    requested_by: UUID
    decided_by: UUID | None
    decision_comment: str | None
    created_at: datetime
    decided_at: datetime | None

    model_config = {"from_attributes": True}


@router.post("", response_model=ApprovalOut, status_code=status.HTTP_201_CREATED)
async def create_approval(
    payload: ApprovalCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    approval = ApprovalRequest(
        organization_id=user.organization_id,
        school_id=user.school_id,
        campus_id=user.campus_id,
        requested_by=user.id,
        **payload.model_dump(),
    )
    db.add(approval)
    await db.flush()
    await record_audit(
        db,
        action="approval.requested",
        user=user,
        module="workflow",
        entity_type="ApprovalRequest",
        entity_id=approval.id,
        after={"request_type": approval.request_type},
        request=request,
    )
    return approval


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status_filter: str = "pending",
):
    query = select(ApprovalRequest).where(ApprovalRequest.status == status_filter)
    if user.is_superuser:
        pass
    elif user.account_type == "ORGANIZATION_ADMIN":
        query = query.where(ApprovalRequest.organization_id == user.organization_id)
    elif user.account_type == "SCHOOL_ADMIN":
        query = query.where(ApprovalRequest.school_id == user.school_id)
    elif user.campus_id:
        query = query.where(ApprovalRequest.campus_id == user.campus_id)
    else:
        query = query.where(ApprovalRequest.school_id == user.school_id)
    result = await db.execute(query.order_by(ApprovalRequest.created_at.desc()).limit(200))
    return list(result.scalars().all())


@router.post("/{approval_id}/decision", response_model=ApprovalOut)
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecision,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("approval.decide"))],
):
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not user.is_superuser:
        if user.account_type == "ORGANIZATION_ADMIN":
            if approval.organization_id != user.organization_id:
                raise HTTPException(status_code=403, detail="Not allowed")
        elif user.account_type == "SCHOOL_ADMIN":
            if approval.school_id != user.school_id:
                raise HTTPException(status_code=403, detail="Not allowed")
        elif approval.campus_id != user.campus_id:
            raise HTTPException(status_code=403, detail="Not allowed")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request has already been decided")
    if (
        approval.request_type == "fee.receipt_cancel"
        and not user.is_superuser
        and "fee.cancel.approve" not in _permission_codes(user)
    ):
        raise HTTPException(status_code=403, detail="Fee cancellation approval permission required")
    if approval.requested_by == user.id:
        raise HTTPException(status_code=409, detail="Requester cannot approve their own request")

    approval.status = payload.decision
    approval.decided_by = user.id
    if (
        payload.decision == "approved"
        and approval.request_type == "fee.receipt_cancel"
        and approval.entity_type == "Payment"
        and approval.entity_id
    ):
        try:
            payment_id = UUID(approval.entity_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Invalid payment reference in approval"
            ) from exc
        payment = await db.get(Payment, payment_id)
        if not payment or payment.school_id != approval.school_id or payment.status != "posted":
            raise HTTPException(status_code=409, detail="Payment cannot be cancelled")
        payment.status = "cancelled"
        payment.cancelled_at = datetime.now(UTC)
        payment.cancellation_reason = approval.reason or payload.comment
    approval.decided_at = datetime.now(UTC)
    approval.decision_comment = payload.comment
    await db.flush()
    await record_audit(
        db,
        action=f"approval.{payload.decision}",
        user=user,
        module="workflow",
        entity_type="ApprovalRequest",
        entity_id=approval.id,
        after={"status": approval.status, "comment": payload.comment},
        request=request,
    )
    return approval
