from __future__ import annotations

import hmac
import re
import secrets
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_license_valid,
    ensure_school_access,
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
from app.models.fee import FeeHead, FeeStructureItem, StudentCharge
from app.models.marks import StudentMark
from app.models.organization import AcademicYear
from app.models.staff import Teacher
from app.models.user import User
from app.services.audit import record_audit
from app.services.imports.student_template import COLUMN_ALIASES, OPTIONAL_COLUMNS, REQUIRED_COLUMNS
from app.services.imports.xlsx_import import (
    MAX_PREVIEW_ROWS,
    clean_text,
    normalize_aadhaar,
    normalize_phone,
    parse_date,
    parse_decimal,
    parse_xlsx,
    read_upload,
    split_name,
)

router = APIRouter(prefix="/imports", tags=["Bulk Import"])
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "imports"

STUDENT_HEADERS = {
    "sis_number",
    "academic_year",
    "admission_number",
    "admission_date",
    "student_name",
    "date_of_birth",
    "gender",
    "class_name",
    "section_name",
    "father_name",
    "mother_name",
    "father_number",
    "mother_number",
    "email_id",
    "aadhaar_number",
    "caste_category",
    "sub_caste",
    "address",
    "emergency_contact_number",
    "student_status",
}
STUDENT_CASTE_CATEGORIES = {"OC", "SC", "ST", "BC-A", "BC-B", "BC-C", "BC-D", "BC-E", "BC-F"}
STUDENT_GENDERS = {
    "male": "Male",
    "female": "Female",
    "transgender": "Transgender",
    "other": "Other",
    "prefer not to say": "Prefer not to say",
}
TEACHER_HEADERS = {
    "employee_number",
    "teacher_name",
    "father_name",
    "mother_name",
    "father_number",
    "mother_number",
    "date_of_birth",
    "email",
    "qualification",
    "aadhaar_number",
    "staff_category",
    "caste_category",
    "sub_caste",
}
MARK_HEADERS = {"admission_number", "student_name", "marks_obtained", "remarks"}
FEE_STRUCTURE_HEADERS = {
    "academic_year",
    "class_name",
    "fee_head",
    "amount",
    "frequency",
    "due_month",
}
PRIOR_DUE_HEADERS = {
    "admission_number",
    "student_name",
    "prior_academic_year",
    "outstanding_amount",
    "reference",
}
CLASS_HEADERS = {"class_code", "class_name"}
SECTION_HEADERS = {"class_code", "section_code", "section_name"}
CLASS_SECTION_HEADERS = {"class_name", "name_of_section"}
CLASS_SECTION_SHEET = "Classes & Sections"


def _student_code() -> str:
    return f"STU-{secrets.token_hex(5).upper()}"


def _issue(row: int, message: str, field: str | None = None) -> dict[str, Any]:
    return {"row": row, "field": field, "message": message}


def _masked(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    return ("•" * max(0, len(text) - 4)) + text[-4:]


def _preview(
    parsed_sha: str,
    total: int,
    valid: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    public_rows = []
    sensitive = {
        "government_id",
        "aadhaar_number",
        "father_number",
        "mother_number",
        "emergency_contact_number",
    }
    for row in valid[:MAX_PREVIEW_ROWS]:
        preview_row: dict[str, Any] = {}
        for key, value in row.items():
            if key.startswith("_") or key == "custom_fields" or key.endswith("_id"):
                continue
            if key in sensitive:
                preview_row[key] = _masked(value)
            else:
                preview_row[key] = (
                    value.isoformat()
                    if isinstance(value, date)
                    else str(value)
                    if isinstance(value, Decimal)
                    else value
                )
        public_rows.append(preview_row)
    result = {
        "sha256": parsed_sha,
        "row_count": total,
        "valid_count": len(valid),
        "error_count": len(errors),
        "errors": errors[:100],
        "warnings": warnings[:100],
        "preview": public_rows,
    }
    if summary:
        result["summary"] = summary
    return result


def _standard_import_class_sort_order(code: str, name: str) -> int | None:
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


async def _academic_structure_context(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
):
    await ensure_school_access(actor, db, school_id)
    campus = await ensure_campus_access(actor, db, campus_id)
    if campus.school_id != school_id:
        raise HTTPException(
            status_code=422, detail="Selected campus does not belong to this school"
        )
    if not campus.is_active:
        raise HTTPException(status_code=409, detail="Selected campus is inactive")
    return campus


async def _validate_classes(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    data: bytes,
):
    await _academic_structure_context(db, actor, school_id, campus_id)
    parsed = parse_xlsx(data, sheet_name="Classes", required_headers=CLASS_HEADERS)

    existing_result = await db.execute(
        select(AcademicClass).where(AcademicClass.campus_id == campus_id)
    )
    existing_classes = list(existing_result.scalars().all())
    existing_codes = {c.code.casefold(): c for c in existing_classes}
    existing_names = {c.name.casefold(): c for c in existing_classes}

    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    max_order_result = await db.execute(
        select(func.coalesce(func.max(AcademicClass.sort_order), 0)).where(
            AcademicClass.campus_id == campus_id
        )
    )
    next_order = int(max_order_result.scalar_one() or 0) + 10

    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            code = clean_text(raw.get("class_code"))
            name = clean_text(raw.get("class_name"))
            if not code:
                raise ValueError("Class Code is required")
            if not name:
                raise ValueError("Class Name is required")
            if len(code) > 50:
                raise ValueError("Class Code must be 50 characters or fewer")
            if len(name) > 100:
                raise ValueError("Class Name must be 100 characters or fewer")

            code_key = code.casefold()
            name_key = name.casefold()
            if code_key in seen_codes:
                raise ValueError("Duplicate Class Code in workbook")
            if code_key in existing_codes:
                raise ValueError("Class Code already exists in the selected campus")
            seen_codes.add(code_key)

            if name_key in seen_names:
                warnings.append(
                    _issue(
                        row_no,
                        "Duplicate Class Name appears in this workbook. Class Code remains the unique identifier.",
                        "Class Name",
                    )
                )
            elif name_key in existing_names:
                warnings.append(
                    _issue(
                        row_no,
                        "A class with the same name already exists in this campus under a different code.",
                        "Class Name",
                    )
                )
            seen_names.add(name_key)

            suggested = _standard_import_class_sort_order(code, name)
            sort_order = suggested if suggested is not None else next_order
            if suggested is None:
                next_order += 10

            valid.append(
                {
                    "_row": row_no,
                    "class_code": code,
                    "class_name": name,
                    "sort_order": sort_order,
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))

    return parsed.sha256, valid, errors, warnings, len(parsed.rows)


async def _validate_sections(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    data: bytes,
):
    await _academic_structure_context(db, actor, school_id, campus_id)
    parsed = parse_xlsx(data, sheet_name="Sections", required_headers=SECTION_HEADERS)

    class_result = await db.execute(
        select(AcademicClass).where(
            AcademicClass.campus_id == campus_id,
            AcademicClass.is_active.is_(True),
        )
    )
    classes = list(class_result.scalars().all())
    by_class_code = {c.code.casefold(): c for c in classes}

    class_ids = [c.id for c in classes]
    existing_result = await db.execute(
        select(Section).where(
            Section.academic_class_id.in_(
                class_ids or [UUID("00000000-0000-0000-0000-000000000000")]
            )
        )
    )
    existing_sections = list(existing_result.scalars().all())
    existing_codes = {(s.academic_class_id, s.code.casefold()) for s in existing_sections}

    seen: set[tuple[UUID, str]] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            class_code = clean_text(raw.get("class_code"))
            section_code = clean_text(raw.get("section_code"))
            section_name = clean_text(raw.get("section_name"))
            if not class_code:
                raise ValueError("Class Code is required")
            if not section_code:
                raise ValueError("Section Code is required")
            if not section_name:
                raise ValueError("Section Name is required")
            if len(class_code) > 50:
                raise ValueError("Class Code must be 50 characters or fewer")
            if len(section_code) > 50:
                raise ValueError("Section Code must be 50 characters or fewer")
            if len(section_name) > 100:
                raise ValueError("Section Name must be 100 characters or fewer")

            academic_class = by_class_code.get(class_code.casefold())
            if not academic_class:
                raise ValueError(
                    "Class Code does not match an active Class in the selected campus. Import/create Classes first."
                )

            key = (academic_class.id, section_code.casefold())
            if key in seen:
                raise ValueError("Duplicate Section Code for this Class in workbook")
            if key in existing_codes:
                raise ValueError("Section Code already exists for this Class")
            seen.add(key)

            valid.append(
                {
                    "_row": row_no,
                    "class_code": academic_class.code,
                    "class_name": academic_class.name,
                    "section_code": section_code,
                    "section_name": section_name,
                    "academic_class_id": academic_class.id,
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))

    return parsed.sha256, valid, errors, warnings, len(parsed.rows)


def _generated_import_code(value: str, *, fallback: str, reserved: set[str]) -> str:
    """Generate a readable unique ERP code without asking users to enter technical codes."""
    base = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").upper() or fallback
    base = base[:50].rstrip("-") or fallback
    candidate = base
    suffix = 2
    while candidate.casefold() in reserved:
        tail = f"-{suffix}"
        candidate = f"{base[: 50 - len(tail)].rstrip('-')}{tail}"
        suffix += 1
    reserved.add(candidate.casefold())
    return candidate


def _parse_import_section_names(value: Any) -> tuple[list[str], bool]:
    text = clean_text(value)
    if not text:
        raise ValueError("Name of Section is required")
    raw_parts = text.split(",")
    if any(not part.strip() for part in raw_parts):
        raise ValueError("Section names must be separated by a single comma, for example A,B")
    names: list[str] = []
    seen: set[str] = set()
    removed_duplicate = False
    for part in raw_parts:
        name = part.strip()
        if len(name) > 100:
            raise ValueError("Each Section Name must be 100 characters or fewer")
        key = name.casefold()
        if key in seen:
            removed_duplicate = True
            continue
        seen.add(key)
        names.append(name)
    return names, removed_duplicate


async def _validate_class_sections(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    data: bytes,
):
    await _academic_structure_context(db, actor, school_id, campus_id)
    parsed = parse_xlsx(
        data, sheet_name=CLASS_SECTION_SHEET, required_headers=CLASS_SECTION_HEADERS
    )

    class_result = await db.execute(
        select(AcademicClass).where(AcademicClass.campus_id == campus_id)
    )
    existing_classes = list(class_result.scalars().all())
    classes_by_name: dict[str, list[AcademicClass]] = {}
    for item in existing_classes:
        classes_by_name.setdefault(item.name.casefold(), []).append(item)

    class_ids = [item.id for item in existing_classes]
    section_result = await db.execute(
        select(Section).where(
            Section.academic_class_id.in_(
                class_ids or [UUID("00000000-0000-0000-0000-000000000000")]
            )
        )
    )
    existing_sections = list(section_result.scalars().all())
    sections_by_class: dict[UUID, list[Section]] = {}
    for item in existing_sections:
        sections_by_class.setdefault(item.academic_class_id, []).append(item)

    reserved_class_codes = {item.code.casefold() for item in existing_classes}
    max_order_result = await db.execute(
        select(func.coalesce(func.max(AcademicClass.sort_order), 0)).where(
            AcademicClass.campus_id == campus_id
        )
    )
    next_order = int(max_order_result.scalar_one() or 0) + 10

    seen_class_names: set[str] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            class_name = clean_text(raw.get("class_name"))
            if not class_name:
                raise ValueError("Class Name is required")
            if len(class_name) > 100:
                raise ValueError("Class Name must be 100 characters or fewer")
            class_key = class_name.casefold()
            if class_key in seen_class_names:
                raise ValueError(
                    "Duplicate Class Name in workbook. Use one row per Class and comma-separated Sections."
                )
            seen_class_names.add(class_key)

            desired_sections, removed_duplicate = _parse_import_section_names(
                raw.get("name_of_section")
            )
            if removed_duplicate:
                warnings.append(
                    _issue(
                        row_no,
                        "Duplicate Section names in the row were ignored.",
                        "Name of Section",
                    )
                )

            matching_classes = classes_by_name.get(class_key, [])
            if len(matching_classes) > 1:
                raise ValueError(
                    "More than one ERP Class has this name. Rename the duplicate Classes before bulk import."
                )

            existing_class = matching_classes[0] if matching_classes else None
            if existing_class and not existing_class.is_active:
                raise ValueError(
                    "This Class already exists but is inactive. Activate it before adding Sections."
                )

            if existing_class:
                class_code = existing_class.code
                sort_order = existing_class.sort_order
                class_status = "Existing"
                reserved_section_codes = {
                    item.code.casefold() for item in sections_by_class.get(existing_class.id, [])
                }
                existing_by_name: dict[str, list[Section]] = {}
                for item in sections_by_class.get(existing_class.id, []):
                    existing_by_name.setdefault(item.name.casefold(), []).append(item)
            else:
                class_code = _generated_import_code(
                    class_name, fallback="CLASS", reserved=reserved_class_codes
                )
                suggested = _standard_import_class_sort_order(class_code, class_name)
                sort_order = suggested if suggested is not None else next_order
                if suggested is None:
                    next_order += 10
                class_status = "Create"
                reserved_section_codes: set[str] = set()
                existing_by_name = {}

            new_sections: list[dict[str, str]] = []
            existing_section_names: list[str] = []
            for section_name in desired_sections:
                section_key = section_name.casefold()
                matches = existing_by_name.get(section_key, [])
                if len(matches) > 1:
                    raise ValueError(
                        f"Section '{section_name}' exists more than once for this Class. Clean the duplicate data before import."
                    )
                if matches:
                    if not matches[0].is_active:
                        raise ValueError(
                            f"Section '{section_name}' already exists but is inactive. Activate it before bulk import."
                        )
                    existing_section_names.append(matches[0].name)
                    continue
                section_code = _generated_import_code(
                    section_name,
                    fallback="SECTION",
                    reserved=reserved_section_codes,
                )
                new_sections.append({"name": section_name, "code": section_code})

            if existing_class and not new_sections:
                warnings.append(
                    _issue(
                        row_no,
                        "Class and all listed Sections already exist; no new record will be created.",
                    )
                )

            valid.append(
                {
                    "_row": row_no,
                    "class_name": class_name,
                    "sections": ", ".join(desired_sections),
                    "class_status": class_status,
                    "sections_to_create": ", ".join(item["name"] for item in new_sections)
                    or "None",
                    "existing_sections": ", ".join(existing_section_names) or "None",
                    "_existing_class_id": existing_class.id if existing_class else None,
                    "_class_code": class_code,
                    "_sort_order": sort_order,
                    "_new_sections": new_sections,
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))

    summary = {
        "new_classes": sum(1 for row in valid if row["class_status"] == "Create"),
        "new_sections": sum(len(row["_new_sections"]) for row in valid),
        "existing_classes": sum(1 for row in valid if row["class_status"] == "Existing"),
        "existing_sections": sum(
            0 if row["existing_sections"] == "None" else len(row["existing_sections"].split(", "))
            for row in valid
        ),
    }
    return parsed.sha256, valid, errors, warnings, len(parsed.rows), summary


async def _student_context(db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "student")
    campus = await ensure_campus_access(actor, db, campus_id)
    if campus.school_id != school_id:
        raise HTTPException(
            status_code=422, detail="Selected campus does not belong to this school"
        )
    if not campus.is_active:
        raise HTTPException(status_code=409, detail="Selected campus is inactive")
    return campus


def _lookup_text(value: Any) -> str:
    return re.sub(r"\s+", " ", (clean_text(value) or "").strip()).casefold()


async def _student_reference_catalog(db: AsyncSession, campus_id: UUID):
    years = list(
        (
            await db.execute(
                select(AcademicYear)
                .where(AcademicYear.campus_id == campus_id)
                .order_by(AcademicYear.starts_on.desc())
            )
        )
        .scalars()
        .all()
    )
    classes = list(
        (
            await db.execute(
                select(AcademicClass)
                .where(AcademicClass.campus_id == campus_id)
                .order_by(AcademicClass.sort_order, AcademicClass.name)
            )
        )
        .scalars()
        .all()
    )
    class_ids = [item.id for item in classes]
    sections = list(
        (
            await db.execute(
                select(Section)
                .where(Section.academic_class_id.in_(class_ids or [UUID(int=0)]))
                .order_by(Section.name)
            )
        )
        .scalars()
        .all()
    )

    by_year: dict[str, AcademicYear] = {}
    for year in years:
        aliases = {year.code, year.name, f"{year.starts_on.year}-{str(year.ends_on.year)[-2:]}"}
        for alias in aliases:
            by_year[_lookup_text(alias)] = year

    by_class: dict[str, AcademicClass] = {}
    for academic_class in classes:
        by_class[_lookup_text(academic_class.code)] = academic_class
        by_class[_lookup_text(academic_class.name)] = academic_class

    by_section: dict[tuple[UUID, str], Section] = {}
    for section in sections:
        by_section[(section.academic_class_id, _lookup_text(section.code))] = section
        by_section[(section.academic_class_id, _lookup_text(section.name))] = section
    return years, classes, sections, by_year, by_class, by_section


async def _validate_students(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    data: bytes,
):
    await _student_context(db, actor, school_id, campus_id)
    _, _, _, by_year, by_class, by_section = await _student_reference_catalog(db, campus_id)
    parsed = parse_xlsx(
        data, sheet_name="Students", required_headers=STUDENT_HEADERS, header_aliases=COLUMN_ALIASES
    )

    admission_values = [clean_text(r.get("admission_number")) for r in parsed.rows]
    admission_values = [x.casefold() for x in admission_values if x]
    existing_result = await db.execute(
        select(func.lower(Student.admission_number)).where(
            Student.school_id == school_id,
            func.lower(Student.admission_number).in_(admission_values or ["__none__"]),
        )
    )
    existing = set(existing_result.scalars().all())
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            admission = clean_text(raw.get("admission_number"))
            if not admission:
                raise ValueError("Admission Number is required")
            if len(admission) > 100:
                raise ValueError("Admission Number must be 100 characters or fewer")
            admission_key = admission.casefold()
            if admission_key in seen:
                raise ValueError("Duplicate Admission Number in workbook")
            if admission_key in existing:
                raise ValueError("Admission Number already exists in this school")
            seen.add(admission_key)

            year_text = clean_text(raw.get("academic_year"))
            class_text = clean_text(raw.get("class_name"))
            section_text = clean_text(raw.get("section_name"))
            if not year_text:
                raise ValueError("Academic Year is required")
            if not class_text:
                raise ValueError("Class is required")
            if not section_text:
                raise ValueError("Section is required")
            year = by_year.get(_lookup_text(year_text))
            academic_class = by_class.get(_lookup_text(class_text))
            if not year:
                raise ValueError("Academic Year does not match the selected Campus")
            if year.is_read_only or year.status == "closed":
                raise ValueError("Historical Academic Year is read-only")
            if not academic_class:
                raise ValueError("Class does not match an ERP Class for the selected Campus")
            if not academic_class.is_active:
                raise ValueError("Class is inactive")
            section = by_section.get((academic_class.id, _lookup_text(section_text)))
            if not section:
                raise ValueError("Section does not belong to the Class in this row")
            if not section.is_active:
                raise ValueError("Section is inactive")

            first_name, last_name = split_name(raw.get("student_name"), field="Student Name")
            dob = parse_date(raw.get("date_of_birth"), field="Date of Birth")
            if not dob:
                raise ValueError("Date of Birth is required")
            admission_date = parse_date(raw.get("admission_date"), field="Admission Date")
            if not admission_date:
                raise ValueError("Admission Date is required")

            gender_text = _lookup_text(raw.get("gender"))
            gender = STUDENT_GENDERS.get(gender_text)
            if not gender:
                raise ValueError(
                    "Gender must be Male, Female, Transgender, Other or Prefer not to say"
                )

            father_name = clean_text(raw.get("father_name"))
            mother_name = clean_text(raw.get("mother_name"))
            if not father_name:
                raise ValueError("Father's Name is required")
            if not mother_name:
                raise ValueError("Mother's Name is required")
            father_number = normalize_phone(
                raw.get("father_number"), field="Father's Mobile Number", required=True
            )
            mother_number = normalize_phone(
                raw.get("mother_number"), field="Mother's Mobile Number"
            )
            emergency_number = normalize_phone(
                raw.get("emergency_contact_number"), field="Emergency Contact Number"
            )

            email_id = clean_text(raw.get("email_id"))
            if email_id:
                try:
                    email_id = validate_email(email_id, check_deliverability=False).normalized
                except EmailNotValidError as exc:
                    raise ValueError("Email ID is not valid") from exc

            aadhaar = normalize_aadhaar(raw.get("aadhaar_number"))
            category = (clean_text(raw.get("caste_category")) or "").upper()
            if category not in STUDENT_CASTE_CATEGORIES:
                raise ValueError(
                    "Caste Category must be one of OC, SC, ST, BC-A, BC-B, BC-C, BC-D, BC-E or BC-F"
                )

            sis_input = clean_text(raw.get("sis_number"))
            if sis_input:
                warnings.append(
                    _issue(
                        row_no,
                        "SIS Number is system-generated; the supplied value is ignored.",
                        "SIS Number",
                    )
                )
            status_input = clean_text(raw.get("student_status"))
            if status_input:
                warnings.append(
                    _issue(
                        row_no,
                        "Student Status is system-generated as Active; the supplied value is ignored.",
                        "Student Status",
                    )
                )

            valid.append(
                {
                    "_row": row_no,
                    "sis_number": "Generated by ERP",
                    "academic_year": year.name,
                    "admission_number": admission,
                    "admission_date": admission_date,
                    "student_name": " ".join(part for part in (first_name, last_name) if part),
                    "_first_name": first_name,
                    "_last_name": last_name,
                    "date_of_birth": dob,
                    "gender": gender,
                    "class": academic_class.name,
                    "section": section.name,
                    "father_name": father_name,
                    "mother_name": mother_name,
                    "father_number": father_number,
                    "mother_number": mother_number,
                    "email_id": email_id,
                    "aadhaar_number": aadhaar,
                    "_government_id": aadhaar,
                    "caste_category": category,
                    "sub_caste": clean_text(raw.get("sub_caste")),
                    "address": clean_text(raw.get("address")),
                    "emergency_contact_number": emergency_number,
                    "student_status": "Active",
                    "academic_year_id": year.id,
                    "academic_class_id": academic_class.id,
                    "section_id": section.id,
                    "custom_fields": {
                        "sub_caste": clean_text(raw.get("sub_caste")),
                        "email_id": email_id,
                    },
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))
    return parsed.sha256, valid, errors, warnings, len(parsed.rows)


async def _teacher_context(db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "teacher")
    campus = await ensure_campus_access(actor, db, campus_id)
    if campus.school_id != school_id:
        raise HTTPException(
            status_code=422, detail="Selected campus does not belong to this school"
        )
    return campus


async def _validate_teachers(
    db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID, data: bytes
):
    await _teacher_context(db, actor, school_id, campus_id)
    parsed = parse_xlsx(data, sheet_name="Teachers", required_headers=TEACHER_HEADERS)
    employee_values = [clean_text(r.get("employee_number")) for r in parsed.rows]
    employee_values = [x for x in employee_values if x]
    existing_result = await db.execute(
        select(Teacher.employee_code).where(
            Teacher.school_id == school_id,
            Teacher.employee_code.in_(employee_values or ["__none__"]),
        )
    )
    existing = set(existing_result.scalars().all())
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            employee = clean_text(raw.get("employee_number"))
            if not employee:
                raise ValueError("Employee Number is required")
            if len(employee) > 50:
                raise ValueError("Employee Number must be 50 characters or fewer")
            if employee in seen:
                raise ValueError("Duplicate Employee Number in workbook")
            if employee in existing:
                raise ValueError("Employee Number already exists in this school")
            seen.add(employee)
            first_name, last_name = split_name(raw.get("teacher_name"), field="Teacher Name")
            qualification = clean_text(raw.get("qualification"))
            if not qualification:
                raise ValueError("Qualification is required")
            father_number = normalize_phone(
                raw.get("father_number"), field="Father Number", required=True
            )
            mother_number = normalize_phone(raw.get("mother_number"), field="Mother Number")
            email = clean_text(raw.get("email"))
            if email:
                try:
                    email = validate_email(email, check_deliverability=False).normalized
                except EmailNotValidError as exc:
                    raise ValueError("Email is not valid") from exc
            valid.append(
                {
                    "_row": row_no,
                    "employee_code": employee,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "qualification": qualification,
                    "date_of_birth": parse_date(raw.get("date_of_birth"), field="Date of Birth"),
                    "government_id": normalize_aadhaar(raw.get("aadhaar_number")),
                    "designation": clean_text(raw.get("staff_category")),
                    "category": clean_text(raw.get("caste_category")),
                    "sub_category": clean_text(raw.get("sub_caste")),
                    "custom_fields": {
                        "father_name": clean_text(raw.get("father_name")),
                        "mother_name": clean_text(raw.get("mother_name")),
                        "father_number": father_number,
                        "mother_number": mother_number,
                    },
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))
    return parsed.sha256, valid, errors, warnings, len(parsed.rows)


async def _fee_import_context(db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    campus = await ensure_campus_access(actor, db, campus_id)
    if campus.school_id != school_id:
        raise HTTPException(
            status_code=422, detail="Selected campus does not belong to this school"
        )
    return campus


def _due_date_for_month(year: AcademicYear, month: int) -> date:
    target_year = year.starts_on.year if month >= year.starts_on.month else year.ends_on.year
    return date(target_year, month, 1)


def _year_aliases(year: AcademicYear) -> set[str]:
    aliases = {year.code.casefold(), year.name.casefold()}
    start = year.starts_on.year
    end = year.ends_on.year
    aliases.update(
        {
            f"{start}-{end}",
            f"{start}-{str(end)[-2:]}",
            f"{start}/{end}",
            f"{start}/{str(end)[-2:]}",
            f"academic year {start}-{end}",
            f"academic year {start}-{str(end)[-2:]}",
        }
    )
    return {re.sub(r"\s+", " ", a.strip()).casefold() for a in aliases}


async def _validate_fee_structures(
    db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID, data: bytes
):
    await _fee_import_context(db, actor, school_id, campus_id)
    parsed = parse_xlsx(data, sheet_name="Fee Structure", required_headers=FEE_STRUCTURE_HEADERS)
    year_result = await db.execute(select(AcademicYear).where(AcademicYear.campus_id == campus_id))
    years = list(year_result.scalars().all())
    class_result = await db.execute(
        select(AcademicClass).where(
            AcademicClass.campus_id == campus_id, AcademicClass.is_active.is_(True)
        )
    )
    classes = list(class_result.scalars().all())
    head_result = await db.execute(
        select(FeeHead).where(FeeHead.school_id == school_id, FeeHead.is_active.is_(True))
    )
    heads = list(head_result.scalars().all())
    by_year = {}
    for y in years:
        for alias in _year_aliases(y):
            by_year[alias] = y
    by_class = {}
    for c in classes:
        by_class[c.code.casefold()] = c
        by_class[c.name.casefold()] = c
    by_head = {}
    for h in heads:
        by_head[h.code.casefold()] = h
        by_head[h.name.casefold()] = h

    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            year_text = clean_text(raw.get("academic_year"))
            class_text = clean_text(raw.get("class_name"))
            head_text = clean_text(raw.get("fee_head"))
            if not year_text:
                raise ValueError("Academic Year is required")
            if not class_text:
                raise ValueError("Class Name is required")
            if not head_text:
                raise ValueError("Fee Head is required")
            year = by_year.get(year_text.casefold())
            academic_class = by_class.get(class_text.casefold())
            head = by_head.get(head_text.casefold())
            if not year:
                raise ValueError("Academic Year does not match this campus")
            if year.is_read_only or year.status == "closed":
                raise ValueError("Historical academic year is read-only")
            if not academic_class:
                raise ValueError("Class Name does not match this campus")
            if not head:
                raise ValueError("Fee Head does not exist in Fee Head Setup")
            amount = parse_decimal(raw.get("amount"), field="Amount", required=True)
            if amount is None:
                raise ValueError("Amount is required")
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
            frequency_text = clean_text(raw.get("frequency"))
            if not frequency_text or len(frequency_text) > 30:
                raise ValueError("Frequency is required and must be 30 characters or fewer")
            frequency = re.sub(r"[-_\s]+", "-", frequency_text.strip().lower())
            due_raw = raw.get("due_month")
            try:
                due_month = int(due_raw)
            except (TypeError, ValueError):
                raise ValueError("Due Month must be a whole number from 1 to 12")
            if due_month < 1 or due_month > 12:
                raise ValueError("Due Month must be from 1 to 12")
            due_date = _due_date_for_month(year, due_month)
            key = (year.id, academic_class.id, head.id, frequency.casefold(), str(amount), due_date)
            if key in seen:
                raise ValueError("Duplicate fee structure row in workbook")
            seen.add(key)
            existing = await db.execute(
                select(FeeStructureItem.id).where(
                    FeeStructureItem.school_id == school_id,
                    FeeStructureItem.campus_id == campus_id,
                    FeeStructureItem.academic_year_id == year.id,
                    FeeStructureItem.academic_class_id == academic_class.id,
                    FeeStructureItem.section_id.is_(None),
                    FeeStructureItem.fee_head_id == head.id,
                    func.lower(FeeStructureItem.frequency) == frequency,
                    FeeStructureItem.amount == amount,
                    FeeStructureItem.due_date == due_date,
                    FeeStructureItem.is_active.is_(True),
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Matching fee structure already exists")
            valid.append(
                {
                    "_row": row_no,
                    "academic_year": year.name,
                    "class_name": academic_class.name,
                    "fee_head": head.name,
                    "amount": amount,
                    "frequency": frequency,
                    "due_month": due_month,
                    "due_date": due_date,
                    "academic_year_id": year.id,
                    "academic_class_id": academic_class.id,
                    "fee_head_id": head.id,
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))
    total_amount = sum((r["amount"] for r in valid), Decimal("0"))
    return parsed.sha256, valid, errors, warnings, len(parsed.rows), total_amount


async def _validate_prior_dues(
    db: AsyncSession, actor: User, school_id: UUID, campus_id: UUID, fee_head_id: UUID, data: bytes
):
    await _fee_import_context(db, actor, school_id, campus_id)
    head = await db.get(FeeHead, fee_head_id)
    if not head or head.school_id != school_id or not head.is_active:
        raise HTTPException(status_code=422, detail="Select an active Fee Head from this school")
    parsed = parse_xlsx(data, sheet_name="Prior Year Dues", required_headers=PRIOR_DUE_HEADERS)
    students_result = await db.execute(
        select(Student).where(Student.school_id == school_id, Student.campus_id == campus_id)
    )
    students = list(students_result.scalars().all())
    by_admission = {x.admission_number.casefold(): x for x in students}
    years_result = await db.execute(select(AcademicYear).where(AcademicYear.campus_id == campus_id))
    years = list(years_result.scalars().all())
    by_year = {}
    for y in years:
        for alias in _year_aliases(y):
            by_year[alias] = y
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            admission = clean_text(raw.get("admission_number"))
            prior = clean_text(raw.get("prior_academic_year"))
            if not admission:
                raise ValueError("Admission Number is required")
            if not prior:
                raise ValueError("Prior Academic Year is required")
            student = by_admission.get(admission.casefold())
            if not student:
                raise ValueError("Student is not found in the selected campus")
            year = by_year.get(prior.casefold())
            if not year:
                raise ValueError("Prior Academic Year does not match this campus")
            amount = parse_decimal(
                raw.get("outstanding_amount"), field="Outstanding Amount", required=True
            )
            if amount is None:
                raise ValueError("Outstanding Amount is required")
            if amount <= 0:
                raise ValueError("Outstanding Amount must be greater than zero")
            key = (student.id, year.id, fee_head_id)
            if key in seen:
                raise ValueError("Duplicate student/prior-year due row in workbook")
            seen.add(key)
            existing = await db.execute(
                select(StudentCharge.id).where(
                    StudentCharge.school_id == school_id,
                    StudentCharge.student_id == student.id,
                    StudentCharge.academic_year_id == year.id,
                    StudentCharge.fee_head_id == fee_head_id,
                    StudentCharge.status.in_(["open", "paid", "partial"]),
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(
                    "A prior-year charge already exists for this student, year and fee head"
                )
            supplied_name = clean_text(raw.get("student_name"))
            expected_name = f"{student.first_name} {student.last_name or ''}".strip()
            if supplied_name and supplied_name.casefold() != expected_name.casefold():
                warnings.append(
                    _issue(
                        row_no,
                        "Student Name does not match ERP; Admission Number is used as the trusted identifier.",
                        "Student Name",
                    )
                )
            reference = clean_text(raw.get("reference"))
            valid.append(
                {
                    "_row": row_no,
                    "student_id": student.id,
                    "admission_number": student.admission_number,
                    "student_name": expected_name,
                    "prior_academic_year": year.name,
                    "outstanding_amount": amount,
                    "reference": reference,
                    "academic_year_id": year.id,
                    "fee_head_id": fee_head_id,
                    "due_date": year.ends_on,
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))
    total_amount = sum((r["outstanding_amount"] for r in valid), Decimal("0"))
    return parsed.sha256, valid, errors, warnings, len(parsed.rows), total_amount, head


async def _marks_context(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    academic_year_id: UUID,
    academic_class_id: UUID,
    section_id: UUID,
    subject_id: UUID,
):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "marks")
    campus = await ensure_campus_access(actor, db, campus_id)
    year = await db.get(AcademicYear, academic_year_id)
    academic_class = await db.get(AcademicClass, academic_class_id)
    section = await db.get(Section, section_id)
    subject = await db.get(Subject, subject_id)
    if campus.school_id != school_id:
        raise HTTPException(
            status_code=422, detail="Selected campus does not belong to this school"
        )
    if not year or year.campus_id != campus_id or year.is_read_only or year.status == "closed":
        raise HTTPException(
            status_code=422, detail="Select an active, writable academic year for this campus"
        )
    if not academic_class or academic_class.campus_id != campus_id:
        raise HTTPException(status_code=422, detail="Selected class does not belong to this campus")
    if not academic_class.is_active:
        raise HTTPException(
            status_code=409,
            detail="Selected class is inactive. Activate it or create an active class before importing students.",
        )
    if not section or section.academic_class_id != academic_class_id:
        raise HTTPException(
            status_code=422, detail="Selected section does not belong to this class"
        )
    if not section.is_active:
        raise HTTPException(
            status_code=409,
            detail="Selected section is inactive. Activate it or create an active section before importing students.",
        )
    if not subject or subject.campus_id != campus_id:
        raise HTTPException(
            status_code=422, detail="Selected subject does not belong to this campus"
        )
    return campus, year, academic_class, section, subject


async def _enrolled_students(
    db: AsyncSession,
    school_id: UUID,
    academic_year_id: UUID,
    academic_class_id: UUID,
    section_id: UUID,
):
    result = await db.execute(
        select(Student, StudentEnrollment.roll_number)
        .join(StudentEnrollment, StudentEnrollment.student_id == Student.id)
        .where(
            Student.school_id == school_id,
            StudentEnrollment.academic_year_id == academic_year_id,
            StudentEnrollment.academic_class_id == academic_class_id,
            StudentEnrollment.section_id == section_id,
            StudentEnrollment.status == "active",
        )
        .order_by(StudentEnrollment.roll_number, Student.first_name, Student.last_name)
    )
    return list(result.all())


async def _validate_marks(
    db: AsyncSession,
    actor: User,
    school_id: UUID,
    campus_id: UUID,
    academic_year_id: UUID,
    academic_class_id: UUID,
    section_id: UUID,
    subject_id: UUID,
    assessment_name: str,
    max_marks: Decimal,
    data: bytes,
):
    await _marks_context(
        db, actor, school_id, campus_id, academic_year_id, academic_class_id, section_id, subject_id
    )
    if not assessment_name.strip() or len(assessment_name.strip()) > 120:
        raise HTTPException(
            status_code=422,
            detail="Assessment Name is required and must be 120 characters or fewer",
        )
    if max_marks <= 0:
        raise HTTPException(status_code=422, detail="Maximum Marks must be greater than zero")
    parsed = parse_xlsx(data, sheet_name="Marks", required_headers=MARK_HEADERS)
    enrolled = await _enrolled_students(
        db, school_id, academic_year_id, academic_class_id, section_id
    )
    by_admission = {student.admission_number: student for student, _ in enrolled}
    student_ids = [student.id for student, _ in enrolled]
    locked_result = await db.execute(
        select(StudentMark.student_id).where(
            StudentMark.school_id == school_id,
            StudentMark.academic_year_id == academic_year_id,
            StudentMark.subject_id == subject_id,
            StudentMark.assessment_name == assessment_name.strip(),
            StudentMark.student_id.in_(
                student_ids or [UUID("00000000-0000-0000-0000-000000000000")]
            ),
            StudentMark.is_locked.is_(True),
        )
    )
    locked_ids = set(locked_result.scalars().all())
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for raw in parsed.rows:
        row_no = int(raw["__row__"])
        try:
            admission = clean_text(raw.get("admission_number"))
            if not admission:
                raise ValueError("Admission Number is required")
            if admission in seen:
                raise ValueError("Duplicate Admission Number in workbook")
            seen.add(admission)
            student = by_admission.get(admission)
            if not student:
                raise ValueError(
                    "Student is not enrolled in the selected academic year/class/section"
                )
            if student.id in locked_ids:
                raise ValueError("Marks are already finalized/locked for this student")
            obtained = parse_decimal(
                raw.get("marks_obtained"), field="Marks Obtained", required=True
            )
            if obtained is None:
                raise ValueError("Marks Obtained is required")
            if obtained < 0 or obtained > max_marks:
                raise ValueError(f"Marks Obtained must be between 0 and {max_marks}")
            supplied_name = clean_text(raw.get("student_name"))
            expected_name = f"{student.first_name} {student.last_name or ''}".strip()
            if supplied_name and supplied_name.casefold() != expected_name.casefold():
                warnings.append(
                    _issue(
                        row_no,
                        "Student Name does not match ERP; Admission Number is used as the trusted identifier.",
                        "Student Name",
                    )
                )
            valid.append(
                {
                    "_row": row_no,
                    "student_id": student.id,
                    "admission_number": admission,
                    "student_name": expected_name,
                    "marks_obtained": obtained,
                    "remarks": clean_text(raw.get("remarks")),
                }
            )
        except ValueError as exc:
            errors.append(_issue(row_no, str(exc)))
    return parsed.sha256, valid, errors, warnings, len(parsed.rows)


@router.get("/classes-sections/{school_id}/template")
async def class_section_import_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        User, Depends(require_permissions("academic_class.bulk_upload", "section.bulk_upload"))
    ],
):
    await ensure_school_access(actor, db, school_id)
    return FileResponse(
        TEMPLATE_DIR / "classes-sections-import.xlsx",
        filename="classes-sections-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/classes-sections/{school_id}/preview")
async def preview_class_sections(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        User, Depends(require_permissions("academic_class.bulk_upload", "section.bulk_upload"))
    ],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total, summary = await _validate_class_sections(
        db, actor, school_id, campus_id, data
    )
    return _preview(sha, total, valid, errors, warnings, summary=summary)


@router.post("/classes-sections/{school_id}/confirm")
async def confirm_class_sections(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[
        User, Depends(require_permissions("academic_class.bulk_upload", "section.bulk_upload"))
    ],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total, summary = await _validate_class_sections(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )

    created_classes = 0
    created_sections = 0
    for row in valid:
        class_id = row["_existing_class_id"]
        if class_id is None:
            academic_class = AcademicClass(
                campus_id=campus_id,
                code=row["_class_code"],
                name=row["class_name"],
                sort_order=row["_sort_order"],
                is_active=True,
            )
            db.add(academic_class)
            await db.flush()
            class_id = academic_class.id
            created_classes += 1

        for section in row["_new_sections"]:
            db.add(
                Section(
                    academic_class_id=class_id,
                    code=section["code"],
                    name=section["name"],
                    is_active=True,
                )
            )
            created_sections += 1

    await db.flush()
    await record_audit(
        db,
        action="academic.class_section.bulk_imported",
        user=actor,
        module="school_admin",
        entity_type="AcademicStructure",
        after={
            "class_count": created_classes,
            "section_count": created_sections,
            "source_sha256_prefix": sha[:12],
            "campus_id": str(campus_id),
        },
        request=request,
    )
    return {
        "imported": created_classes + created_sections,
        "warnings": len(warnings),
        "sha256": sha,
        "classes_created": created_classes,
        "sections_created": created_sections,
        "preview_summary": summary,
    }


@router.get("/classes/{school_id}/template", include_in_schema=False)
async def class_import_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("academic_class.bulk_upload"))],
):
    await ensure_school_access(actor, db, school_id)
    return FileResponse(
        TEMPLATE_DIR / "classes-import.xlsx",
        filename="classes-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/classes/{school_id}/preview", include_in_schema=False)
async def preview_classes(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("academic_class.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total = await _validate_classes(
        db, actor, school_id, campus_id, data
    )
    return _preview(sha, total, valid, errors, warnings)


@router.post("/classes/{school_id}/confirm", include_in_schema=False)
async def confirm_classes(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("academic_class.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total = await _validate_classes(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )

    for row in valid:
        db.add(
            AcademicClass(
                campus_id=campus_id,
                code=row["class_code"],
                name=row["class_name"],
                sort_order=row["sort_order"],
                is_active=True,
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="academic.class.bulk_imported",
        user=actor,
        module="school_admin",
        entity_type="AcademicClass",
        after={
            "record_count": len(valid),
            "source_sha256_prefix": sha[:12],
            "campus_id": str(campus_id),
        },
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/sections/{school_id}/template", include_in_schema=False)
async def section_import_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("section.bulk_upload"))],
):
    await ensure_school_access(actor, db, school_id)
    return FileResponse(
        TEMPLATE_DIR / "sections-import.xlsx",
        filename="sections-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/sections/{school_id}/preview", include_in_schema=False)
async def preview_sections(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("section.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total = await _validate_sections(
        db, actor, school_id, campus_id, data
    )
    return _preview(sha, total, valid, errors, warnings)


@router.post("/sections/{school_id}/confirm", include_in_schema=False)
async def confirm_sections(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("section.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total = await _validate_sections(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )

    for row in valid:
        db.add(
            Section(
                academic_class_id=row["academic_class_id"],
                code=row["section_code"],
                name=row["section_name"],
                is_active=True,
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="academic.section.bulk_imported",
        user=actor,
        module="school_admin",
        entity_type="Section",
        after={
            "record_count": len(valid),
            "source_sha256_prefix": sha[:12],
            "campus_id": str(campus_id),
        },
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/students/template-metadata")
async def student_template_metadata(
    _: Annotated[User, Depends(require_permissions("student.bulk_upload"))],
):
    return {
        "version": "3.0",
        "field_count": 20,
        "required_columns": list(REQUIRED_COLUMNS),
        "optional_columns": list(OPTIONAL_COLUMNS),
        "aliases": {key: sorted(value) for key, value in COLUMN_ALIASES.items()},
        "notes": {
            "sis_number": "System-generated; leave blank",
            "student_status": "System-generated as Active; leave blank",
            "prior_year_due": "Removed from Student Import; use the dedicated Prior Year Dues import",
        },
    }


@router.get("/students/{school_id}/template")
async def student_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("student.bulk_upload"))],
    campus_id: UUID = Query(...),
):
    await _student_context(db, actor, school_id, campus_id)
    years, classes, sections, _, _, _ = await _student_reference_catalog(db, campus_id)
    class_by_id = {item.id: item for item in classes}

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    headers = [
        "SIS Number (System Generated)",
        "Academic Year*",
        "Admission Number*",
        "Admission Date*",
        "Student Name*",
        "Date of Birth*",
        "Gender*",
        "Class*",
        "Section*",
        "Father's Name*",
        "Mother's Name*",
        "Father's Mobile Number*",
        "Mother's Mobile Number",
        "Email ID",
        "Aadhaar Number",
        "Caste Category*",
        "Sub-caste",
        "Address",
        "Emergency Contact Number",
        "Student Status (System Generated)",
    ]
    for col, value in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=value)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    widths = [23, 18, 20, 18, 24, 18, 16, 18, 18, 22, 22, 23, 23, 28, 20, 19, 18, 34, 25, 25]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
    ws.freeze_panes = "A2"

    ref = wb.create_sheet("ERP Reference")
    ref_headers = ["Academic Year", "Academic Year Status", "Class", "Section", "Active"]
    for col, value in enumerate(ref_headers, start=1):
        cell = ref.cell(row=1, column=col, value=value)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    row_no = 2
    for year in years:
        for section in sections:
            academic_class = class_by_id.get(section.academic_class_id)
            if not academic_class:
                continue
            ref.cell(row=row_no, column=1, value=year.code)
            ref.cell(row=row_no, column=2, value=year.status)
            ref.cell(row=row_no, column=3, value=academic_class.name)
            ref.cell(row=row_no, column=4, value=section.name)
            ref.cell(
                row=row_no,
                column=5,
                value="Yes" if academic_class.is_active and section.is_active else "No",
            )
            row_no += 1
    for col, width in enumerate([20, 20, 24, 18, 12], start=1):
        ref.column_dimensions[ref.cell(row=1, column=col).column_letter].width = width
    ref.freeze_panes = "A2"

    ins = wb.create_sheet("Instructions")
    rules = [
        ("Mandatory fields", "Headers ending with * are mandatory."),
        ("SIS Number", "Leave blank. ERP generates the SIS/student code."),
        ("Student Status", "Leave blank. ERP sets new enrolments to Active."),
        ("Academic Year", "Use an Academic Year from ERP Reference."),
        ("Class / Section", "Section must belong to the Class in the same row."),
        ("Dates", "Use a valid Excel date or YYYY-MM-DD."),
        (
            "Prior Year Due",
            "Not part of Student Import. Use Fee Management → Prior Year Dues Import.",
        ),
        ("Preview", "Validate & Preview the workbook before Confirm Import."),
    ]
    ins.append(["Rule", "Details"])
    for cell in ins[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for rule in rules:
        ins.append(list(rule))
    ins.column_dimensions["A"].width = 24
    ins.column_dimensions["B"].width = 95

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="students-import.xlsx"'},
    )


@router.post("/students/{school_id}/preview")
async def preview_students(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("student.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total = await _validate_students(
        db, actor, school_id, campus_id, data
    )
    return _preview(sha, total, valid, errors, warnings)


@router.post("/students/{school_id}/confirm")
async def confirm_students(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("student.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total = await _validate_students(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )

    for row in valid:
        student = Student(
            school_id=school_id,
            campus_id=campus_id,
            student_code=_student_code(),
            admission_number=row["admission_number"],
            first_name=row["_first_name"],
            last_name=row["_last_name"],
            date_of_birth=row["date_of_birth"],
            gender=row["gender"],
            government_id=row["_government_id"],
            admission_date=row["admission_date"],
            category=row["caste_category"],
            address_line1=row["address"],
            emergency_contact_name="Emergency Contact" if row["emergency_contact_number"] else None,
            emergency_contact_phone=row["emergency_contact_number"],
            custom_fields=row["custom_fields"],
            status="active",
        )
        db.add(student)
        await db.flush()

        father = Guardian(
            school_id=school_id,
            name=row["father_name"],
            relationship_type="Father",
            mobile=row["father_number"],
            email=row["email_id"],
            address=row["address"],
            is_primary=True,
        )
        db.add(father)
        await db.flush()
        db.add(StudentGuardian(student_id=student.id, guardian_id=father.id))

        mother = Guardian(
            school_id=school_id,
            name=row["mother_name"],
            relationship_type="Mother",
            mobile=row["mother_number"],
            address=row["address"],
            is_primary=False,
        )
        db.add(mother)
        await db.flush()
        db.add(StudentGuardian(student_id=student.id, guardian_id=mother.id))

        db.add(
            StudentEnrollment(
                student_id=student.id,
                academic_year_id=row["academic_year_id"],
                academic_class_id=row["academic_class_id"],
                section_id=row["section_id"],
                enrolled_on=row["admission_date"],
            )
        )

    await db.flush()
    await record_audit(
        db,
        action="student.bulk_imported",
        user=actor,
        module="student",
        entity_type="Student",
        after={
            "record_count": len(valid),
            "source_sha256_prefix": sha[:12],
            "campus_id": str(campus_id),
            "template_version": "3.0",
        },
        request=request,
        target_school_id=school_id,
        target_campus_id=campus_id,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/teachers/{school_id}/template")
async def teacher_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("teacher.bulk_upload"))],
):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "teacher")
    return FileResponse(
        TEMPLATE_DIR / "teachers-import.xlsx",
        filename="teachers-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/teachers/{school_id}/preview")
async def preview_teachers(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("teacher.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total = await _validate_teachers(
        db, actor, school_id, campus_id, data
    )
    return _preview(sha, total, valid, errors, warnings)


@router.post("/teachers/{school_id}/confirm")
async def confirm_teachers(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("teacher.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total = await _validate_teachers(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )
    for row in valid:
        db.add(
            Teacher(
                school_id=school_id,
                campus_id=campus_id,
                employee_code=row["employee_code"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                qualification=row["qualification"],
                date_of_birth=row["date_of_birth"],
                government_id=row["government_id"],
                designation=row["designation"],
                category=row["category"],
                sub_category=row["sub_category"],
                custom_fields=row["custom_fields"],
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="teacher.bulk_imported",
        user=actor,
        module="teacher",
        entity_type="Teacher",
        after={"record_count": len(valid), "source_sha256_prefix": sha[:12]},
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/fee-structures/{school_id}/template")
async def fee_structure_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.structure.bulk_upload"))],
):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    return FileResponse(
        TEMPLATE_DIR / "fee-structures-import.xlsx",
        filename="fee-structures-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/fee-structures/{school_id}/preview")
async def preview_fee_structures(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.structure.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total, total_amount = await _validate_fee_structures(
        db, actor, school_id, campus_id, data
    )
    return _preview(
        sha, total, valid, errors, warnings, {"total_amount": str(total_amount), "currency": "INR"}
    )


@router.post("/fee-structures/{school_id}/confirm")
async def confirm_fee_structures(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.structure.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total, total_amount = await _validate_fee_structures(
        db, actor, school_id, campus_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )
    for row in valid:
        db.add(
            FeeStructureItem(
                school_id=school_id,
                campus_id=campus_id,
                academic_year_id=row["academic_year_id"],
                academic_class_id=row["academic_class_id"],
                section_id=None,
                fee_head_id=row["fee_head_id"],
                frequency=row["frequency"],
                amount=row["amount"],
                due_date=row["due_date"],
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="fee.structure.bulk_imported",
        user=actor,
        module="fee",
        entity_type="FeeStructureItem",
        after={
            "record_count": len(valid),
            "total_amount": str(total_amount),
            "source_sha256_prefix": sha[:12],
        },
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/prior-year-dues/{school_id}/template")
async def prior_dues_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.dues.bulk_upload"))],
):
    await ensure_school_access(actor, db, school_id)
    await ensure_license_valid(school_id, db, "fee")
    return FileResponse(
        TEMPLATE_DIR / "prior-year-dues-import.xlsx",
        filename="prior-year-dues-import.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/prior-year-dues/{school_id}/preview")
async def preview_prior_dues(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.dues.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    fee_head_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total, total_amount, _head = await _validate_prior_dues(
        db, actor, school_id, campus_id, fee_head_id, data
    )
    return _preview(
        sha,
        total,
        valid,
        errors,
        warnings,
        {"total_outstanding": str(total_amount), "currency": "INR", "requires_confirmation": True},
    )


@router.post("/prior-year-dues/{school_id}/confirm")
async def confirm_prior_dues(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("fee.dues.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    fee_head_id: Annotated[UUID, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total, total_amount, head = await _validate_prior_dues(
        db, actor, school_id, campus_id, fee_head_id, data
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )
    for row in valid:
        reference = f" · {row['reference']}" if row.get("reference") else ""
        db.add(
            StudentCharge(
                school_id=school_id,
                student_id=row["student_id"],
                academic_year_id=row["academic_year_id"],
                fee_head_id=fee_head_id,
                description=f"Prior Year Due - {row['prior_academic_year']}{reference}"[:255],
                amount=row["outstanding_amount"],
                due_date=row["due_date"],
                status="open",
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="fee.prior_dues.bulk_imported",
        user=actor,
        module="fee",
        entity_type="StudentCharge",
        after={
            "record_count": len(valid),
            "total_outstanding": str(total_amount),
            "fee_head_id": str(head.id),
            "source_sha256_prefix": sha[:12],
        },
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}


@router.get("/marks/{school_id}/template")
async def marks_template(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("marks.bulk_upload"))],
    campus_id: UUID = Query(...),
    academic_year_id: UUID = Query(...),
    academic_class_id: UUID = Query(...),
    section_id: UUID = Query(...),
    subject_id: UUID = Query(...),
    assessment_name: str = Query(..., min_length=1, max_length=120),
    max_marks: Decimal = Query(..., gt=0),
):
    _, year, academic_class, section, subject = await _marks_context(
        db, actor, school_id, campus_id, academic_year_id, academic_class_id, section_id, subject_id
    )
    enrolled = await _enrolled_students(
        db, school_id, academic_year_id, academic_class_id, section_id
    )
    if not enrolled:
        raise HTTPException(
            status_code=409, detail="No active students are enrolled in the selected class/section"
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "Marks"
    ws.append(["Admission Number", "Student Name", "Marks Obtained", "Remarks"])
    for student, _roll in enrolled:
        ws.append(
            [
                student.admission_number,
                f"{student.first_name} {student.last_name or ''}".strip(),
                None,
                None,
            ]
        )
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1D4ED8")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 32
    ins = wb.create_sheet("Instructions")
    lines = [
        "Important instructions",
        f"Academic Year: {year.name}",
        f"Class: {academic_class.name}",
        f"Section: {section.name}",
        f"Subject: {subject.name}",
        f"Assessment: {assessment_name}",
        f"Maximum Marks: {max_marks}",
        "Do not change Admission Number. Student Name is informational; the ERP trusts Admission Number.",
        "Enter Marks Obtained only from 0 to Maximum Marks. Remarks are optional.",
        "Preview and fix all validation errors before confirming the import.",
    ]
    for line in lines:
        ins.append([line])
    ins["A1"].font = Font(bold=True)
    ins.column_dimensions["A"].width = 100
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="marks-import.xlsx"'},
    )


@router.post("/marks/{school_id}/preview")
async def preview_marks(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("marks.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    academic_year_id: Annotated[UUID, Form()],
    academic_class_id: Annotated[UUID, Form()],
    section_id: Annotated[UUID, Form()],
    subject_id: Annotated[UUID, Form()],
    assessment_name: Annotated[str, Form()],
    max_marks: Annotated[Decimal, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, total = await _validate_marks(
        db,
        actor,
        school_id,
        campus_id,
        academic_year_id,
        academic_class_id,
        section_id,
        subject_id,
        assessment_name,
        max_marks,
        data,
    )
    return _preview(sha, total, valid, errors, warnings)


@router.post("/marks/{school_id}/confirm")
async def confirm_marks(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("marks.bulk_upload"))],
    campus_id: Annotated[UUID, Form()],
    academic_year_id: Annotated[UUID, Form()],
    academic_class_id: Annotated[UUID, Form()],
    section_id: Annotated[UUID, Form()],
    subject_id: Annotated[UUID, Form()],
    assessment_name: Annotated[str, Form()],
    max_marks: Annotated[Decimal, Form()],
    expected_sha256: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    data = await read_upload(file)
    sha, valid, errors, warnings, _total = await _validate_marks(
        db,
        actor,
        school_id,
        campus_id,
        academic_year_id,
        academic_class_id,
        section_id,
        subject_id,
        assessment_name,
        max_marks,
        data,
    )
    if not hmac.compare_digest(sha, expected_sha256):
        raise HTTPException(
            status_code=409,
            detail="Workbook changed after preview. Preview the file again before importing.",
        )
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import contains validation errors", "errors": errors[:100]},
        )
    for row in valid:
        result = await db.execute(
            select(StudentMark).where(
                StudentMark.school_id == school_id,
                StudentMark.academic_year_id == academic_year_id,
                StudentMark.student_id == row["student_id"],
                StudentMark.subject_id == subject_id,
                StudentMark.assessment_name == assessment_name.strip(),
            )
        )
        mark = result.scalar_one_or_none()
        if mark and mark.is_locked:
            raise HTTPException(
                status_code=409, detail=f"Marks are locked for admission {row['admission_number']}"
            )
        if mark:
            mark.max_marks = max_marks
            mark.marks_obtained = row["marks_obtained"]
            mark.remarks = row["remarks"]
            mark.entered_by = actor.id
        else:
            db.add(
                StudentMark(
                    school_id=school_id,
                    campus_id=campus_id,
                    academic_year_id=academic_year_id,
                    student_id=row["student_id"],
                    subject_id=subject_id,
                    assessment_name=assessment_name.strip(),
                    max_marks=max_marks,
                    marks_obtained=row["marks_obtained"],
                    remarks=row["remarks"],
                    entered_by=actor.id,
                )
            )
    await db.flush()
    await record_audit(
        db,
        action="marks.bulk_imported",
        user=actor,
        module="marks",
        entity_type="StudentMark",
        after={
            "record_count": len(valid),
            "assessment_name": assessment_name.strip(),
            "source_sha256_prefix": sha[:12],
        },
        request=request,
    )
    return {"imported": len(valid), "warnings": len(warnings), "sha256": sha}
