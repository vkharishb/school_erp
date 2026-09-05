from app.services.imports.student_template import build_header_mapping

STUDENT_20_HEADERS = [
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


def test_new_student_20_field_headers_are_valid():
    mapping = build_header_mapping(STUDENT_20_HEADERS)
    assert mapping.is_valid
    assert mapping.missing_required == ()
    assert len(mapping.source_to_canonical) == 20


def test_missing_and_duplicate_import_headers_are_reported():
    mapping = build_header_mapping(["Admission Number", "Admission No", "Student Name"])
    assert not mapping.is_valid
    assert "admission_number" in mapping.duplicate_targets
    assert "academic_year" in mapping.missing_required
