import re
from dataclasses import dataclass

# Student enrolment and Student Bulk Upload deliberately share one 20-field model.
# SIS Number and Student Status are system-managed columns that remain visible in
# the workbook for clarity but are not supplied by users.
REQUIRED_COLUMNS = (
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
)

OPTIONAL_COLUMNS = (
    "mother_number",
    "email_id",
    "aadhaar_number",
    "sub_caste",
    "address",
    "emergency_contact_number",
)

COLUMN_ALIASES = {
    "sis_number": {"sis_number", "sis", "student_code", "sis number system generated"},
    "academic_year": {"academic_year", "academic_year_code", "session"},
    "admission_number": {"admission_number", "admission_no", "adm_no"},
    "admission_date": {"admission_date", "date_of_admission"},
    "student_name": {"student_name", "name"},
    "date_of_birth": {"date_of_birth", "dob", "birth_date"},
    "gender": {"gender", "sex"},
    "class_name": {"class", "class_name", "class_code", "grade"},
    "section_name": {"section", "section_name", "section_code"},
    "father_name": {"father_name", "fathers_name", "father's name"},
    "mother_name": {"mother_name", "mothers_name", "mother's name"},
    "father_number": {
        "father_number",
        "father_mobile_number",
        "father_mobile",
        "father's number",
        "father's mobile number",
    },
    "mother_number": {
        "mother_number",
        "mother_mobile_number",
        "mother_mobile",
        "mother's number",
        "mother's mobile number",
    },
    "email_id": {"email_id", "email", "parent_email"},
    "aadhaar_number": {"aadhaar_number", "aadhaar", "aadhaar number optional"},
    "caste_category": {"caste_category", "category", "social_category"},
    "sub_caste": {"sub_caste", "subcategory", "sub_category"},
    "address": {"address", "residential_address"},
    "emergency_contact_number": {"emergency_contact_number", "emergency_contact_phone"},
    "student_status": {"student_status", "status", "student status system generated"},
}


def normalize_header(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


@dataclass(frozen=True)
class HeaderMapping:
    source_to_canonical: dict[str, str]
    missing_required: tuple[str, ...]
    duplicate_targets: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.missing_required and not self.duplicate_targets


def build_header_mapping(headers: list[str]) -> HeaderMapping:
    alias_to_canonical = {
        normalize_header(alias): canonical
        for canonical, aliases in COLUMN_ALIASES.items()
        for alias in aliases
    }
    source_to_canonical: dict[str, str] = {}
    seen_targets: set[str] = set()
    duplicate_targets: set[str] = set()
    for header in headers:
        normalized = normalize_header(header)
        canonical = alias_to_canonical.get(normalized)
        if not canonical:
            continue
        if canonical in seen_targets:
            duplicate_targets.add(canonical)
        seen_targets.add(canonical)
        source_to_canonical[header] = canonical
    missing = tuple(column for column in REQUIRED_COLUMNS if column not in seen_targets)
    return HeaderMapping(
        source_to_canonical=source_to_canonical,
        missing_required=missing,
        duplicate_targets=tuple(sorted(duplicate_targets)),
    )
