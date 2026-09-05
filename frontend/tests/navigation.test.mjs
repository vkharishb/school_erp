import assert from "node:assert/strict";
import test from "node:test";

import { primaryNavigationVisibility } from "../src/utils/navigation.ts";
import { canManageOrganizationAcademicYears, usesOrganizationAcademicYears } from "../src/utils/academicYears.ts";
import { canAccessBulkImports, canImportClassesAndSections } from "../src/utils/bulkImports.ts";
import { canAccessSchoolDirectory, isAdminLevel } from "../src/utils/permissions.ts";

const modules = [
  "dashboard", "school_admin", "school_config", "student", "teacher",
  "fee", "marks", "attendance", "reports",
];

function user(accountType, permissions, overrides = {}) {
  return {
    id: `${accountType.toLowerCase()}-id`,
    username: accountType.toLowerCase(),
    account_type: accountType,
    full_name: accountType,
    is_active: true,
    is_superuser: accountType === "SUPER_ADMIN",
    roles: [accountType],
    permissions,
    enabled_modules: modules,
    ...overrides,
  };
}

const allVisible = {
  schoolAdministration: true,
  students: true,
  teachers: true,
  fees: true,
  marks: true,
  attendance: true,
  reports: true,
};

test("platform, organization and school administrators receive the complete core navigation", () => {
  assert.deepEqual(primaryNavigationVisibility(user("SUPER_ADMIN", ["*"])), allVisible);
  const adminPermissions = [
    "school.admin.view", "student.view", "teacher.view", "fee.view",
    "marks.view", "attendance.view", "reports.view",
  ];
  assert.deepEqual(primaryNavigationVisibility(user("ORGANIZATION_ADMIN", adminPermissions)), allVisible);
  assert.deepEqual(primaryNavigationVisibility(user("SCHOOL_ADMIN", adminPermissions)), allVisible);
});

test("accounts navigation is limited to students, fees and reports", () => {
  assert.deepEqual(
    primaryNavigationVisibility(user("ACCOUNTS", ["student.view", "fee.view", "reports.view"])),
    {...allVisible, schoolAdministration:false, teachers:false, marks:false, attendance:false},
  );
});

test("teacher navigation is limited to assigned operational modules", () => {
  assert.deepEqual(
    primaryNavigationVisibility(user("TEACHER", ["student.view", "teacher.view", "marks.view", "attendance.view", "reports.view"])),
    {...allVisible, schoolAdministration:false, fees:false},
  );
});

test("reception and parent/student navigation stay least-privileged", () => {
  assert.deepEqual(
    primaryNavigationVisibility(user("RECEPTIONIST", ["fee.view", "teacher.view"])),
    {...allVisible, schoolAdministration:false, students:false, marks:false, attendance:false, reports:false},
  );
  assert.deepEqual(
    primaryNavigationVisibility(user("PARENT_STUDENT", ["parent_student.portal.view"])),
    {...allVisible, schoolAdministration:false, students:false, teachers:false, fees:false, marks:false, attendance:false, reports:false},
  );
});

test("a permission never exposes a module missing from the effective entitlement", () => {
  const organizationAdmin = user(
    "ORGANIZATION_ADMIN",
    ["school.admin.view", "student.view", "teacher.view", "fee.view", "marks.view", "attendance.view", "reports.view"],
    {enabled_modules:["dashboard", "school_admin"]},
  );
  assert.deepEqual(
    primaryNavigationVisibility(organizationAdmin),
    {...allVisible, students:false, teachers:false, fees:false, marks:false, attendance:false, reports:false},
  );
});

test("signed-out state exposes no operational navigation", () => {
  assert.deepEqual(primaryNavigationVisibility(null), {
    schoolAdministration:false, students:false, teachers:false, fees:false,
    marks:false, attendance:false, reports:false,
  });
});


test("organization admin can manage organization-wide academic years when permission is granted", () => {
  const organizationAdmin = user("ORGANIZATION_ADMIN", ["academic_year.view", "academic_year.manage"]);
  assert.equal(canManageOrganizationAcademicYears(organizationAdmin), true);
  assert.equal(usesOrganizationAcademicYears(organizationAdmin), true);

  const schoolAdmin = user("SCHOOL_ADMIN", ["academic_year.view"]);
  assert.equal(canManageOrganizationAcademicYears(schoolAdmin), false);
  assert.equal(usesOrganizationAcademicYears(schoolAdmin), true);
});


test("merged Class & Section bulk import requires both scoped permissions", () => {
  const admin = user("SCHOOL_ADMIN", ["academic_class.bulk_upload", "section.bulk_upload"]);
  assert.equal(canImportClassesAndSections(admin), true);
  assert.equal(canImportClassesAndSections(user("SCHOOL_ADMIN", ["academic_class.bulk_upload"])), false);
  assert.equal(canImportClassesAndSections(user("SCHOOL_ADMIN", ["section.bulk_upload"])), false);
  assert.equal(canImportClassesAndSections(user("SUPER_ADMIN", ["*"])), true);
});

test("bulk-import route visibility matches usable import panels", () => {
  assert.equal(canAccessBulkImports(user("SCHOOL_ADMIN", ["academic_class.bulk_upload"])), false);
  assert.equal(canAccessBulkImports(user("SCHOOL_ADMIN", ["section.bulk_upload"])), false);
  assert.equal(canAccessBulkImports(user("SCHOOL_ADMIN", ["academic_class.bulk_upload", "section.bulk_upload"])), true);
  assert.equal(canAccessBulkImports(user("SCHOOL_ADMIN", ["student.bulk_upload"])), true);
  assert.equal(canAccessBulkImports(user("SCHOOL_ADMIN", ["student.bulk_upload"], {enabled_modules:["dashboard"]})), false);
});

test("school directory is limited to platform and organization scope", () => {
  assert.equal(canAccessSchoolDirectory(user("SUPER_ADMIN", ["*"])), true);
  assert.equal(canAccessSchoolDirectory(user("ORGANIZATION_ADMIN", ["school.admin.view"])), true);
  assert.equal(canAccessSchoolDirectory(user("SCHOOL_ADMIN", ["school.admin.view"])), false);
  assert.equal(isAdminLevel(user("SCHOOL_ADMIN", ["school.admin.view"])), true);
  assert.equal(isAdminLevel(user("TEACHER", ["school.admin.view"])), false);
});
