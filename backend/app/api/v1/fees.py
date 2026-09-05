from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_license_valid,
    ensure_school_access,
    get_role_codes,
    require_permissions,
)
from app.db.session import get_db
from app.models.academic import Student
from app.models.approval import ApprovalRequest
from app.models.fee import (
    FeeHead,
    FeeStructureItem,
    Payment,
    PaymentAllocation,
    ReceiptSequence,
    StudentCharge,
)
from app.models.school import SchoolConfiguration
from app.models.user import User
from app.schemas.fee import (
    CancellationRequest,
    ChargeCreate,
    ChargeOut,
    FeeHeadCreate,
    FeeHeadOut,
    FeeStructureCreate,
    FeeStructureOut,
    PaymentCreate,
    PaymentOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/fees", tags=["Fee Collection"])


async def next_receipt_number(
    db: AsyncSession, school_id: UUID, campus_id: UUID, config: SchoolConfiguration | None
) -> str:
    settings = (config.settings or {}).get("fees", {}) if config else {}
    prefix = str(settings.get("receipt_prefix", "RCPT")).strip() or "RCPT"
    period_key = datetime.now(UTC).strftime("%Y")
    result = await db.execute(
        select(ReceiptSequence)
        .where(
            ReceiptSequence.school_id == school_id,
            ReceiptSequence.campus_id == campus_id,
            ReceiptSequence.period_key == period_key,
        )
        .with_for_update()
    )
    sequence = result.scalar_one_or_none()
    if not sequence:
        sequence = ReceiptSequence(
            school_id=school_id, campus_id=campus_id, period_key=period_key, next_number=1
        )
        db.add(sequence)
        await db.flush()
    number = sequence.next_number
    sequence.next_number += 1
    await db.flush()
    return f"{prefix}-{period_key}-{number:06d}"


async def _school_check(user: User, db: AsyncSession, school_id: UUID) -> None:
    await ensure_school_access(user, db, school_id)


@router.get("/{school_id}/account-students")
async def list_fee_account_students(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.view"))],
):
    """Minimal Student identity list for fee-account browsing.

    Receptionist has read-only Accounts access without broad Student Management
    permission, so the fee module exposes only the identifiers needed to locate
    a ledger.
    """
    await _school_check(user, db, school_id)
    rows = await db.execute(
        select(
            Student.id,
            Student.student_code,
            Student.admission_number,
            Student.first_name,
            Student.last_name,
            Student.status,
        )
        .where(Student.school_id == school_id)
        .order_by(Student.first_name, Student.last_name)
    )
    return [
        {
            "id": str(row.id),
            "student_code": row.student_code,
            "admission_number": row.admission_number,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "status": row.status,
        }
        for row in rows
    ]


@router.get("/{school_id}/heads", response_model=list[FeeHeadOut])
async def list_fee_heads(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.view"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    result = await db.execute(
        select(FeeHead)
        .where(FeeHead.school_id == school_id, FeeHead.is_active.is_(True))
        .order_by(FeeHead.name)
    )
    return list(result.scalars().all())


@router.get("/{school_id}/structures", response_model=list[FeeStructureOut])
async def list_fee_structures(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.view"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    query = select(FeeStructureItem).where(
        FeeStructureItem.school_id == school_id, FeeStructureItem.is_active.is_(True)
    )
    if (
        user.campus_id
        and "ORGANIZATION_ADMIN" not in get_role_codes(user)
        and not user.is_superuser
    ):
        query = query.where(FeeStructureItem.campus_id == user.campus_id)
    result = await db.execute(query.order_by(FeeStructureItem.created_at.desc()))
    return list(result.scalars().all())


@router.post("/{school_id}/heads", response_model=FeeHeadOut, status_code=201)
async def create_fee_head(
    school_id: UUID,
    payload: FeeHeadCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.head.manage"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    exists = await db.execute(
        select(FeeHead).where(FeeHead.school_id == school_id, FeeHead.code == payload.code)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Fee head already exists")
    item = FeeHead(school_id=school_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        action="fee.head.created",
        user=user,
        module="fee",
        entity_type="FeeHead",
        entity_id=item.id,
        after={
            "code": item.code,
            "name": item.name,
            "is_misc": item.is_misc,
            "is_active": item.is_active,
        },
        request=request,
        target_school_id=school_id,
    )
    return item


@router.post("/{school_id}/structures", response_model=FeeStructureOut, status_code=201)
async def create_fee_structure(
    school_id: UUID,
    payload: FeeStructureCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.structure.manage"))],
):
    await _school_check(user, db, school_id)
    await ensure_campus_access(user, db, payload.campus_id)
    await ensure_license_valid(school_id, db, "fee")
    head = await db.get(FeeHead, payload.fee_head_id)
    if not head or head.school_id != school_id:
        raise HTTPException(status_code=404, detail="Fee head not found")
    item = FeeStructureItem(school_id=school_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        action="fee.structure.created",
        user=user,
        module="fee",
        entity_type="FeeStructureItem",
        entity_id=item.id,
        after={
            "campus_id": str(item.campus_id),
            "academic_year_id": str(item.academic_year_id),
            "academic_class_id": str(item.academic_class_id) if item.academic_class_id else None,
            "section_id": str(item.section_id) if item.section_id else None,
            "fee_head_id": str(item.fee_head_id),
            "frequency": item.frequency,
            "amount": str(item.amount),
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "is_active": item.is_active,
        },
        request=request,
        target_school_id=school_id,
        target_campus_id=item.campus_id,
    )
    return item


@router.post("/{school_id}/charges", response_model=ChargeOut, status_code=201)
async def create_charge(
    school_id: UUID,
    payload: ChargeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.collect"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    student = await db.get(Student, payload.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    item = StudentCharge(school_id=school_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    return item


@router.get("/{school_id}/students/{student_id}/charges", response_model=list[ChargeOut])
async def list_student_charges(
    school_id: UUID,
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.view"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    result = await db.execute(
        select(StudentCharge)
        .where(StudentCharge.school_id == school_id, StudentCharge.student_id == student_id)
        .order_by(StudentCharge.due_date, StudentCharge.created_at)
    )
    return list(result.scalars().all())


@router.post("/{school_id}/payments", response_model=PaymentOut, status_code=201)
async def collect_payment(
    school_id: UUID,
    payload: PaymentCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.collect"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    student = await db.get(Student, payload.student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    if (
        user.campus_id
        and "ORGANIZATION_ADMIN" not in get_role_codes(user)
        and not user.is_superuser
    ):
        await ensure_campus_access(user, db, student.campus_id)
    config_result = await db.execute(
        select(SchoolConfiguration).where(SchoolConfiguration.school_id == school_id)
    )
    config = config_result.scalar_one_or_none()
    fee_settings = (config.settings or {}).get("fees", {}) if config else {}
    allowed_modes = fee_settings.get("payment_methods", ["cash", "upi"])
    mode = payload.payment_mode.strip().lower()
    if mode not in [str(x).lower() for x in allowed_modes]:
        raise HTTPException(status_code=422, detail="Payment mode is not enabled for this school")
    if mode == "upi" and not payload.upi_reference_last5:
        raise HTTPException(
            status_code=422, detail="Last 5 UPI transaction characters are required"
        )
    if mode != "upi" and payload.upi_reference_last5:
        raise HTTPException(status_code=422, detail="UPI reference is only valid for UPI payments")
    charge_ids = [a.charge_id for a in payload.allocations]
    result = await db.execute(
        select(StudentCharge)
        .where(
            StudentCharge.id.in_(charge_ids),
            StudentCharge.school_id == school_id,
            StudentCharge.student_id == student.id,
        )
        .with_for_update()
    )
    charges = {c.id: c for c in result.scalars().all()}
    if len(charges) != len(set(charge_ids)):
        raise HTTPException(
            status_code=422, detail="One or more charges are invalid for this student"
        )
    max_parts = int(fee_settings.get("part_payment_max", 12))
    total = Decimal("0")
    for allocation in payload.allocations:
        charge = charges[allocation.charge_id]
        paid_result = await db.execute(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.charge_id == charge.id, Payment.status == "posted")
        )
        paid = Decimal(str(paid_result.scalar_one() or 0))
        outstanding = Decimal(str(charge.amount)) - paid
        if allocation.amount > outstanding:
            raise HTTPException(
                status_code=422,
                detail=f"Allocation exceeds outstanding amount for charge {charge.id}",
            )
        part_count_result = await db.execute(
            select(func.count(PaymentAllocation.payment_id.distinct()))
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.charge_id == charge.id, Payment.status == "posted")
        )
        if int(part_count_result.scalar_one() or 0) >= max_parts:
            raise HTTPException(
                status_code=422,
                detail=f"Configured part-payment limit ({max_parts}) reached for charge {charge.id}",
            )
        total += allocation.amount
    if total <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    receipt_no = await next_receipt_number(db, school_id, student.campus_id, config)
    payment = Payment(
        school_id=school_id,
        student_id=student.id,
        campus_id=student.campus_id,
        amount=total,
        payment_mode=mode,
        upi_reference_last5=payload.upi_reference_last5,
        receipt_number=receipt_no,
        collected_by=user.id,
    )
    db.add(payment)
    await db.flush()
    for allocation in payload.allocations:
        db.add(
            PaymentAllocation(
                payment_id=payment.id, charge_id=allocation.charge_id, amount=allocation.amount
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="fee.payment.posted",
        user=user,
        module="fee",
        entity_type="Payment",
        entity_id=payment.id,
        after={
            "amount": str(total),
            "receipt_number": payment.receipt_number,
            "payment_mode": mode,
        },
        request=request,
    )
    return payment


@router.post("/{school_id}/payments/{payment_id}/cancel", status_code=202)
async def request_payment_cancellation(
    school_id: UUID,
    payment_id: UUID,
    payload: CancellationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("fee.cancel.request"))],
):
    await _school_check(user, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    payment = await db.get(Payment, payment_id)
    if not payment or payment.school_id != school_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    await ensure_campus_access(user, db, payment.campus_id)
    if payment.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted payments can be cancelled")
    approval = ApprovalRequest(
        organization_id=user.organization_id,
        school_id=school_id,
        campus_id=payment.campus_id,
        requested_by=user.id,
        request_type="fee.receipt_cancel",
        entity_type="Payment",
        entity_id=str(payment.id),
        reason=payload.reason,
        payload={"receipt_number": payment.receipt_number, "amount": str(payment.amount)},
    )
    db.add(approval)
    await db.flush()
    await record_audit(
        db,
        action="fee.payment.cancellation_requested",
        user=user,
        module="fee",
        entity_type="Payment",
        entity_id=payment.id,
        after={"approval_id": str(approval.id), "reason": payload.reason},
        request=request,
    )
    return {
        "approval_id": approval.id,
        "status": approval.status,
        "receipt_number": payment.receipt_number,
    }
