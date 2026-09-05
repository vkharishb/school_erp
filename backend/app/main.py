import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.audit import record_audit
from app.services.backups import create_backup, list_backups

settings = get_settings()
logger = logging.getLogger(__name__)


async def _scheduled_backup_loop() -> None:
    if settings.app_env.lower() in {"test", "ci"}:
        return
    while True:
        try:
            items = list_backups()
            due = True
            if items:
                from datetime import UTC, datetime, timedelta

                latest = datetime.fromisoformat(items[0]["created_at"])
                due = datetime.now(UTC) - latest >= timedelta(hours=settings.backup_schedule_hours)
            if due:
                await create_backup(label="scheduled")
        except Exception:
            logger.exception("Scheduled database backup failed")
        await asyncio.sleep(min(settings.backup_schedule_hours * 3600, 3600))


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_scheduled_backup_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant School ERP Platform - configurable, modular, secure.",
    version="V1.1.DEV.15",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CHANGE_CONTROL_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/login/json",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/change-password",
    "/api/v1/system/development-reset",
}


async def _record_generic_confirmed_change(request: Request) -> None:
    """Fallback audit so every successful confirmed mutation has an audit event."""
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    if not payload or not payload.get("sub"):
        return
    try:
        from uuid import UUID

        user_id = UUID(payload["sub"])
    except (TypeError, ValueError):
        return
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return
        await record_audit(
            db,
            action="change.confirmed",
            user=user,
            module="change_control",
            entity_type="API",
            entity_id=request.url.path,
            after={"method": request.method, "path": request.url.path},
            request=request,
        )
        await db.commit()


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id[:64]
    request.state.audit_recorded = False

    is_non_mutating_post = request.method.upper() == "POST" and request.url.path.endswith(
        "/preview"
    )
    is_controlled_change = (
        request.url.path.startswith("/api/v1/")
        and request.method.upper() in MUTATING_METHODS
        and request.url.path not in CHANGE_CONTROL_EXEMPT_PATHS
        and not is_non_mutating_post
    )
    if is_controlled_change:
        confirmed = (request.headers.get("X-Change-Confirmed") or "").strip().lower()
        if confirmed not in {"true", "1", "yes"}:
            return JSONResponse(
                status_code=428,
                content={
                    "error": {
                        "code": "change_confirmation_required",
                        "message": "Please confirm the change before submitting it.",
                        "details": None,
                    },
                    "request_id": request.state.request_id,
                },
                headers={"X-Request-ID": request.state.request_id},
            )
        reason = (request.headers.get("X-Change-Reason") or "").strip()
        if len(reason) < 3:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "change_reason_required",
                        "message": "A reason is mandatory for every confirmed change.",
                        "details": None,
                    },
                    "request_id": request.state.request_id,
                },
                headers={"X-Request-ID": request.state.request_id},
            )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if is_controlled_change and response.status_code < 400 and not request.state.audit_recorded:
        try:
            await _record_generic_confirmed_change(request)
        except Exception:
            logger.exception("Fallback change audit failed request_id=%s", request.state.request_id)
    return response


def _error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    details=None,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "request_id": getattr(request.state, "request_id", None),
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    details = None if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request,
            code=f"http_{exc.status_code}",
            message=message,
            details=details,
        ),
        headers=exc.headers,
    )


def _friendly_field(loc) -> str:
    parts = [
        str(x)
        for x in (loc or [])
        if str(x) not in {"body", "query", "path", "form", "header", "cookie"}
    ]
    labels = {
        "campus_id": "Campus",
        "school_id": "School / Branch",
        "organization_id": "Organization",
        "academic_year_id": "Academic Year",
        "academic_class_id": "Class",
        "class_id": "Class",
        "section_id": "Section",
        "subject_id": "Subject",
        "student_id": "Student",
        "teacher_id": "Teacher",
        "fee_head_id": "Fee Head",
        "role_code": "Role",
        "full_name": "Full Name",
        "admission_number": "Admission Number",
        "employee_code": "Employee Number",
        "starts_on": "Start Date",
        "ends_on": "End Date",
        "attendance_date": "Attendance Date",
        "marks_obtained": "Marks Obtained",
        "max_marks": "Maximum Marks",
        "assessment_name": "Assessment",
        "expected_sha256": "Validated File",
        "file": "Upload File",
        "password": "Password",
        "new_password": "New Password",
    }
    human = []
    for part in parts:
        if part.isdigit():
            continue
        human.append(labels.get(part, part.removesuffix("_id").replace("_", " ").title()))
    return " → ".join(human)


def _safe_validation_details(exc: RequestValidationError) -> list[dict]:
    # Never return Pydantic's raw `input` or context values; request bodies can
    # contain passwords, financial values, Aadhaar data, or other sensitive data.
    details = []
    for item in exc.errors():
        details.append(
            {
                "field": _friendly_field(item.get("loc")),
                "message": item.get("msg", "Invalid value"),
                "type": item.get("type", "validation_error"),
            }
        )
    return details


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = _safe_validation_details(exc)
    first = details[0] if details else None
    message = (
        f"{first['field']}: {first['message']}"
        if first and first.get("field")
        else first.get("message", "Please correct the submitted information")
        if first
        else "Please correct the submitted information"
    )
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request,
            code="validation_error",
            message=message,
            details=details,
        ),
    )


def _integrity_sqlstate(exc: IntegrityError) -> str | None:
    current = getattr(exc, "orig", None)
    for _ in range(3):
        if current is None:
            break
        state = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if state:
            return str(state)
        current = getattr(current, "__cause__", None)
    return None


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    # Convert common database constraint failures to safe, actionable messages.
    # Do not expose SQL, table names, constraint names, parameters, or PII.
    state = _integrity_sqlstate(exc)
    if state == "23505":
        message = (
            "A record with the same code, name, username, email, or identifier already exists."
        )
        code = "duplicate_record"
    elif state == "23503":
        message = "A selected related record no longer exists or is not available. Refresh the page and select it again."
        code = "invalid_reference"
    elif state == "23502":
        message = "A required value is missing. Complete all mandatory fields and try again."
        code = "required_value_missing"
    elif state == "23514":
        message = "One of the submitted values violates a data rule. Check the entered values and try again."
        code = "constraint_failed"
    else:
        message = (
            "The database rejected this change because it conflicts with existing or required data."
        )
        code = "data_conflict"
    logger.warning(
        "Database integrity error request_id=%s sqlstate=%s",
        getattr(request.state, "request_id", None),
        state,
    )
    return JSONResponse(
        status_code=409,
        content=_error_payload(request, code=code, message=message),
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            request,
            code="internal_error",
            message="The server could not complete this request. Please try again or provide the Reference ID to support.",
        ),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
