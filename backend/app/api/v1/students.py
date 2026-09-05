import re
import secrets
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_license_valid,
    ensure_school_access,
    get_current_user,
    get_role_codes,
    require_permissions,
)
from app.db.session import get_db
from app.models.academic import (
    AcademicClass,
    Guardian,
    Section,
    Student,
    StudentEnrollment,
    StudentGuardian,
    Subject,
)
from app.models.organization import AcademicYear, Campus
from app.models.user import User
from app.schemas.student import (
    AcademicClassCreate,
    AcademicClassOut,
    AcademicClassUpdate,
    EnrollmentCreate,
    EnrollmentOut,
    GuardianCreate,
    GuardianOut,
    SectionCreate,
    SectionOut,
    SectionUpdate,
    StudentCreate,
    StudentOut,
    StudentUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/students", tags=["Students & Academics"])


def generate_student_code(prefix: str = "STU") -> str:
    return f"{prefix}-{secrets.token_hex(5).upper()}"


CASTE_CATEGORIES = {"OC", "SC", "ST", "BC-A", "BC-B", "BC-C", "BC-D", "BC-E", "BC-F"}
GENDER_VALUES = {
    "male": "Male",
    "female": "Female",
    "transgender": "Transgender",
    "other": "Other",
    "prefer not to say": "Prefer not to say",
}


def _normalized_phone(
    value: str | None, *, required: bool = False, field: str = "Phone"
) -> str | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise HTTPException(status_code=422, detail=f"{field} is required")
        return None
    compact = re.sub(r"[\s()-]", "", text)
    digits = compact[1:] if compact.startswith("+") else compact
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise HTTPException(status_code=422, detail=f"{field} must contain 7 to 15 digits")
    return compact


def _normalized_aadhaar(value: str | None) -> str | None:
    text = re.sub(r"\s", "", (value or "").strip())
    if not text:
        return None
    if not text.isdigit() or len(text) != 12:
        raise HTTPException(status_code=422, detail="Aadhaar Number must contain exactly 12 digits")
    return text


def _standard_class_sort_order(code: str, name: str) -> int | None:
    text = f"{code} {name}".strip().lower()
    if "nursery" in text or re.search(r"\bnur\b", text):
        return 10
    if "lkg" in text or "lower kg" in text or "lower kindergarten" in text:
        return 20
    if "ukg" in text or "upper kg" in text or "upper kindergarten" in text:
        return 30
    match = re.search(r"(?:class|grade|std|standard)?\s*([1-9]|1[0-2])\b", text)
    if match:
        return 30 + int(match.group(1)) * 10
    return None


@router.post("/campuses/{campus_id}/classes", response_model=AcademicClassOut, status_code=201)
async def create_class(
    campus_id: UUID,
    payload: AcademicClassCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_class.manage"))],
):
    await ensure_campus_access(user, db, campus_id)
    exists = await db.execute(
        select(AcademicClass).where(
            AcademicClass.campus_id == campus_id, AcademicClass.code == payload.code
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Class code already exists")
    max_order_result = await db.execute(
        select(func.coalesce(func.max(AcademicClass.sort_order), 0)).where(
            AcademicClass.campus_id == campus_id
        )
    )
    next_order = int(max_order_result.scalar_one() or 0) + 10
    suggested_order = _standard_class_sort_order(payload.code, payload.name)
    item = AcademicClass(
        campus_id=campus_id,
        code=payload.code.strip(),
        name=payload.name.strip(),
        sort_order=payload.sort_order
        if payload.sort_order is not None
        else (suggested_order if suggested_order is not None else next_order),
    )
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        action="academic.class.created",
        user=user,
        module="school_admin",
        entity_type="AcademicClass",
        entity_id=item.id,
        after={"campus_id": str(campus_id), "code": item.code, "name": item.name},
        request=request,
    )
    return item


@router.patch("/classes/{class_id}", response_model=AcademicClassOut)
async def update_class(
    class_id: UUID,
    payload: AcademicClassUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_class.manage"))],
):
    item = await db.get(AcademicClass, class_id)
    if not item:
        raise HTTPException(status_code=404, detail="Class not found")
    await ensure_campus_access(user, db, item.campus_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return item
    before = {"code": item.code, "name": item.name}
    if "code" in changes:
        code = changes["code"].strip()
        duplicate = await db.execute(
            select(AcademicClass.id).where(
                AcademicClass.campus_id == item.campus_id,
                AcademicClass.code == code,
                AcademicClass.id != item.id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Class code already exists")
        item.code = code
    if "name" in changes:
        item.name = changes["name"].strip()
    await db.flush()
    await record_audit(
        db,
        action="academic.class.updated",
        user=user,
        module="school_admin",
        entity_type="AcademicClass",
        entity_id=item.id,
        before=before,
        after={"code": item.code, "name": item.name},
        request=request,
    )
    return item


@router.get("/campuses/{campus_id}/classes", response_model=list[AcademicClassOut])
async def list_classes(
    campus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await ensure_campus_access(user, db, campus_id)
    result = await db.execute(
        select(AcademicClass)
        .where(AcademicClass.campus_id == campus_id, AcademicClass.is_active.is_(True))
        .order_by(AcademicClass.sort_order, AcademicClass.name)
    )
    return list(result.scalars().all())


@router.post("/classes/{class_id}/sections", response_model=SectionOut, status_code=201)
async def create_section(
    class_id: UUID,
    payload: SectionCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_class.manage"))],
):
    item_class = await db.get(AcademicClass, class_id)
    if not item_class:
        raise HTTPException(status_code=404, detail="Class not found")
    await ensure_campus_access(user, db, item_class.campus_id)
    exists = await db.execute(
        select(Section).where(Section.academic_class_id == class_id, Section.code == payload.code)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Section code already exists")
    item = Section(academic_class_id=class_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        action="academic.section.created",
        user=user,
        module="school_admin",
        entity_type="Section",
        entity_id=item.id,
        after={"class_id": str(class_id), "code": item.code, "name": item.name},
        request=request,
    )
    return item


@router.patch("/sections/{section_id}", response_model=SectionOut)
async def update_section(
    section_id: UUID,
    payload: SectionUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_class.manage"))],
):
    item = await db.get(Section, section_id)
    if not item:
        raise HTTPException(status_code=404, detail="Section not found")
    item_class = await db.get(AcademicClass, item.academic_class_id)
    if not item_class:
        raise HTTPException(status_code=404, detail="Class not found")
    await ensure_campus_access(user, db, item_class.campus_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return item
    before = {"code": item.code, "name": item.name}
    if "code" in changes:
        code = changes["code"].strip()
        duplicate = await db.execute(
            select(Section.id).where(
                Section.academic_class_id == item.academic_class_id,
                Section.code == code,
                Section.id != item.id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Section code already exists")
        item.code = code
    if "name" in changes:
        item.name = changes["name"].strip()
    await db.flush()
    await record_audit(
        db,
        action="academic.section.updated",
        user=user,
        module="school_admin",
        entity_type="Section",
        entity_id=item.id,
        before=before,
        after={"code": item.code, "name": item.name},
        request=request,
    )
    return item


@router.get("/classes/{class_id}/sections", response_model=list[SectionOut])
async def list_sections(
    class_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    item_class = await db.get(AcademicClass, class_id)
    if not item_class:
        raise HTTPException(status_code=404, detail="Class not found")
    await ensure_campus_access(user, db, item_class.campus_id)
    result = await db.execute(
        select(Section)
        .where(Section.academic_class_id == class_id, Section.is_active.is_(True))
        .order_by(Section.name)
    )
    return list(result.scalars().all())


@router.post("/campuses/{campus_id}/subjects", response_model=SubjectOut, status_code=201)
async def create_subject(
    campus_id: UUID,
    payload: SubjectCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("subject.manage"))],
):
    campus = await ensure_campus_access(user, db, campus_id)
    code = payload.code.strip()
    name = payload.name.strip()
    exists = await db.execute(
        select(Subject).where(
            Subject.campus_id == campus_id,
            func.lower(Subject.code) == code.lower(),
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Subject code already exists")
    item = Subject(campus_id=campus_id, code=code, name=name)
    db.add(item)
    await db.flush()
    await record_audit(
        db,
        action="academic.subject.created",
        user=user,
        module="school_admin",
        entity_type="Subject",
        entity_id=item.id,
        after={"campus_id": str(campus_id), "code": item.code, "name": item.name},
        request=request,
        target_school_id=campus.school_id,
        target_campus_id=campus_id,
    )
    return item


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("subject.manage"))],
):
    item = await db.get(Subject, subject_id)
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")
    campus = await ensure_campus_access(user, db, item.campus_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return item
    before = {"code": item.code, "name": item.name, "is_active": item.is_active}
    if "code" in changes:
        code = changes["code"].strip()
        duplicate = await db.execute(
            select(Subject.id).where(
                Subject.campus_id == item.campus_id,
                func.lower(Subject.code) == code.lower(),
                Subject.id != item.id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Subject code already exists")
        item.code = code
    if "name" in changes:
        item.name = changes["name"].strip()
    await db.flush()
    await record_audit(
        db,
        action="academic.subject.updated",
        user=user,
        module="school_admin",
        entity_type="Subject",
        entity_id=item.id,
        before=before,
        after={"code": item.code, "name": item.name, "is_active": item.is_active},
        request=request,
        target_school_id=campus.school_id,
        target_campus_id=item.campus_id,
    )
    return item


@router.get("/campuses/{campus_id}/subjects", response_model=list[SubjectOut])
async def list_subjects(
    campus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await ensure_campus_access(user, db, campus_id)
    result = await db.execute(
        select(Subject)
        .where(Subject.campus_id == campus_id, Subject.is_active.is_(True))
        .order_by(Subject.name)
    )
    return list(result.scalars().all())


@router.post("/{school_id}/guardians", response_model=GuardianOut, status_code=201)
async def create_guardian(
    school_id: UUID,
    payload: GuardianCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.create"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    guardian = Guardian(school_id=school_id, **payload.model_dump())
    db.add(guardian)
    await db.flush()
    return guardian


@router.post("/{school_id}", response_model=StudentOut, status_code=201)
async def create_student(
    school_id: UUID,
    payload: StudentCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.create"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    campus_id = payload.campus_id or user.campus_id
    if campus_id:
        campus = await ensure_campus_access(user, db, campus_id)
        if campus.school_id != school_id:
            raise HTTPException(status_code=422, detail="Campus does not belong to this school")
    else:
        result = await db.execute(
            select(Campus)
            .where(Campus.school_id == school_id, Campus.is_active.is_(True))
            .order_by(Campus.created_at)
        )
        campus = result.scalars().first()
        if not campus:
            raise HTTPException(status_code=422, detail="School has no active campus")
        campus_id = campus.id
    exists = await db.execute(
        select(Student).where(
            Student.school_id == school_id,
            func.lower(Student.admission_number) == payload.admission_number.strip().lower(),
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Admission number already exists")

    prefix = "STU"
    config_result = await db.execute(select(Campus).where(Campus.id == campus_id))
    if not config_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Campus not found")

    father_number = _normalized_phone(
        payload.father_number,
        required=bool(payload.academic_year_id),
        field="Father's Mobile Number",
    )
    mother_number = _normalized_phone(payload.mother_number, field="Mother's Mobile Number")
    emergency_phone = _normalized_phone(
        payload.emergency_contact_phone, field="Emergency Contact Number"
    )
    aadhaar = _normalized_aadhaar(payload.government_id)
    category = payload.category.strip().upper() if payload.category else None
    gender = (
        GENDER_VALUES.get((payload.gender or "").strip().casefold()) if payload.gender else None
    )
    if payload.academic_year_id and category not in CASTE_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail="Caste Category must be one of OC, SC, ST, BC-A, BC-B, BC-C, BC-D, BC-E or BC-F",
        )
    if payload.academic_year_id and not gender:
        raise HTTPException(
            status_code=422,
            detail="Gender must be Male, Female, Transgender, Other or Prefer not to say",
        )

    custom_fields = dict(payload.custom_fields or {})
    if payload.sub_caste:
        custom_fields["sub_caste"] = payload.sub_caste.strip()
    if payload.email_id:
        custom_fields["email_id"] = payload.email_id.strip()

    student_payload = payload.model_dump(
        exclude={
            "campus_id",
            "guardian_ids",
            "academic_year_id",
            "academic_class_id",
            "section_id",
            "roll_number",
            "father_name",
            "mother_name",
            "father_number",
            "mother_number",
            "email_id",
            "sub_caste",
        }
    )
    student_payload["government_id"] = aadhaar
    student_payload["category"] = category
    student_payload["gender"] = gender if payload.academic_year_id else payload.gender
    student_payload["emergency_contact_phone"] = emergency_phone
    student_payload["custom_fields"] = custom_fields
    student = Student(
        school_id=school_id,
        campus_id=campus_id,
        student_code=generate_student_code(prefix),
        **student_payload,
    )
    db.add(student)
    await db.flush()

    if payload.academic_year_id:
        year = await db.get(AcademicYear, payload.academic_year_id)
        academic_class = await db.get(AcademicClass, payload.academic_class_id)
        section = await db.get(Section, payload.section_id)
        if not year or not academic_class or not section:
            raise HTTPException(status_code=422, detail="Academic year, class or section not found")
        if (
            year.campus_id != campus_id
            or academic_class.campus_id != campus_id
            or section.academic_class_id != academic_class.id
        ):
            raise HTTPException(
                status_code=422,
                detail="Academic year, class and section must belong to the student's campus",
            )
        if year.is_read_only or year.status == "closed":
            raise HTTPException(status_code=409, detail="Historical academic year is read-only")
        db.add(
            StudentEnrollment(
                student_id=student.id,
                academic_year_id=year.id,
                academic_class_id=academic_class.id,
                section_id=section.id,
                roll_number=payload.roll_number,
                enrolled_on=payload.admission_date or date.today(),
            )
        )

    # New enrolment captures Father and Mother explicitly. Store them as canonical
    # Guardian records so ERP access can use the registered parent mobile numbers.
    if payload.father_name:
        father = Guardian(
            school_id=school_id,
            name=payload.father_name.strip(),
            relationship_type="Father",
            mobile=father_number,
            email=payload.email_id.strip() if payload.email_id else None,
            address=payload.address_line1,
            is_primary=True,
        )
        db.add(father)
        await db.flush()
        db.add(StudentGuardian(student_id=student.id, guardian_id=father.id))
    if payload.mother_name:
        mother = Guardian(
            school_id=school_id,
            name=payload.mother_name.strip(),
            relationship_type="Mother",
            mobile=mother_number,
            address=payload.address_line1,
            is_primary=not bool(payload.father_name),
        )
        db.add(mother)
        await db.flush()
        db.add(StudentGuardian(student_id=student.id, guardian_id=mother.id))

    if payload.guardian_ids:
        guardians = await db.execute(
            select(Guardian).where(
                Guardian.id.in_(payload.guardian_ids), Guardian.school_id == school_id
            )
        )
        guardian_rows = list(guardians.scalars().all())
        if len(guardian_rows) != len(set(payload.guardian_ids)):
            raise HTTPException(
                status_code=422, detail="One or more guardians do not belong to this school"
            )
        for guardian in guardian_rows:
            db.add(StudentGuardian(student_id=student.id, guardian_id=guardian.id))
    await record_audit(
        db,
        action="student.created",
        user=user,
        module="student",
        entity_type="Student",
        entity_id=student.id,
        after={
            "student_code": student.student_code,
            "admission_number": student.admission_number,
            "academic_year_id": str(payload.academic_year_id) if payload.academic_year_id else None,
            "academic_class_id": str(payload.academic_class_id)
            if payload.academic_class_id
            else None,
            "section_id": str(payload.section_id) if payload.section_id else None,
        },
        request=request,
        target_school_id=school_id,
        target_campus_id=campus_id,
    )
    return student


@router.get("/{school_id}", response_model=list[StudentOut])
async def list_students(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.view"))],
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    query = select(Student).where(Student.school_id == school_id)
    if (
        user.campus_id
        and "ORGANIZATION_ADMIN" not in get_role_codes(user)
        and not user.is_superuser
    ):
        query = query.where(Student.campus_id == user.campus_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            (Student.first_name.ilike(term))
            | (Student.last_name.ilike(term))
            | (Student.admission_number.ilike(term))
            | (Student.student_code.ilike(term))
        )
    query = query.order_by(Student.created_at.desc()).offset(offset).limit(min(limit, 500))
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/{student_id}/enrollments", response_model=EnrollmentOut, status_code=201)
async def enroll_student(
    student_id: UUID,
    payload: EnrollmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.edit"))],
):
    student = await db.get(Student, student_id)
    year = await db.get(AcademicYear, payload.academic_year_id)
    academic_class = await db.get(AcademicClass, payload.academic_class_id)
    section = await db.get(Section, payload.section_id)
    if not student or not year or not academic_class or not section:
        raise HTTPException(status_code=404, detail="Student or academic records not found")
    await ensure_campus_access(user, db, student.campus_id)
    await ensure_license_valid(student.school_id, db, "student")
    if year.is_read_only or year.status == "closed":
        raise HTTPException(status_code=409, detail="Historical academic year is read-only")
    if (
        academic_class.campus_id != student.campus_id
        or section.academic_class_id != academic_class.id
        or year.campus_id != student.campus_id
    ):
        raise HTTPException(
            status_code=422, detail="Enrollment records belong to different campus/class"
        )
    existing = await db.execute(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_year_id == payload.academic_year_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Student already has an enrollment for this academic year"
        )
    enrollment = StudentEnrollment(student_id=student_id, **payload.model_dump())
    db.add(enrollment)
    await db.flush()
    return enrollment


@router.get("/{school_id}/{student_id}", response_model=StudentOut)
async def get_student(
    school_id: UUID,
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.view"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    return student


@router.patch("/{school_id}/{student_id}", response_model=StudentOut)
async def update_student(
    school_id: UUID,
    student_id: UUID,
    payload: StudentUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.edit"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    changes = payload.model_dump(exclude_unset=True)
    if "admission_number" in changes and changes["admission_number"] != student.admission_number:
        duplicate = await db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.admission_number == changes["admission_number"],
                Student.id != student.id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Admission number already exists")
    before = {field: getattr(student, field) for field in changes}
    for field, value in changes.items():
        setattr(student, field, value)
    await db.flush()
    await record_audit(
        db,
        action="student.updated",
        user=user,
        module="student",
        entity_type="Student",
        entity_id=student.id,
        before=before,
        after=changes,
        request=request,
        target_school_id=student.school_id,
        target_campus_id=student.campus_id,
    )
    return student


@router.delete("/{school_id}/{student_id}", response_model=StudentOut)
async def archive_student(
    school_id: UUID,
    student_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.edit"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    before = {"status": student.status}
    student.status = "inactive"
    await db.flush()
    await record_audit(
        db,
        action="student.archived",
        user=user,
        module="student",
        entity_type="Student",
        entity_id=student.id,
        before=before,
        after={"status": student.status},
        request=request,
        target_school_id=student.school_id,
        target_campus_id=student.campus_id,
    )
    return student


@router.post("/{school_id}/{student_id}/reactivate", response_model=StudentOut)
async def reactivate_student(
    school_id: UUID,
    student_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("student.edit"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    student = await db.get(Student, student_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_campus_access(user, db, student.campus_id)
    before = {"status": student.status}
    student.status = "active"
    await db.flush()
    await record_audit(
        db,
        action="student.reactivated",
        user=user,
        module="student",
        entity_type="Student",
        entity_id=student.id,
        before=before,
        after={"status": student.status},
        request=request,
        target_school_id=student.school_id,
        target_campus_id=student.campus_id,
    )
    return student
