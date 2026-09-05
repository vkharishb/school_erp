import type { User } from "../types";
import { hasAnyPermission, hasModule, hasPermission, isAdminLevel } from "./permissions.ts";

export interface PrimaryNavigationVisibility {
  schoolAdministration: boolean;
  students: boolean;
  teachers: boolean;
  fees: boolean;
  marks: boolean;
  attendance: boolean;
  reports: boolean;
}

export function primaryNavigationVisibility(user: User | null): PrimaryNavigationVisibility {
  return {
    schoolAdministration: isAdminLevel(user) && hasAnyPermission(user, [
      "school.admin.view", "school.config.view", "user.view", "license.view",
      "academic_year.view", "academic_class.manage", "subject.manage", "audit.view",
    ]),
    students: hasPermission(user, "student.view") && hasModule(user, "student"),
    teachers: hasPermission(user, "teacher.view") && hasModule(user, "teacher"),
    fees: hasPermission(user, "fee.view") && hasModule(user, "fee"),
    marks: hasPermission(user, "marks.view") && hasModule(user, "marks"),
    attendance: hasPermission(user, "attendance.view") && hasModule(user, "attendance"),
    reports: hasPermission(user, "reports.view") && hasModule(user, "reports"),
  };
}
