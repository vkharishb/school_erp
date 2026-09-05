from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.audit import ensure_admin_audit_access
from app.models.user import Role, User, UserRole


def _user(account_type: str, role_code: str, *, superuser: bool = False) -> User:
    user = User(
        username=f"{account_type.lower()}_{uuid4().hex[:8]}",
        account_type=account_type,
        full_name=account_type,
        hashed_password="not-used",
        is_superuser=superuser,
    )
    role = Role(code=role_code, name=role_code, is_system=True)
    user.roles = [UserRole(role=role)]
    return user


def test_all_admin_levels_can_view_audit_logs():
    ensure_admin_audit_access(_user("SUPER_ADMIN", "SUPER_ADMIN", superuser=True))
    ensure_admin_audit_access(_user("ORGANIZATION_ADMIN", "ORGANIZATION_ADMIN"))
    ensure_admin_audit_access(_user("SCHOOL_ADMIN", "SCHOOL_ADMIN"))


def test_non_admin_roles_cannot_view_audit_logs_even_if_endpoint_is_reached():
    with pytest.raises(HTTPException) as exc:
        ensure_admin_audit_access(_user("TEACHER", "TEACHER"))
    assert exc.value.status_code == 403
