from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.license import SchoolLicense
from app.models.organization import Organization
from app.models.school import School
from app.models.user import User
from app.services.licensing import CORE_MODULES


async def effective_enabled_modules(db: AsyncSession, user: User) -> list[str]:
    """Return the module entitlement visible to the current account.

    Organization Admins operate across every School in their Organization, so
    their navigation is governed by the Organization license. School-scoped
    accounts receive only the intersection of the Organization and School
    licenses. Backend endpoints still enforce permission and tenant scope.
    """
    if user.is_superuser:
        return ["*"]

    if user.account_type == "ORGANIZATION_ADMIN" and user.organization_id:
        organization = await db.get(Organization, user.organization_id)
        return (
            sorted(set(organization.enabled_modules or []) | CORE_MODULES) if organization else []
        )

    if not user.school_id:
        return []

    school_license = (
        await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == user.school_id))
    ).scalar_one_or_none()
    if not school_license or not school_license.is_valid():
        return []

    school_modules = set(school_license.enabled_modules or []) | CORE_MODULES
    organization_id = user.organization_id
    if not organization_id:
        school = await db.get(School, user.school_id)
        organization_id = school.organization_id if school else None
    if not organization_id:
        return sorted(school_modules)

    organization = await db.get(Organization, organization_id)
    if not organization:
        return []
    organization_modules = set(organization.enabled_modules or []) | CORE_MODULES
    return sorted(school_modules & organization_modules)
