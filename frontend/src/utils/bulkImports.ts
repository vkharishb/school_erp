import type { User } from "../types";
import { hasModule, hasPermission } from "./permissions.ts";

export const BULK_IMPORT_PERMISSIONS = [
  "student.bulk_upload",
  "teacher.bulk_upload",
  "fee.structure.bulk_upload",
  "fee.dues.bulk_upload",
] as const;

export function canImportClassesAndSections(user: User | null): boolean {
  return hasPermission(user, "academic_class.bulk_upload") && hasPermission(user, "section.bulk_upload");
}

/** Keep route, menu, and page visibility aligned with the imports actually available. */
export function canAccessBulkImports(user: User | null): boolean {
  return canImportClassesAndSections(user) ||
    (hasModule(user, "student") && hasPermission(user, "student.bulk_upload")) ||
    (hasModule(user, "teacher") && hasPermission(user, "teacher.bulk_upload")) ||
    (hasModule(user, "fee") && (
      hasPermission(user, "fee.structure.bulk_upload") ||
      hasPermission(user, "fee.dues.bulk_upload")
    ));
}
