from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.deps import ensure_organization_read_access
from app.models.user import Role, User, UserRole


def _user(account_type: str, organization_id, role_code: str) -> User:
    user = User(
        username=f"{account_type.lower()}_{uuid4().hex[:8]}",
        account_type=account_type,
        full_name=account_type,
        hashed_password="not-used",
        organization_id=organization_id,
        is_superuser=False,
    )
    role = Role(code=role_code, name=role_code, is_system=True)
    user.roles = [UserRole(role=role)]
    return user


@pytest.mark.asyncio
async def test_school_admin_can_read_own_organization_academic_years():
    organization_id = uuid4()
    user = _user("SCHOOL_ADMIN", organization_id, "SCHOOL_ADMIN")
    await ensure_organization_read_access(user, organization_id)


@pytest.mark.asyncio
async def test_school_admin_cannot_read_another_organization_academic_years():
    user = _user("SCHOOL_ADMIN", uuid4(), "SCHOOL_ADMIN")
    with pytest.raises(HTTPException) as exc:
        await ensure_organization_read_access(user, uuid4())
    assert exc.value.status_code == 403
