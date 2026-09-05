import type { User } from "../types";
import { hasPermission } from "./permissions.ts";

export function canManageOrganizationAcademicYears(user: User | null | undefined): boolean {
  return hasPermission(user ?? null, "academic_year.manage");
}

export function usesOrganizationAcademicYears(user: User | null | undefined): boolean {
  if (!user) return false;
  return Boolean(
    user.is_superuser
    || user.account_type === "ORGANIZATION_ADMIN"
    || user.account_type === "SCHOOL_ADMIN"
    || user.roles?.includes("ORGANIZATION_ADMIN")
    || user.roles?.includes("SCHOOL_ADMIN")
  );
}
