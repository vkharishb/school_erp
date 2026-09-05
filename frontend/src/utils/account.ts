import type { AccountType, User } from "../types";

const ACCOUNT_LABELS: Record<AccountType, string> = {
  SUPER_ADMIN: "Platform Owner",
  ORGANIZATION_ADMIN: "Organization Admin",
  SCHOOL_ADMIN: "School / Branch Admin",
  ACCOUNTS: "Accountant",
  TEACHER: "Teacher",
  RECEPTIONIST: "Receptionist",
  PARENT_STUDENT: "Parent / Student",
};

export function accountLabel(type?: string | null): string {
  if (!type) return "User";
  return ACCOUNT_LABELS[type as AccountType] ?? type.replace(/_/g, " ");
}

export function displayDesignation(user?: User | null): string {
  if (!user) return "";
  if (user.is_superuser) return user.designation || "Platform Owner";
  return user.designation || accountLabel(user.account_type);
}

export function isAdminLevel(user?: User | null): boolean {
  return !!user && (
    user.is_superuser ||
    user.account_type === "ORGANIZATION_ADMIN" ||
    user.account_type === "SCHOOL_ADMIN"
  );
}

export function hasFinancialDashboard(user?: User | null): boolean {
  if (!user) return false;
  return user.is_superuser === false && ["ORGANIZATION_ADMIN", "SCHOOL_ADMIN", "ACCOUNTS"].includes(user.account_type);
}
