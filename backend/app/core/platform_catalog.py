"""Single source of truth for School ERP platform module delivery status.

This catalog is deliberately separate from per-school licensing.  It describes
what the product build currently contains so the Platform Owner can see an
honest development checklist in System Settings.
"""

from typing import TypedDict


class PlatformModule(TypedDict):
    code: str
    name: str
    phase: int
    status: str
    status_label: str
    note: str
    is_core: bool


PLATFORM_MODULES: list[PlatformModule] = [
    {
        "code": "dashboard",
        "name": "Dashboard",
        "phase": 1,
        "status": "ready_dev",
        "status_label": "Ready in DEV",
        "note": "Role-based dashboard foundation implemented; production QA still required.",
        "is_core": True,
    },
    {
        "code": "school_admin",
        "name": "School Administration",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Users, academic setup, classes/sections, subjects, bulk imports and audit controls implemented; UX/governance refinement continues.",
        "is_core": True,
    },
    {
        "code": "school_config",
        "name": "School Configuration",
        "phase": 1,
        "status": "ready_dev",
        "status_label": "Ready in DEV",
        "note": "Organization/school/campus configuration foundation implemented; production QA still required.",
        "is_core": True,
    },
    {
        "code": "student",
        "name": "Student Management",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "20-field enrolment and bulk-import alignment implemented; full student module UX refinement remains.",
        "is_core": True,
    },
    {
        "code": "teacher",
        "name": "Teacher Management",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Teacher master exists; joining fields, edit UX and bulk-template redesign remain.",
        "is_core": True,
    },
    {
        "code": "fee",
        "name": "Fee Management",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Core fee engine and governance exist; submodule UX and correction workflows are being refined.",
        "is_core": True,
    },
    {
        "code": "marks",
        "name": "Marks",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Entry, finalization and controlled reopen foundation implemented; remaining UX/data-scope QA required.",
        "is_core": True,
    },
    {
        "code": "attendance",
        "name": "Attendance",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Student/teacher attendance and correction audit exist; class/section workflow refinement remains.",
        "is_core": True,
    },
    {
        "code": "reports",
        "name": "Reports",
        "phase": 1,
        "status": "in_progress",
        "status_label": "In Progress",
        "note": "Report engine and Excel export foundation exist; card-based report centre and PDF workflow remain.",
        "is_core": True,
    },
    {
        "code": "exams",
        "name": "Exams",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "timetable",
        "name": "Timetable",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "homework",
        "name": "Homework",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "online_classes",
        "name": "Online Classes",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "lesson_plans",
        "name": "Lesson Plans",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "certificates",
        "name": "Certificates",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "id_cards",
        "name": "ID Cards",
        "phase": 2,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "communication",
        "name": "Communication",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "transport",
        "name": "Transport Management",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "gate_pass",
        "name": "Gate Pass",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "hostel",
        "name": "Hostel Management",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "call_logs",
        "name": "Call Logs",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "pickup_drop_alerts",
        "name": "Parent Pickup & Drop Alerts",
        "phase": 3,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "smart_attendance",
        "name": "Smart Attendance",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "face_attendance",
        "name": "Face Recognition Attendance",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "biometric",
        "name": "Biometric Integration",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "live_gps",
        "name": "Live GPS Tracking",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "route_monitoring",
        "name": "Route Monitoring",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
    {
        "code": "driver_app",
        "name": "Driver Mobile App",
        "phase": 4,
        "status": "planned",
        "status_label": "Planned",
        "note": "Planned future module.",
        "is_core": False,
    },
]


def module_status_summary() -> dict[str, int]:
    summary = {"ready_dev": 0, "in_progress": 0, "planned": 0}
    for module in PLATFORM_MODULES:
        summary[module["status"]] = summary.get(module["status"], 0) + 1
    summary["total"] = len(PLATFORM_MODULES)
    return summary
