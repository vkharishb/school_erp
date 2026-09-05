import type { User } from "../types";

export function hasPermission(user: User | null, code: string): boolean {
  if (!user) return false;
  if (user.is_superuser) return true;
  const permissions = user.permissions || [];
  return permissions.includes("*") || permissions.includes(code);
}

export function hasAnyPermission(user: User | null, codes: string[]): boolean {
  return codes.some((code) => hasPermission(user, code));
}

export function hasModule(user: User | null, moduleCode: string): boolean {
  if (!user) return false;
  if (user.is_superuser) return true;
  const modules = user.enabled_modules || [];
  return modules.includes("*") || modules.includes(moduleCode);
}

export function isAdminLevel(user: User | null): boolean {
  return !!user && (
    user.is_superuser ||
    user.account_type === "ORGANIZATION_ADMIN" ||
    user.account_type === "SCHOOL_ADMIN"
  );
}

export function canAccessSchoolDirectory(user: User | null): boolean {
  return !!user && (user.is_superuser || user.account_type === "ORGANIZATION_ADMIN");
}
