from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_school_access, require_permissions
from app.core.security import get_password_hash
from app.core.usernames import normalize_username
from app.db.session import get_db
from app.models.academic import Guardian, Student, StudentGuardian
from app.models.erp_access import ERPAccessPolicy, ParentStudentLink, StudentERPAccess
from app.models.fee import FeeHead, StudentCharge
from app.models.organization import AcademicYear, OrganizationAcademicYear
from app.models.school import School
from app.models.user import Role, User, UserRole
from app.schemas.erp_access import (
    AccessContactOut,
    ERPAccessOptIn,
    ERPAccessOut,
    ERPAccessPolicyOut,
    ERPAccessPolicyUpsert,
)
from app.services.audit import record_audit
from app.services.password_policy import validate_password

router = APIRouter(prefix="/erp-access", tags=["Parent / Student ERP Access"])


def _normalize_phone(value: str) -> str:
    value = value.strip()
    # Preserve an optional leading +, remove formatting characters only.
    if value.startswith("+"):
        return "+" + "".join(ch for ch in value[1:] if ch.isdigit())
    return "".join(ch for ch in value if ch.isdigit())


async def _registered_contacts(db: AsyncSession, student: Student) -> list[AccessContactOut]:
    contacts: list[AccessContactOut] = []
    seen: set[str] = set()

    if student.emergency_contact_phone:
        phone = _normalize_phone(student.emergency_contact_phone)
        if phone:
            seen.add(phone)
            contacts.append(
                AccessContactOut(
                    mobile=phone, label=student.emergency_contact_name or "Emergency contact"
                )
            )

    rows = await db.execute(
        select(Guardian)
        .join(StudentGuardian, StudentGuardian.guardian_id == Guardian.id)
        .where(StudentGuardian.student_id == student.id, Guardian.mobile.is_not(None))
        .order_by(Guardian.is_primary.desc(), Guardian.name)
    )
    for guardian in rows.scalars().all():
        if not guardian.mobile:
            continue
        phone = _normalize_phone(guardian.mobile)
        if not phone or phone in seen:
            continue
        seen.add(phone)
        label = f"{guardian.relationship_type}: {guardian.name}"
        contacts.append(AccessContactOut(mobile=phone, label=label))
    return contacts


async def _parent_student_role(db: AsyncSession) -> Role:
    result = await db.execute(
        select(Role).where(Role.code == "PARENT_STUDENT", Role.school_id.is_(None))
    )
    role = result.scalars().first()
    if not role:
        raise HTTPException(status_code=500, detail="Parent / Student role is not initialized")
    return role


async def _get_or_create_access_user(
    db: AsyncSession,
    *,
    school: School,
    access_number: str,
    initial_password: str | None,
) -> tuple[User, bool]:
    result = await db.execute(
        select(User).where(
            User.organization_id == school.organization_id,
            User.account_type == "PARENT_STUDENT",
            User.phone == access_number,
        )
    )
    users = list(result.scalars().all())
    if len(users) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple Parent / Student access accounts exist for this number. Contact Super Admin.",
        )
    if users:
        user = users[0]
        if not user.is_active:
            user.is_active = True
        return user, False

    if not initial_password:
        raise HTTPException(
            status_code=422,
            detail="Initial school-issued password is required the first time this access number is activated.",
        )
    validate_password(initial_password)
    digits = "".join(ch for ch in access_number if ch.isdigit())[-8:] or "ACCESS"
    org_fragment = str(school.organization_id).replace("-", "")[:8]
    base = f"PS-{org_fragment}-{digits}"
    username = normalize_username(base)
    seq = 1
    while (
        await db.execute(select(User.id).where(func.lower(User.username) == username))
    ).scalar_one_or_none():
        seq += 1
        username = f"{base}-{seq}"

    user = User(
        organization_id=school.organization_id,
        school_id=None,
        campus_id=None,
        account_type="PARENT_STUDENT",
        username=username,
        email=None,
        phone=access_number,
        full_name="Parent / Student Access",
        hashed_password=get_password_hash(initial_password),
        is_active=True,
        is_superuser=False,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    role = await _parent_student_role(db)
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()
    return user, True


@router.get(
    "/schools/{school_id}/students/{student_id}/contacts", response_model=list[AccessContactOut]
)
async def list_access_contacts(
    school_id: UUID,
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("erp_access.opt"))],
):
    await ensure_school_access(actor, db, school_id)
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    return await _registered_contacts(db, student)


@router.get("/schools/{school_id}/policy", response_model=ERPAccessPolicyOut | None)
async def get_policy(
    school_id: UUID,
    organization_academic_year_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.view"))],
):
    await ensure_school_access(actor, db, school_id)
    result = await db.execute(
        select(ERPAccessPolicy).where(
            ERPAccessPolicy.school_id == school_id,
            ERPAccessPolicy.organization_academic_year_id == organization_academic_year_id,
        )
    )
    return result.scalar_one_or_none()


@router.put("/schools/{school_id}/policy", response_model=ERPAccessPolicyOut)
async def upsert_policy(
    school_id: UUID,
    payload: ERPAccessPolicyUpsert,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("erp_access.manage"))],
):
    await ensure_school_access(actor, db, school_id)
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    year = await db.get(OrganizationAcademicYear, payload.organization_academic_year_id)
    if not year or year.organization_id != school.organization_id:
        raise HTTPException(status_code=404, detail="Organization Academic Year not found")
    head = await db.get(FeeHead, payload.fee_head_id)
    if not head or head.school_id != school_id or not head.is_active:
        raise HTTPException(status_code=404, detail="Active Fee Head not found for this School")

    result = await db.execute(
        select(ERPAccessPolicy).where(
            ERPAccessPolicy.school_id == school_id,
            ERPAccessPolicy.organization_academic_year_id == year.id,
        )
    )
    policy = result.scalar_one_or_none()
    before = None
    if policy:
        before = {
            "fee_head_id": str(policy.fee_head_id),
            "annual_amount": str(policy.annual_amount),
            "is_enabled": policy.is_enabled,
        }
        policy.fee_head_id = payload.fee_head_id
        policy.annual_amount = payload.annual_amount
        policy.is_enabled = payload.is_enabled
    else:
        policy = ERPAccessPolicy(
            school_id=school_id,
            organization_academic_year_id=year.id,
            fee_head_id=payload.fee_head_id,
            annual_amount=payload.annual_amount,
            is_enabled=payload.is_enabled,
        )
        db.add(policy)
    await db.flush()
    await record_audit(
        db,
        action="erp_access.policy_updated" if before else "erp_access.policy_created",
        user=actor,
        module="fee",
        entity_type="ERPAccessPolicy",
        entity_id=policy.id,
        before=before,
        after={
            "school_id": str(school_id),
            "organization_academic_year_id": str(year.id),
            "fee_head_id": str(policy.fee_head_id),
            "annual_amount": str(policy.annual_amount),
            "is_enabled": policy.is_enabled,
        },
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school_id,
    )
    return policy


@router.post(
    "/schools/{school_id}/opt-in", response_model=ERPAccessOut, status_code=status.HTTP_201_CREATED
)
async def opt_student_in(
    school_id: UUID,
    payload: ERPAccessOptIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("erp_access.opt"))],
):
    await ensure_school_access(actor, db, school_id)
    student = await db.get(Student, payload.student_id)
    if not student or student.school_id != school_id or student.status != "active":
        raise HTTPException(status_code=404, detail="Active Student not found")
    school = await db.get(School, school_id)
    if not school or not school.organization_id:
        raise HTTPException(status_code=409, detail="School Organization is not configured")

    year_result = await db.execute(
        select(OrganizationAcademicYear)
        .where(
            OrganizationAcademicYear.organization_id == school.organization_id,
            OrganizationAcademicYear.status == "active",
        )
        .order_by(OrganizationAcademicYear.starts_on.desc())
    )
    org_year = year_result.scalars().first()
    if not org_year:
        raise HTTPException(
            status_code=409,
            detail="Activate the Organization Academic Year before opting ERP access",
        )

    policy_result = await db.execute(
        select(ERPAccessPolicy).where(
            ERPAccessPolicy.school_id == school_id,
            ERPAccessPolicy.organization_academic_year_id == org_year.id,
            ERPAccessPolicy.is_enabled.is_(True),
        )
    )
    policy = policy_result.scalar_one_or_none()
    if not policy:
        raise HTTPException(
            status_code=409,
            detail="Configure the annual ERP Access Fee Head and amount before opting students",
        )

    access_number = _normalize_phone(payload.access_number)
    contacts = await _registered_contacts(db, student)
    if access_number not in {item.mobile for item in contacts}:
        raise HTTPException(
            status_code=422,
            detail="Access Number must be selected from the Student's registered contact numbers",
        )

    existing_access_result = await db.execute(
        select(StudentERPAccess).where(
            StudentERPAccess.student_id == student.id,
            StudentERPAccess.organization_academic_year_id == org_year.id,
        )
    )
    existing_access = existing_access_result.scalar_one_or_none()
    if existing_access:
        if existing_access.status == "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail="ERP access is already active for this Student in the current Academic Year",
            )
        existing_access.status = "ACTIVE"
        existing_access.access_number = access_number
        existing_access.suspended_at = None
        existing_access.opted_by = actor.id
        existing_access.opted_at = datetime.now(UTC)
        existing_access.notes = payload.notes
        access = existing_access
    else:
        access = StudentERPAccess(
            school_id=school_id,
            student_id=student.id,
            organization_academic_year_id=org_year.id,
            access_number=access_number,
            status="ACTIVE",
            opted_by=actor.id,
            notes=payload.notes,
        )
        db.add(access)
        await db.flush()

    access_user, login_account_created = await _get_or_create_access_user(
        db,
        school=school,
        access_number=access_number,
        initial_password=payload.initial_password,
    )
    link_result = await db.execute(
        select(ParentStudentLink).where(
            ParentStudentLink.user_id == access_user.id,
            ParentStudentLink.student_id == student.id,
        )
    )
    if not link_result.scalar_one_or_none():
        db.add(ParentStudentLink(user_id=access_user.id, student_id=student.id))

    academic_year_result = await db.execute(
        select(AcademicYear).where(
            AcademicYear.campus_id == student.campus_id,
            AcademicYear.organization_academic_year_id == org_year.id,
        )
    )
    academic_year = academic_year_result.scalar_one_or_none()
    if not academic_year:
        raise HTTPException(
            status_code=409,
            detail="School Academic Year projection is missing; contact Super Admin",
        )

    charge_result = await db.execute(
        select(StudentCharge).where(
            StudentCharge.student_id == student.id,
            StudentCharge.academic_year_id == academic_year.id,
            StudentCharge.source_type == "ERP_ACCESS",
        )
    )
    charge = charge_result.scalar_one_or_none()
    if not charge:
        charge = StudentCharge(
            school_id=school_id,
            student_id=student.id,
            academic_year_id=academic_year.id,
            fee_head_id=policy.fee_head_id,
            description=f"Annual Parent / Student ERP Access - {org_year.name}",
            amount=Decimal(str(policy.annual_amount)),
            status="open",
            source_type="ERP_ACCESS",
            source_ref=str(access.id),
        )
        db.add(charge)
        await db.flush()

    await db.flush()
    await record_audit(
        db,
        action="erp_access.student_opted",
        user=actor,
        module="student",
        entity_type="StudentERPAccess",
        entity_id=access.id,
        after={
            "student_id": str(student.id),
            "access_number": access_number,
            "organization_academic_year_id": str(org_year.id),
            "charge_id": str(charge.id),
            "fee_amount": str(policy.annual_amount),
            "login_account_created": login_account_created,
        },
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school_id,
    )

    # Pydantic response can consume model attributes plus these computed fields.
    return ERPAccessOut(
        id=access.id,
        school_id=access.school_id,
        student_id=access.student_id,
        organization_academic_year_id=access.organization_academic_year_id,
        access_number=access.access_number,
        status=access.status,
        opted_by=access.opted_by,
        opted_at=access.opted_at,
        suspended_at=access.suspended_at,
        notes=access.notes,
        login_account_created=login_account_created,
        charge_id=charge.id,
    )
