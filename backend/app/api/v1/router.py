from fastapi import APIRouter

from app.api.v1 import (
    approvals,
    attendance,
    audit,
    auth,
    dashboard,
    erp_access,
    fees,
    foundation,
    imports,
    marks,
    organizations,
    parent_student,
    rbac,
    reports,
    schools,
    students,
    system,
    teachers,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(schools.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(rbac.router)
api_router.include_router(imports.router)
api_router.include_router(foundation.router)
api_router.include_router(approvals.router)
api_router.include_router(students.router)
api_router.include_router(fees.router)
api_router.include_router(erp_access.router)
api_router.include_router(parent_student.router)
api_router.include_router(audit.router)
api_router.include_router(teachers.router)
api_router.include_router(attendance.router)
api_router.include_router(marks.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)

api_router.include_router(system.router)
