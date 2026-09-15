## 2026-09-12 — Organization/School governance hardening validation
- School lifecycle authorization is centralized through `get_current_active_superuser`.
- School capacity consumption is guarded by a per-Organization database row lock acquired before counting non-archived Schools.
- The active OrganizationSubscription row is also selected with `FOR UPDATE` before its limit is evaluated.
- Added regression source assertions to prevent removal/reordering of these controls.
- Runtime concurrency verification remains part of formal PostgreSQL QA.


## 2026-09-09 — School module validation
- School create/edit uses shared exact email/mobile validation in touched frontend and backend paths.
- User-facing mobile input is limited to 10 numeric digits; backend stores India E.164 (+91).
- School capacity creation guard counts non-archived Schools, so disabling a School does not create a free entitlement slot.
- Mandatory lifecycle reason is backend-enforced for Disable/Enable and Archive.

# SCHOOL ERP — Validation Report

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.10.txt`

School ERP V1.1.DEV.10 — Development Validation
================================================

Decision: DEVELOPMENT VALIDATION PASSED; NOT YET PROMOTED TO QA.

Passed in the packaging environment
-----------------------------------
1. Backend complete API/regression suite: 40 passed in 47.89s using a disposable
   SQLite compatibility harness configured to preserve PostgreSQL partial-index
   semantics. This includes Organization Admin dual login, effective core modules,
   tenant isolation, dashboard metrics, lifecycle, fees, attendance, marks, imports,
   reports, session security and core-license enforcement.
2. Backend data-bearing Organization dashboard test: exact daily collection,
   outstanding/overdue dues, Student present/marked, Teacher present/marked and
   finalized-marks performance calculations passed.
3. Backend database-independent tests: 15 passed (also included in the 40-test run).
4. Frontend account/navigation tests: 6 passed, covering all seven predefined
   account types plus permission/entitlement intersection.
5. TypeScript: `npm run typecheck` passed.
6. Frontend production PWA build: 1,678 modules transformed; build passed.
7. Frontend production dependency audit: 0 vulnerabilities.
8. Python dependency consistency: no broken requirements.
9. Python source/test/migration compilation: passed.
10. Alembic 023 -> 024 PostgreSQL offline SQL generation: passed; JSON/module values
    render as deterministic SQL literals and head advances to 024.
11. Phase 1 catalogue consistency: nine modules are core in licensing, bootstrap,
    frontend provisioning, module display, tests and migration 024.
12. Version metadata: V1.1.DEV.10 / frontend 1.1.0-dev.10 / Alembic head 024.

Environment-specific gates still required before QA promotion
-------------------------------------------------------------
1. Run migration 023 -> 024 against PostgreSQL and confirm `alembic current` is
   `024 (head)`.
2. Run `pytest -q` against PostgreSQL/Redis; target is `40 passed`.
3. Complete a real-browser Organization Admin dashboard and card-to-report smoke
   test. This runner could not obtain a Chromium binary and its managed browser
   cannot access workspace localhost; this is an environment limitation, not an
   application test failure.
4. Backup -> restore verification remains a release-level Phase 1 gate.
5. Signed offline license-file activation is an approved Phase 1 plan item and is
   not implemented or represented as complete in this package.

Promotion rule
--------------
Do not label this package V1.1.QA.1 until the PostgreSQL 40-test result and browser
smoke test pass without defects.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.11.txt`

School ERP V1.1.DEV.11 — Targeted Bugfix Validation
===================================================

Decision: TARGETED DEVELOPMENT VALIDATION PASSED WITH ENVIRONMENT GATE; NOT PROMOTED TO QA.

Scope
-----
BUG-01: Organization Admin Academic Year create/manage UI permission and organization-level scope.
BUG-02: Audit Log human-readable actor identity.

Passed in this packaging environment
------------------------------------
1. Frontend Node regression tests: 7 passed.
   - Includes Organization Admin `academic_year.manage` visibility and organization-wide Academic Year mode.
   - Existing all-role navigation tests remain green.
2. Python application + test source compilation: passed.
3. Database-independent audit service/query smoke passed: new events snapshot actor full name/username and the actor-resolution query compiles with an outer join. The API keeps immutable `user_id` while the UI renders human-readable identity rather than raw UUID.
4. Version metadata updated to V1.1.DEV.11 / frontend 1.1.0-dev.11 / Alembic head 024.
5. No migration added because both corrections are application/API/UI fixes.

Environment gate not executed here
----------------------------------
- Database-backed targeted pytest could not start because the packaging runner does not have `asyncpg` installed. This is an environment dependency limitation, not a passed test.
- Frontend dependency-backed TypeScript production build was not run because `node_modules` is intentionally absent from the clean source package.

Required local/QA verification
------------------------------
1. Install backend requirements, use the disposable PostgreSQL test database, then run:
   pytest -q tests/test_audit_user_identity.py tests/test_organization_academic_year.py
2. Run the full backend regression suite against PostgreSQL/Redis.
3. Run `npm ci`, `npm run test`, `npm run typecheck`, and `npm run build`.
4. Browser smoke: login as Organization Admin for each Organization, open School Administration -> Academic Years, create a draft year, activate it, and confirm all campuses receive the projected year.
5. Browser smoke: open Audit Logs and confirm User shows full name + username rather than UUID.

Promotion rule
--------------
Do not label this package V1.1.QA.1 until the PostgreSQL/Redis and browser gates pass.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.12.txt`

School ERP V1.1.DEV.12 — Class & Section Bulk Import Validation
================================================================

Decision: DEVELOPMENT VALIDATION PASSED WITH ENVIRONMENT GATES; NOT PROMOTED TO QA.

Scope
-----
Merged Class + Section user-facing bulk import and approved two-column workbook template.

Passed in this packaging environment
------------------------------------
1. Frontend Node regression tests: 8 passed.
   - Includes merged Class & Section bulk permission test requiring both bulk permissions.
   - Existing navigation and Academic Year regression tests remain green.
2. Python application + test source compilation: passed.
3. XLSX parser smoke: approved workbook sheet `Classes & Sections` correctly normalizes `Class Name*` -> `class_name` and `Name of Section*` -> `name_of_section`; comma-separated sample rows parse correctly.
4. Targeted PostgreSQL integration tests were added for create and repeat/reuse behavior (`tests/test_class_section_bulk_import.py`).
5. Version metadata updated to V1.1.DEV.12 / frontend 1.1.0-dev.12 / Alembic head 024.
6. No migration added because the merged workflow uses the existing AcademicClass and Section tables.

Environment gates not executed here
-----------------------------------
- Database-backed pytest cannot start in the packaging runner because full backend runtime dependencies (including python-jose/asyncpg) are not installed.
- Frontend dependency-backed TypeScript build cannot run because `node_modules` is intentionally absent from the clean source package; direct typecheck therefore reports missing React/axios/zustand modules.

Required local/QA verification
------------------------------
1. Install backend requirements, point DATABASE_URL to the disposable PostgreSQL test database, run migrations and execute:
   pytest -q tests/test_class_section_bulk_import.py
2. Run the full backend PostgreSQL/Redis regression suite.
3. Run `npm ci`, `npm run test`, `npm run typecheck`, and `npm run build`.
4. Browser smoke: School Administration -> Bulk Imports -> select Campus / Branch. Confirm there is one Class & Section Import card (not separate Class and Section cards).
5. Download the template and confirm headers are `Class Name*` and `Name of Section*`.
6. Upload rows such as `Class 1 | A,B` and `Class 2 | A,B,C`; preview should report 2 new Classes and 5 new Sections, then confirmation should create them.
7. Re-upload the same file; preview should report existing records and create no duplicates.
8. Verify users missing either of the two bulk permissions cannot run the merged operation.

Promotion rule
--------------
Do not label this package V1.1.QA.1 until PostgreSQL/Redis, frontend build and browser gates pass.

In-place DEV.12 bug-fix addendum — 2026-09-03
------------------------------------------------
- Version remains V1.1.DEV.12; Alembic remains 024.
- School Admin can read organization-wide Academic Years and see Draft/Active/Closed state; create/edit/activate remain Organization Admin / Platform Super Admin only.
- Audit Logs now permit Platform Super Admin, Organization Admin and School Admin within their existing tenant/school scope.
- Audit actor display resolves Full Name + Username + Account Type; new events snapshot all three values in immutable audit metadata.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.13.txt`

School ERP V1.1.DEV.13 — Identity & Authentication Validation

Scope
-----
1. Add governed User designation/profile identity.
2. Sidebar identity order: Organization/School Name -> Person Name -> Designation.
3. Organization creation captures Organization Admin designation.
4. School / Branch creation supports atomic School Admin profile/login creation.
5. Existing admin profiles can be edited by an authorized higher-level admin.
6. Platform Owner/staff username authentication remains case-insensitive; passwords remain case-sensitive.
7. First-login password-change flow routes directly to Account Security.
8. Self-service /auth/change-password is exempt from generic business-change confirmation/reason middleware.
9. Successful password change revokes sessions and requires a fresh login.
10. All V1.1.DEV.12 Academic Year, Audit Log, and Class & Section import changes are retained.

Database
--------
- Alembic migration added: 025_user_designation.py
- down_revision: 024
- Static revision graph check: PASS; single head = 025

Validation completed in packaging environment
--------------------------------------------
- Python compileall for backend app, Alembic, and tests: PASS
- Pydantic/schema smoke for Organization Admin and School Admin designations: PASS
- Frontend native regression suite: 8/8 PASS
- TypeScript parser/transpile diagnostics on changed TS/TSX files: PASS
- Class & Section bulk-import assets carried forward unchanged from DEV.12

Environment-gated checks
------------------------
- PostgreSQL-backed pytest: NOT RUN in packaging environment because asyncpg/python-jose/passlib are not installed here. Run in the project backend environment after dependencies and test PostgreSQL are available.
- Full frontend production build: NOT RUN in packaging environment because node_modules is intentionally excluded and the package cache is incomplete. Run `npm ci` then `npm run build` in the target development environment.

Required local upgrade
----------------------
1. Extract V1.1.DEV.13.
2. Activate backend environment and install requirements.
3. Run: alembic upgrade head
4. Verify: alembic current -> 025
5. Restart backend/frontend.
6. Smoke test: Platform Owner mixed-case username login.
7. Smoke test: first-login required password change -> sign out -> login using new password.
8. Smoke test: existing Organization/School Admin profile edit and sidebar identity display.

QA status
---------
Development snapshot only; not promoted to QA or production.

In-place DEV.13 Student Import preview fix
------------------------------------------
- Student bulk-import preview now shows the selected Academic Year, Class, and Section on every valid student row before confirmation.
- Class/Section values come from validated ERP master selections; no free-text class assignment was introduced.
- Package version remains V1.1.DEV.13.
- Alembic remains 025; no schema migration required.

In-place Student enrolment/import alignment validation:
- 20-field Student template header mapping: PASS
- Student enrolment mandatory-field schema smoke check: PASS
- Backend Python compileall: PASS
- Changed TypeScript/TSX syntax transpile: PASS
- Static Student template workbook header validation: PASS
- Version unchanged: V1.1.DEV.13
- Alembic unchanged: 025
- PostgreSQL integration pytest: environment gate (asyncpg unavailable in packaging runner)
- Full frontend dependency-backed typecheck/build: environment gate (package does not ship node_modules)

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.14.txt`

School ERP V1.1.DEV.14 — Role-Based Shell / Dashboard Validation

PASS: backend Python source compilation
PASS: frontend regression tests 9/9
PASS: changed TS/TSX syntax transpile validation
PASS: permission-aware navigation regression retained
PASS: Student bulk import layout regression retained
PASS: no Alembic migration added; head remains 025

Environment gates before QA promotion:
- run npm ci && npm run build in the target development environment
- run PostgreSQL-backed pytest/integration suite
- browser QA each account type: Platform Owner, Organization Admin, School Admin, Accountant, Receptionist, Teacher, Parent/Student
- verify school logo URLs and responsive layout with real configured data

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.15.txt`

School ERP V1.1.DEV.15 — Platform Owner System Settings Validation

Version: V1.1.DEV.15
Alembic head: 025
Environment: DEV
QA promotion: NO

Validated in packaging environment:
- Python backend compileall: PASS
- Frontend node regression tests: 10/10 PASS
- Platform module catalog count: 28 PASS
- System Settings UI/API static consistency: PASS
- Development reset production-hard-block logic: source validation PASS
- ZIP integrity and clean-package scan: PASS

Target-environment gates still required:
- npm dependency-backed typecheck/build
- PostgreSQL/Redis integration tests
- Development Data Reset against a disposable lower-environment database
- Safety backup restore drill

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.16.txt`

SCHOOL ERP RELEASE VALIDATION
=============================
Release: V1.1.DEV.16
Date: 2026-09-06
Alembic head: 026
Migration: 025 -> 026 platform payments, organization subscriptions and school activation

PASS  Python source compilation
PASS  SQLAlchemy mapper configuration
PASS  FastAPI OpenAPI generation (122 paths)
PASS  Required Payments and Subscriptions routes (0 missing)
PASS  Focused backend unit tests (16 passed)
PASS  Frontend role/workflow tests (17 passed)
PASS  Frontend TypeScript/Vite production build
PASS  Alembic heads (026 head)
PASS  Alembic offline PostgreSQL SQL generation (195 lines)

BLOCKED  Full database-backed backend suite
Reason: PostgreSQL service hostname "db" is not available in this workspace.
Observed: 4 non-database tests passed before fixture setup stopped at the
database connection error. This is an environment blocker, not a test assertion
failure.

NON-BLOCKING  Vite reports a generated JavaScript chunk slightly above 500 kB.

Required deployment order:
1. Back up the target database.
2. Run: alembic upgrade 026
3. Run the application bootstrap so the new permissions are registered.
4. Deploy backend and frontend from the same V1.1.DEV.16 package.
5. Verify Platform Owner Payments and Subscriptions access.
6. Verify Organization Admin ERP Activation access.
7. Verify School Admin has no payment, subscription, or activation access.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.17.txt`

School ERP V1.1.DEV.17 — Development Validation
================================================
Alembic head: 027

PASS Python source compilation.
PASS DEV.16 package used as implementation baseline and preserved migration lineage 026 -> 027.
PASS Backend commercial-rule code review: mandatory Organization plan, yearly fixed plans, Customized monthly/yearly, PAYG per-School minimum basis, production catalog lock.
PASS Trial backend controls added for one School, 50 Students, 10 Teachers, and Student/Teacher edit denial.
PASS Subscription UI reorganized into Plans / Subscriptions / Entitlements / Keys / Renewals / Reminders.

BLOCKED focused pytest execution in this workspace: asyncpg is not installed in the runner Python environment.
BLOCKED frontend typecheck/build validation: npm dependency install exceeded the available execution window in this runner.

IMPORTANT: Student, Teacher, Fee and Reports are still under active product development. DEV.17 establishes the subscription/trial policy layer; remaining detailed Fee/Reports trial capability enforcement must be extended as those module workflows are finalized.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.18.txt`

School ERP V1.1.DEV.18 — QA Correction Validation
=================================================
Alembic head: 027 (unchanged; no migration)

Corrected from user DEV.17 test run:
- 1 stale Trial/paid-plan policy assertion updated to finalized DEV.17+ requirements.
- 31 database setup errors traced to tests/conftest.py fallback hostname `db`; direct-host fallback changed to 127.0.0.1.

Validation in packaging runner:
- PASS Python source compilation.
- PASS static verification of corrected test policy and local DB fallback.
- BLOCKED database-backed pytest execution in packaging runner because asyncpg is not installed in this runner. User's local environment has asyncpg and PostgreSQL and is the authoritative DB-backed rerun environment.

Expected local action:
- Ensure DATABASE_URL points to the local schoolerp_test database with valid credentials.
- Run: pytest -q
- QA target: 0 failed, 0 errors.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.19.txt`

School ERP V1.1.DEV.19 — QA Fix Candidate
Alembic head: 027
FIX: Organization business code remains unique and is no longer overwritten by subscription plan code.
FIX: Subscriptions UI restores Core ERP and Trial restriction/no-key/no-export guidance.
FIX: DEV.19 frontend/release metadata synchronized.
PASS: Python source compilation.
PENDING: Full PostgreSQL-backed pytest rerun in local QA environment.
PASS: Frontend regression tests 17/17.
BLOCKED IN PACKAGING RUNNER: Frontend production build dependencies are incomplete in packaged node_modules; local QA must rerun npm install/npm run build. Previous user QA build passed before this patch.

---

## Imported history/source: `RELEASE_VALIDATION_V1.1.DEV.15_CLEANUP.txt`

School ERP V1.1.dev15 - Cleanup Validation
Date: 2026-09-06

PASS  Frontend TypeScript type-check
PASS  Frontend noUnusedLocals/noUnusedParameters check
PASS  Frontend tests: 14/14
PASS  Frontend production/PWA build
PASS  Backend database-independent tests: 15/15
PASS  Python source compilation
PASS  Ruff lint + format: 132 files
PASS  NPM audit: 0 known vulnerabilities
PASS  Python dependency audit: 0 known vulnerabilities
PASS  Bandit: 0 medium/high findings; 8 reviewed low informational findings
PASS  GitHub workflow YAML validation
PASS  Runtime secrets/credentials moved to required environment configuration
PASS  PyJWT HS256 token smoke test
PASS  Platform Owner user-hierarchy fix: lint, type-check, build, static security
PASS  Platform Owner organization-first navigation, profile and subscription UI regression
PASS  README and release/QA documentation synchronized
ADDED Database regression: Platform Owner sees governing Organization Admin;
      non-Platform actors cannot enable the expanded hierarchy view
BLOCK Full backend database suite: PostgreSQL hostname `db` unavailable
      Observed result: 21 passed, 31 setup connection errors

Cleanup focus:
- shared form/status UI primitives
- centralized navigation and route access rules
- fixed partial Class/Section bulk permission exposure
- restricted school directory to platform/organization scope
- no unproven dead route, CSS, or compatibility endpoint removed
- client school name and bootstrap credentials are not runtime source defaults
- vulnerable fast-uri, python-dotenv, pytest and ecdsa dependency paths remediated
- Platform Owner school Users list includes its Organization Admin without exposing
  that expanded view to lower roles
- Organization → School is the active product hierarchy; a hidden one-per-School
  compatibility scope remains until academic/finance foreign-key flattening

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.10-dev.2.txt`

School ERP V1.1.10-dev.2 — Development Snapshot Validation

PASS TypeScript/TSX source syntax: 36 files, 0 parse errors.
PASS Python source syntax: 104 files, 0 parse errors.
PASS frontend package.json version: 1.1.10-dev.2.
PASS frontend package-lock.json root version: 1.1.10-dev.2.
PASS backend FastAPI version: 1.1.10-dev.2.
PASS /api/v1/system/version release: V1.1.10-dev.2.
PASS /api/v1/system/version migration head: 019.
PASS Alembic chain has a single head: 019.
PASS AKSHARA SCHOOL branding defaults present.
PASS configured provider technology-partner branding present.
PASS No new database migration required for this snapshot.

NOT RUN Full frontend dependency install/build in packaging environment because internet access is unavailable and the npm cache does not contain all locked packages (zustand 5.0.14 missing). Run `npm ci` followed by `npm run build` on the Windows development workstation before QA promotion.

Status: DEVELOPMENT ONLY — not QA or production approved.

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.10-dev.4.txt`

School ERP V1.1.10-dev.4 — Development Snapshot Validation
Date: 2026-09-01
Environment: packaging workspace (not the user's Windows/PostgreSQL development runtime)

PASS 117 backend Python source/test/migration files parsed with 0 syntax errors.
PASS Python compileall completed successfully.
PASS Alembic migration chain has 20 revisions and a single head: 020.
PASS frontend package.json version: 1.1.10-dev.4.
PASS frontend package-lock.json root version: 1.1.10-dev.4.
PASS backend OpenAPI/application version metadata: 1.1.10-dev.4.
PASS /api/v1/system/version metadata: V1.1.10-dev.4 / migration head 020.
PASS current package excludes runtime .env files, private keys, database dumps, node_modules, virtual environments and cache directories.

NOT VERIFIED HERE PostgreSQL/Redis integration pytest: packaging Python environment does not contain asyncpg.
NOT VERIFIED HERE frontend production build: available node_modules cache is incomplete and TypeScript reports missing installed type-definition packages. Run npm ci before npm run build in the Windows development environment.

Release classification: DEVELOPMENT SNAPSHOT ONLY.
QA status: NOT PROMOTED TO QA.
Production status: NOT RELEASED.

Required Windows validation before QA promotion:
1. backend: pip install -r requirements.txt
2. backend: alembic upgrade head
3. backend: alembic current -> 020 (head)
4. backend: pytest tests/ -v
5. frontend: npm ci
6. frontend: npm run build
7. run security/dependency audits and Phase 1 manual regression.

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.10-dev.5.txt`

School ERP V1.1.10-dev.5 — Development Snapshot Validation

PASS login branding root-cause fix: Tailwind primary.950 is now defined.
PASS login branding panel uses explicit high-contrast dark gradient.
PASS AKSHARA SCHOOL and configured provider branding remains configurable.
PASS account-type login behavior unchanged.
PASS frontend package version metadata updated to 1.1.10-dev.5.
PASS backend application/system version metadata updated to 1.1.10-dev.5.
PASS Alembic head remains 020; no schema migration is required for this UI-only fix.
PASS TypeScript/TSX syntax parse validation.
PASS Python source compilation.
NOTE Full npm production build must be run in the Windows development environment before QA promotion.

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.10-dev.6.txt`

School ERP V1.1.10-dev.6 — Development Snapshot Validation

PASS School profile update no longer accesses lazy School.udise_codes in AsyncSession request handler.
PASS Explicit async SELECT is used for before/after UDISE audit values.
PASS Regression test added for School profile update with existing UDISE.
PASS Login page has one configurable Powered by line; duplicate Technology Partner footer removed.
PASS Provider name is blank by default and can be configured later.
PASS TypeScript/TSX syntax parse: 36 files, 0 syntax errors.
PASS Python syntax/compile validation: 117 backend/test Python files, 0 syntax errors.
PASS Backend/frontend version metadata updated to V1.1.10-dev.6.
PASS No database migration required; current Alembic head remains 020.
NOTE Live PostgreSQL pytest was not executed in the packaging environment because asyncpg is not installed there. Run the regression suite in the Windows development environment before QA promotion.

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.DEV.7.txt`

School ERP V1.1.DEV.7 — Development Snapshot Validation
Date: 2026-09-01

PASS Python static compile: backend/app + backend/alembic (119 Python files in backend tree).
PASS Alembic static graph: single head 021; 021 revises 020.
PASS Branding source scan: no Powered by / Technology Partner / Srivalli provider attribution rendered in current frontend source.
PASS Package hygiene source scan: no real .env, database dump, private-key file, node_modules, dist, .vite or __pycache__ retained for packaging.
PASS Version metadata/source updated to V1.1.DEV.7.

PENDING Frontend dependency-backed production build. npm ci could not complete within the packaging runtime; npm run build therefore could not resolve installed type dependencies. Re-run on Windows DEV with npm ci && npm run build.
PENDING Backend pytest/integration suite. Packaging runtime lacks asyncpg; run against the Windows PostgreSQL/Redis DEV environment.
PENDING Live Alembic 020 -> 021 migration on the Windows DEV PostgreSQL database.
PENDING Fresh-database alembic upgrade head + bootstrap + end-to-end smoke test.
PENDING Backup -> restore drill and optional off-site backup validation.
PENDING Full RBAC/tenant-isolation/security regression before QA promotion.

Promotion status: DEVELOPMENT ONLY. Do not promote to V1.1.QA.1 until all PENDING gates pass.

---

## Imported history/source: `docs/history/RELEASE_VALIDATION_V1.1.DEV.8.txt`

School ERP V1.1.DEV.8 — Development Snapshot Validation
Date: 2026-09-01

IMPLEMENTED
- Organization Admin authentication accepts either username or registered email under the ORGANIZATION_ADMIN account type.
- Username/email matching is case-insensitive; password verification remains case-sensitive.
- Migration 022 normalizes Organization Admin emails and enforces a case-insensitive partial unique index.
- Organization API/tile exposes both login identifiers only to Super Admin and the owning Organization Admin level; lower roles receive no identifier values.
- Local Vite development uses same-origin /api/v1 proxying.
- Refresh handling redirects to login only after confirmed 401/403 rejection; network and backend 5xx failures preserve browser state.
- Users module displays the backend error and provides Retry instead of forcing logout.

VALIDATION PASSED IN THIS WORKSPACE
- Python AST parse: 121 backend/application/migration/test files passed.
- Python compileall: backend app, Alembic migrations and tests passed.
- Alembic static graph: 22 migrations, one head (022), no missing parent revision.
- Frontend package.json and package-lock.json parsed as valid JSON and both report 1.1.0-dev.8.
- Node type-stripping syntax checks passed for changed non-JSX TypeScript: vite.config.ts, services/api.ts and authStore.ts.
- Static contract scan confirmed dual username/email lookup, 401/403-only session clearing and relative /api/v1 development configuration.
- Package hygiene scan found no real .env, private key, database/dump, node_modules, dist, .vite or __pycache__ content.
- Version metadata is synchronized as V1.1.DEV.8.

REGRESSION TESTS ADDED
- backend/tests/test_organization_admin_login.py
  - username login (case-insensitive)
  - email login (case-insensitive)
  - Organization API/tile username and email fields
  - duplicate Organization Admin email rejection

ENVIRONMENT-LIMITED / REQUIRED ON WINDOWS DEV
- Backend pytest could not execute here because this runtime does not contain pytest/asyncpg or PostgreSQL/Redis services.
- Frontend npm ci/build/lint could not execute because dependency installation is unavailable in this packaging runtime.
- Apply and verify the live PostgreSQL migration 021 -> 022 before browser testing.

WINDOWS DEV RELEASE GATE
1. backend: alembic upgrade head
2. backend: python -m app.scripts.bootstrap
3. backend: pytest -q
4. frontend: npm ci
5. frontend: npm run build
6. frontend: npm run lint
7. Browser: login as Organization Admin once with username and once with email.
8. Browser: open Users, stop the backend, retry/open Users and confirm the app shows a retryable error without logout; restart the backend and confirm Retry succeeds.
9. Browser: expire/reject a session and confirm a genuine refresh 401/403 still redirects to login.

PROMOTION STATUS
DEVELOPMENT ONLY. Do not promote to V1.1.QA.1 until every Windows DEV release gate passes.

---

## Imported history/source: `docs/history/LEGACY_RELEASE_VALIDATION_V1.2.9.txt`

School ERP Phase1-Core-Security-V1.2.9 — Rev3
Alembic head: 018

Validation summary in packaging workspace:
PASS Python AST parse: 103 files / 0 syntax errors
PASS Python compileall
PASS SQLAlchemy ORM mapper configuration
PASS Alembic chain: 18 revisions / one head 018 / no missing parents
PASS TypeScript/TSX syntax parse: 35 source files / 0 syntax errors
PASS package.json + package-lock.json version remains 1.2.9
PASS BUG-1 source ordering fix remains present
PASS BUG-2 school_config module catalog fix remains present
PASS Organization disable cascade source assertion
PASS School-enable parent-Organization guard source assertion
PASS Disabled-School soft-delete route + migration source assertion
PASS Notifications planning document included; runtime module not enabled
LIMITED full pytest: packaging environment missing asyncpg/PostgreSQL
LIMITED npm build/lint/audit: frontend dependencies are not installed in packaging environment

Local/CI release gate after migration 018:
- alembic upgrade head
- pytest tests/ -v
- npm ci && npm run build
- dependency audits

## DEV.21 QA-01 validation — 2026-09-12
- PASS: Python source/test compilation after School-scope authorization correction.
- PASS: frontend unit suite `19/19`.
- LIMITED: backend focused pytest cannot run in this packaging environment because `asyncpg` is not installed.
- LIMITED: frontend typecheck cannot run from the clean package because dependency folders are intentionally excluded; missing React/Axios/Zustand type packages are an environment prerequisite, not a source regression result.
- Local release gate: run `pytest -q`, `npm run typecheck`, `npm run build`, then Teacher login/browser regression.

## DEV.21 Schools correction validation
- PASS: frontend static tests 25/25.
- PASS: backend app Python compileall.
- RETEST REQUIRED locally: install frontend dependencies then run `npm run typecheck`, production build and Playwright.
- Browser checks: School List admin + activation columns; School Capacity inline limit increase; Module Catalogue plan states and synchronization; Academic Year draft -> activate/rollover -> previous year closed/history preserved.

### School Capacity trial exclusion validation
- Frontend regression tests: **26/26 PASS** (`npm test`).
- Added regression coverage confirming Trial-plan Schools do not consume School Capacity and School List renders the assigned Plan.
- Version remains V1.1.DEV.21; Alembic remains 030.


## School Capacity / Trial Conversion Validation
- Targeted frontend regression tests: **16/16 passed** across School corrections, Platform Owner experience, Payments/Subscriptions, and renewal policy suites.
- Backend `compileall`: **PASS**.
- Full frontend test command is environment-blocked in the clean package because one navigation test imports TypeScript directly without the project test loader/dependencies; this does not replace the required local full-suite run.
- No Alembic migration added; head remains **030**.

## Organization + Schools gap closure validation — 2026-09-12
- Backend compile validation: PASS (`python -m compileall backend/app`).
- Frontend source regressions excluding loader-dependent navigation test: 18/18 PASS.
- Focused Schools module corrections: 9/9 PASS.
- Backend focused pytest: BLOCKED because the clean packaging runtime lacks `asyncpg`; this is not recorded as a source-test failure.
- No Alembic migration added; head remains 030.


## 2026-09-12 — DEV.21 Gap Closure Validation
- Source compile: PASS.
- Alembic head discovery: PASS (`031`).
- Frontend regression tests: 35 passed / 0 failed.
- Backend pytest execution: BLOCKED (`ModuleNotFoundError: asyncpg`) in packaging environment; no claim of backend runtime pass is made.
- Required local/CI retest: migrate a copy of PostgreSQL data to 031, verify zero orphan Schools preflight, run simultaneous create/restore capacity probes, activation payment/key/terms E2E, full pytest, TypeScript build, npm audit and Playwright.


## DEV.21 TypeScript compatibility correction
- Fixed Dashboard quick-action icon alias (`SchoolIcon`) so the imported `School` domain type is not used as a runtime value.
- Replaced `String.replaceAll()` with ES-compatible `replace(/_/g, " ")` in Module Catalogue and Schools views, preserving the current TypeScript target.
- No version bump and no database migration.

## V1.1.24.01 CI blocker correction — 2026-09-15
- GitHub Actions CI #55 blockers reviewed against the packaged source.
- Fixed Docker Compose validation input by adding documented local PostgreSQL variables to `.env.example`.
- Removed the confirmed Ruff unused-code findings reported by CI.
- CI now keeps substantive Ruff lint findings blocking while legacy formatting-only debt is reported separately as a non-blocking step.
- Python source/test compile validation: PASS in packaging workspace.
- GitHub green status remains RETEST REQUIRED after the patched source is pushed; no green-run claim is made here.

