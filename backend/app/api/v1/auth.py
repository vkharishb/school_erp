from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import ensure_user_tenant_active, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.usernames import normalize_username
from app.db.session import get_db
from app.models.session import UserSession, hash_token, utcnow
from app.models.user import Role, RolePermission, User, UserRole
from app.schemas.auth import ACCOUNT_TYPES, ChangePasswordRequest, LoginRequest, Token, UserOut
from app.services.audit import record_audit
from app.services.auth_rate_limit import clear_login_rate_limit, enforce_login_rate_limit
from app.services.module_access import effective_enabled_modules
from app.services.password_policy import validate_password

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )


async def _issue_tokens(
    user: User,
    db: AsyncSession,
    *,
    request: Request,
    family_id: UUID | None = None,
    parent_session: UserSession | None = None,
) -> tuple[Token, str]:
    session_id = uuid4()
    token_family_id = family_id or uuid4()
    extra = {
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "school_id": str(user.school_id) if user.school_id else None,
        "campus_id": str(user.campus_id) if user.campus_id else None,
        "sid": str(session_id),
        "is_superuser": user.is_superuser,
    }
    access = create_access_token(subject=str(user.id), extra_claims=extra)
    refresh = create_refresh_token(
        subject=str(user.id), session_id=str(session_id), family_id=str(token_family_id)
    )
    session = UserSession(
        id=session_id,
        family_id=token_family_id,
        user_id=user.id,
        parent_session_id=parent_session.id if parent_session else None,
        token_hash=hash_token(refresh),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    # Persist the replacement session before wiring the parent session to it.
    # PostgreSQL enforces the self-referential FK immediately, so setting
    # replaced_by_session_id before the INSERT has been flushed can fail with
    # sqlstate=23503 during refresh-token rotation.
    await db.flush()
    if parent_session:
        parent_session.replaced_by_session_id = session_id
        await db.flush()
    return Token(access_token=access, token_type="bearer"), refresh


async def _find_users_for_login(
    db: AsyncSession, login_id: str, account_type: str | None
) -> list[User]:
    login_id = login_id.strip()
    normalized_type = account_type.strip().upper() if account_type else None
    if normalized_type and normalized_type not in ACCOUNT_TYPES:
        return []
    query = select(User)
    if normalized_type == "PARENT_STUDENT":
        query = query.where(User.phone == login_id, User.account_type == "PARENT_STUDENT")
    elif normalized_type == "ORGANIZATION_ADMIN":
        normalized_login = normalize_username(login_id)
        query = query.where(
            User.account_type == "ORGANIZATION_ADMIN",
            or_(
                func.lower(User.username) == normalized_login,
                func.lower(User.email) == normalized_login,
            ),
        )
    elif normalized_type == "SUPER_ADMIN":
        # Platform Owner authentication is based on the superuser flag so older
        # bootstrap records with a legacy account_type remain usable. The login
        # identifier itself is still case-insensitive.
        query = query.where(
            User.is_superuser.is_(True),
            func.lower(User.username) == normalize_username(login_id),
        )
    else:
        query = query.where(func.lower(User.username) == normalize_username(login_id))
        if normalized_type:
            query = query.where(User.account_type == normalized_type)
    result = await db.execute(query)
    return list(result.scalars().all())


def _user_to_out(user: User, enabled_modules: list[str] | None = None) -> UserOut:
    role_codes: list[str] = []
    permission_codes: set[str] = set()
    for ur in user.roles or []:
        if not ur.role:
            continue
        role_codes.append(ur.role.code)
        for rp in ur.role.permissions or []:
            if rp.permission:
                permission_codes.add(rp.permission.code)
    return UserOut(
        id=user.id,
        username=user.username,
        account_type=user.account_type,
        email=user.email,
        full_name=user.full_name,
        designation=user.designation,
        phone=user.phone,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
        organization_id=user.organization_id,
        school_id=user.school_id,
        campus_id=user.campus_id,
        last_login_at=user.last_login_at,
        roles=sorted(role_codes),
        permissions=["*"] if user.is_superuser else sorted(permission_codes),
        enabled_modules=["*"] if user.is_superuser else sorted(set(enabled_modules or [])),
    )


async def _complete_login(
    request: Request,
    response: Response,
    login_id: str,
    password: str,
    db: AsyncSession,
    account_type: str | None = None,
) -> Token:
    normalized_type = account_type.strip().upper() if account_type else None
    limiter_login = (
        login_id.strip() if normalized_type == "PARENT_STUDENT" else normalize_username(login_id)
    )
    limiter_key = f"{normalized_type or 'LEGACY'}:{limiter_login}"
    await enforce_login_rate_limit(request, limiter_key)
    candidates = await _find_users_for_login(db, login_id, normalized_type)
    matching = [user for user in candidates if verify_password(password, user.hashed_password)]
    # Never reveal whether a username/phone exists or which account type it belongs to.
    if len(matching) != 1:
        raise HTTPException(
            status_code=401,
            detail="Invalid account type or login credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = matching[0]
    if (
        normalized_type
        and normalized_type != "SUPER_ADMIN"
        and user.account_type != normalized_type
    ):
        raise HTTPException(status_code=401, detail="Invalid account type or login credentials.")
    if normalized_type == "SUPER_ADMIN" and not user.is_superuser:
        raise HTTPException(status_code=401, detail="Invalid account type or login credentials.")
    if user.is_superuser and user.account_type != "SUPER_ADMIN":
        # Canonicalize legacy Platform Owner records after a successful login.
        user.account_type = "SUPER_ADMIN"
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    await ensure_user_tenant_active(user, db)
    user.last_login_at = datetime.now(UTC)
    await clear_login_rate_limit(request, limiter_key)
    token, refresh = await _issue_tokens(user, db, request=request)
    _set_refresh_cookie(response, refresh)
    await record_audit(db, action="login", user=user, module="auth", request=request)
    # Persist the server-side session before the client immediately calls /auth/me.
    # FastAPI yield-dependency cleanup can occur after the response is available,
    # which otherwise creates a race where the access token references an
    # uncommitted UserSession and /auth/me returns 401.
    await db.commit()
    return token


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # OAuth2 form remains as a compatibility endpoint; the branded UI uses /login/json.
    return await _complete_login(request, response, form_data.username, form_data.password, db)


@router.post("/login/json", response_model=Token)
async def login_json(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await _complete_login(
        request, response, body.username, body.password, db, account_type=body.account_type
    )


async def _revoke_family(
    db: AsyncSession, family_id: UUID, *, reason: str, reuse_detected: bool = False
) -> None:
    now = utcnow()
    values = {"is_active": False, "revoked_at": now, "revocation_reason": reason}
    if reuse_detected:
        values["reuse_detected_at"] = now
    await db.execute(update(UserSession).where(UserSession.family_id == family_id).values(**values))


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)] = None,
):
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="Refresh session is missing")
    payload = decode_token(refresh_cookie)
    if not payload or payload.get("type") != "refresh" or not payload.get("sub"):
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        family_id = UUID(payload["family_id"])
        session_id = UUID(payload["sid"])
    except (KeyError, TypeError, ValueError) as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    result = await db.execute(
        select(UserSession)
        .where(UserSession.id == session_id, UserSession.token_hash == hash_token(refresh_cookie))
        .with_for_update()
    )
    session = result.scalar_one_or_none()
    if not session:
        await _revoke_family(db, family_id, reason="refresh_token_reuse", reuse_detected=True)
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Refresh token reuse detected")
    if session.family_id != family_id:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not session.is_valid:
        if session.replaced_by_session_id or session.revocation_reason == "rotated":
            await _revoke_family(
                db, session.family_id, reason="refresh_token_reuse", reuse_detected=True
            )
            await db.commit()
            _clear_refresh_cookie(response)
            raise HTTPException(status_code=401, detail="Refresh token reuse detected")
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        await _revoke_family(db, session.family_id, reason="user_inactive")
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    try:
        await ensure_user_tenant_active(user, db)
    except HTTPException:
        await _revoke_family(db, session.family_id, reason="tenant_disabled")
        _clear_refresh_cookie(response)
        raise

    session.revoked_at = utcnow()
    session.is_active = False
    session.revocation_reason = "rotated"
    session.last_used_at = utcnow()
    await db.flush()
    token, refresh = await _issue_tokens(
        user, db, request=request, family_id=session.family_id, parent_session=session
    )
    _set_refresh_cookie(response, refresh)
    # Make the rotated session visible before callers use the new access token.
    await db.commit()
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_cookie: Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)] = None,
):
    _clear_refresh_cookie(response)
    if not refresh_cookie:
        return None
    payload = decode_token(refresh_cookie)
    actor = None
    if payload and payload.get("sub"):
        try:
            actor = await db.get(User, UUID(payload["sub"]))
        except (TypeError, ValueError):
            actor = None
    family_id = payload.get("family_id") if payload else None
    if family_id:
        try:
            await _revoke_family(db, UUID(family_id), reason="logout")
        except ValueError:
            pass
    else:
        result = await db.execute(
            select(UserSession).where(UserSession.token_hash == hash_token(refresh_cookie))
        )
        session = result.scalar_one_or_none()
        if session:
            session.revoked_at = utcnow()
            session.is_active = False
            session.revocation_reason = "logout"
            actor = actor or await db.get(User, session.user_id)
    if actor:
        await record_audit(db, action="logout", user=actor, module="auth", request=request)
    await db.flush()
    await db.commit()
    return None


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=422, detail="Current password is incorrect")
    validate_password(body.new_password, username=user.username)
    if verify_password(body.new_password, user.hashed_password):
        raise HTTPException(
            status_code=422, detail="New password must be different from current password"
        )
    user.hashed_password = get_password_hash(body.new_password)
    user.must_change_password = False
    now = utcnow()
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=now, revocation_reason="password_changed")
    )
    await record_audit(
        db,
        action="user.password.changed",
        user=user,
        module="auth",
        entity_type="User",
        entity_id=user.id,
        request=request,
    )
    _clear_refresh_cookie(response)
    await db.flush()
    # Password and session revocations must be durable before the response
    # instructs the user to sign in again.
    await db.commit()
    return None


@router.get("/me", response_model=UserOut)
async def read_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission)
        )
        .where(User.id == current_user.id)
    )
    user = result.scalar_one()
    enabled_modules = await effective_enabled_modules(db, user)
    return _user_to_out(user, enabled_modules)
