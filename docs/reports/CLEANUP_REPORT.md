## 2026-09-09 — Schools update cleanup
School management UI now follows the approved table/list and compact-row architecture. No new duplicate report files or database migrations were introduced. Final global dead-code cleanup remains part of the release gate.

# SCHOOL ERP — Cleanup Report

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `CLEANUP_REPORT_V1.1.DEV.15.md`

# V1.1.dev15 Cleanup Report

Date: 2026-09-05

## Scope

Conservative cleanup of duplicated frontend helpers, route/navigation consistency,
unused CSS and code review, and role/permission enforcement. The release version
remains `V1.1.dev15`; no database model, migration, or business API was changed.

## Changes completed

- Added shared `FormField`, `FormSelect`, and `StatusAlert` UI components.
- Replaced repeated field/select/alert implementations in Marks, Teachers, and
  Academic Years pages.
- Centralized admin-level and school-directory role checks.
- Centralized bulk-import access so the route, sidebar, and administration card
  use the same policy as the usable import panels.
- Restricted the `/schools` directory route to Platform Owner and Organization
  Admin scope. School Admin remains on its assigned single-school scope.
- Fixed the Class & Section bulk-import navigation bug: both permissions are now
  required. Possessing only one no longer exposes an unusable route.
- Added regression tests for bulk-import access and school-directory scope.
- Removed client-specific school branding from runtime defaults.
- Removed hardcoded runtime signing secret, database URL, and Platform Owner
  username/email/password defaults; these settings now fail fast when absent.
- Made the bootstrap Platform Owner username environment-configurable.
- Replaced `python-jose`/`ecdsa` with PyJWT for the existing HS256 token flow.
- Updated vulnerable Python and npm dependency locks.
- Applied Ruff formatting and safe lint cleanup across the Python codebase.
- Fixed the Platform Owner's school-scoped Users list so it also includes the
  Organization Admin responsible for that school's organization.
- Kept hierarchy expansion server-enforced: Organization Admin and School Admin
  accounts cannot request visibility of superior organization-level users.

## Audit decisions

- No abandoned React route or unreferenced TypeScript component was proven by the
  compiler/import audit, so none was deleted.
- No custom CSS selector was unused. The header and ticker selectors remain active.
- Legacy individual Class and Section import endpoints/templates remain referenced
  by active backend routes and were retained for compatibility. The merged Class &
  Section import remains the frontend workflow.
- Marks upload remains inside Marks by design and was not duplicated in the central
  Bulk Imports page.

## Verification

| Check | Result |
| --- | --- |
| Frontend TypeScript type-check | Passed |
| Frontend strict unused symbols | Passed |
| Frontend navigation/utility tests | 14 passed |
| Frontend production/PWA build | Passed |
| Backend database-independent tests | 15 passed |
| Python Ruff lint and format | Passed: 132 files |
| NPM dependency audit | Passed: 0 known vulnerabilities |
| Python dependency audit | Passed: 0 known vulnerabilities |
| Bandit static security scan | 0 medium/high; 8 reviewed low informational findings |
| GitHub workflow YAML parse | Passed |
| Configured PyJWT HS256 smoke | Passed |
| Backend full suite | Environment-blocked: 21 passed, 31 setup errors because PostgreSQL host `db` was unavailable |
| Python source compilation | Passed |

The database-dependent errors are infrastructure connection failures during test
setup, not assertion failures caused by this cleanup. Run the full backend suite
with the test PostgreSQL service available before production acceptance.

## Files changed

- `frontend/src/App.tsx`
- `frontend/src/components/shell/AppSidebar.tsx`
- `frontend/src/components/ui/FormControls.tsx` (new)
- `frontend/src/pages/AcademicYearsPage.tsx`
- `frontend/src/pages/MarksPage.tsx`
- `frontend/src/pages/SchoolAdministrationPage.tsx`
- `frontend/src/pages/TeachersPage.tsx`
- `frontend/src/pages/UsersPage.tsx`
- `frontend/src/services/api.ts`
- `frontend/src/utils/bulkImports.ts`
- `frontend/src/utils/navigation.ts`
- `frontend/src/utils/permissions.ts`
- `frontend/tests/navigation.test.mjs`
- Python files were mechanically formatted by Ruff; functional Python changes are
  limited to configuration/bootstrap security, JWT dependency migration, explicit
  import validation guards, safe backup subprocess cleanup, and the guarded user
  hierarchy query in `backend/app/api/v1/users.py`.

## Remaining cleanup backlog

- Continue migrating page-local Field/Select/Alert helpers only when each page is
  functionally touched; their required/default behavior differs and a bulk rewrite
  would add unnecessary regression risk.
- Split the route table from `App.tsx` into declarative route metadata after adding
  rendered-route tests.
- Run database-backed RBAC, tenant-scope, migration, and API tests in Docker or the
  target Windows PostgreSQL environment.

---

## Imported history/source: `docs/PROJECT_CLEANUP.md`

# Project Cleanup — V1.2.9

Removed:
- accidental backend scratch file
- generated TypeScript build metadata
- unused Back-button component
- unused offline sync files
- obsolete Phase-0/cumulative patch-note clutter

Security cleanup:
- removed service-worker caching of authenticated API responses
- refreshed environment examples
- retained backend RBAC/tenant enforcement as the security boundary

Validation:
- Backend/Alembic Python syntax: PASS (81 files)
- Alembic head: 016
- Frontend orphan-source scan: PASS

A full local `npm ci && npm run build` is still recommended after extraction.
