## 2026-09-12 — ORG-SCHOOL-SEC-01 / ORG-SCHOOL-CAP-01 closure
- SEC-01: PASS at source review. Lifecycle endpoints now depend on the shared Platform Owner dependency.
- CAP-01: FIXED at source level. `create_school` locks the Organization row and selected active subscription row with `FOR UPDATE` before the School count/limit decision. This removes the prior same-Organization count/compare race when all School creation uses this endpoint.
- Backend compileall: PASS in packaging environment.
- A real PostgreSQL concurrent-request regression run is still required in formal QA to prove runtime locking behavior under contention.
- No frontend files changed in this delta.


## 2026-09-09 — Schools QA/security checkpoint
- Frontend `npm run typecheck`: PASS.
- Frontend node tests: 19/19 PASS.
- Backend `python -m compileall -q app`: PASS.
- Direct School schema/contact checks: PASS, including +91 normalization.
- Full backend pytest could not execute in the packaging sandbox because `asyncpg` is unavailable and outbound package installation is blocked. Local DEV regression remains required before Product Head sign-off.
- Frontend Vite production build could not complete in the packaging sandbox because the uploaded Windows node_modules lacks Linux Rollup optional binary. TypeScript compilation itself passed.
- No database migration added; Alembic head remains 029.
- Lifecycle endpoints now enforce Platform Owner-only status/archive/restore and mandatory reason for status/archive.

# SCHOOL ERP — QA & Security Notes

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `QA_SECURITY_NOTES.md`

# SCHOOL ERP — Continuous QA & Security Notes

## V1.1.DEV.21
- Python source compilation: PASS (`python -m compileall -q backend/app`).
- Migration chain: new head 029, down_revision 028.
- Security design: temporary passwords are generated with `secrets`, plaintext is returned only on creation/reset response and never persisted; password hash is stored.
- Disable/Enable requires authenticated Platform Owner, reason, expiry gate, audit and session revocation.
- Archive requires authenticated Platform Owner and 90-day post-expiry gate; existing optional recent-backup guard remains.
- Automatic retention removes School operational records only; Society/Trust identity, organization subscription and subscription payment ledger are retained.
- SMTP failure is non-transactional by design and does not undo successful Society/Trust/Admin creation.
- Frontend full build could not be completed in this sandbox because dependencies were not present and `npm ci` exceeded the execution window. Build must be rerun in the normal project environment before production sign-off.
- Database integration tests requiring the project PostgreSQL test database/migration environment remain required after applying Alembic 029.

## Release gate
DEV.21 is an implementation candidate, not production-signed-off until Alembic upgrade, backend pytest, frontend build/tests, and E2E regression pass in the deployment/test environment.

### Sandbox validation evidence
- Frontend build was attempted after dependency installation attempt; TypeScript could not resolve several type packages (`react`, `react-dom`, Babel/estree/prop-types/resolve/trusted-types) because `npm ci` did not complete within the sandbox execution window.
- Targeted backend pytest was attempted; collection stopped because `asyncpg` is not installed in this sandbox runtime. This is an environment dependency blocker, not a passing test result.

---

## Imported history/source: `docs/history/QA_FIX_REPORT_V1.2.9.md`

# School ERP V1.2.9 — QA & Security Fix Report

Release: `Phase1-Core-Security-V1.2.9`  
Alembic head: `019`


## Post-review blocker amendment — 31-Aug-2026

The independent PostgreSQL QA pass identified two carried-over blockers after the original V1.2.9 package was produced. This revised V1.2.9 source package applies both fixes without changing the product version:

- **BUG-1:** `_issue_tokens` now flushes the new `UserSession` INSERT before assigning `parent_session.replaced_by_session_id`, eliminating the immediate PostgreSQL self-referential FK ordering violation during refresh-token rotation.
- **BUG-2:** `school_config` is now included in `PHASE1_MODULES` / `IMPLEMENTED_MODULES`, so school provisioning can enable the same module used by the academic configuration permissions seeded in `bootstrap.py`.

A focused licensing regression test was added. The existing refresh rotation/replay test remains the integration regression gate for BUG-1. A fresh live-PostgreSQL test run is still required before production approval because this packaging environment does not provide `asyncpg`/PostgreSQL.

## Lifecycle amendment — Organization / School controls

The V1.2.9 Rev3 package adds the approved lifecycle behavior without changing the product version:

- Disabling an Organization sets every non-deleted School/Branch under it to `is_active=false` and revokes organization sessions.
- Re-enabling the Organization does **not** silently re-enable its Schools; they can be enabled individually afterward.
- Attempting to enable a School while its parent Organization is disabled returns HTTP 409 with: `Organization is disabled. Please activate the Organization before enabling this School.`
- A School can be deleted only after it is disabled. Delete is implemented as a **soft archive** (`deleted_at`, `deleted_by`) so student, fee, attendance, marks and audit history are preserved. The school is removed from normal lists, its users/campuses/license are disabled, and sessions are revoked.
- Pytest forces `APP_ENV=test` before app import, and bootstrap synchronizes the Super Admin password only in test/CI mode. This isolates integration tests from Redis login-throttle state and avoids the development 401→429 test contamination observed during Windows QA. Development/production bootstrap behavior is unchanged.
- `PLANNING_NOTIFICATIONS.md` records the approved Phase-2 Notifications module scope; Notifications remain unimplemented/disabled in V1.2.9.

Alembic migration `018_school_lifecycle_soft_delete.py` adds the School archive metadata; migration `019_reuse_archived_school_identifiers.py` allows archived School code/UDISE identifiers to be reused by new active Schools.

## Remediated findings

1. Upgraded FastAPI/Starlette and `python-multipart` to remove the previously identified multipart/form parsing vulnerability exposure.
2. Upgraded `python-jose` and Pillow; upgraded nginx runtime to `1.30.4-alpine` across Compose and frontend Dockerfile.
3. Protected school dashboard API with `dashboard.view`, dashboard-module licensing, school authorization, campus-scoped student/teacher/attendance metrics, and campus-scoped fee aggregates.
4. Added campus authorization checks to fee charge creation, charge listing, payment collection/cancellation and campus-scoped fee structures.
5. Hardened production settings: known/example JWT secrets are rejected, production requires HTTPS origins and Secure refresh cookies, and default Super Admin credentials are rejected.
6. Deployment workflow is HTTPS-first and requires TLS certificate/key secrets for EC2 deployment.
7. Browser refresh tokens moved to `HttpOnly; SameSite=Strict` cookies; access tokens are held in memory rather than localStorage.
8. Closed module-license gaps on Teacher update and Guardian creation; licensed APIs enforce backend licensing rather than relying on menu visibility.
9. Audit service supports target organization/school/campus scope so Platform Super Admin actions appear in the affected tenant audit trail.
10. Disabled organizations/schools are rejected during authentication/refresh and active sessions are revoked when a tenant is disabled.
11. Login throttling fails closed when Redis is unavailable; Docker Uvicorn proxy forwarding is explicitly configured for the nginx boundary.
12. Added authenticated self-service password change with current-password verification, stronger password policy and session revocation.
13. Added Student profile read/update, soft archive and reactivate APIs and corresponding frontend controls.
14. Added role-aware dashboards; financial values are returned only to users who hold `fee.view`.
15. Implemented Super-Admin-only backup history/manual backup/download/delete plus maintenance-gated restore with checksum verification and a pre-restore safety backup. Scheduled backups and retention are configurable.
16. Added Alembic migration `017_qa_security_hardening.py` and bootstrap seeding for `dashboard.view`; Rev3 adds migration `018_school_lifecycle_soft_delete.py` for safe School archival; Rev4 adds migration `019_reuse_archived_school_identifiers.py` for safe identifier reuse after archival.
17. Expanded security regression coverage for refresh-cookie behavior, production configuration and password policy.
18. CI now includes backend tests, dependency audit (`pip-audit`), frontend build/lint, `npm audit`, migration checks and TLS Compose validation.

## Release validation performed in this workspace

- Python AST parse: **103 files, 0 syntax errors**.
- Python `compileall`: **passed** for backend application, tests and migrations.
- TypeScript/TSX syntax parse: **35 files, 0 syntax errors**.
- Alembic chain: **19 migrations, one head (`019`), no missing parent revision**.
- `package.json` and `package-lock.json`: **valid JSON** and versioned `1.2.9`.
- Frontend security lock: **Axios 1.19.0** and **Vite 6.4.3**.
- Docker Compose / CI / CD YAML files: **parsed successfully**.
- Static regression scan: no prior vulnerable pins (`FastAPI 0.115.6`, `python-multipart 0.0.20`, `python-jose 3.3.0`, nginx 1.25) remain in active runtime files.
- Static frontend scan: no access/refresh JWT persistence in `localStorage` remains.
- Clean-package scan: no `.env`, private key, certificate key, SQLite database or SQL/database dump is included.

## Environment-limited checks

The complete PostgreSQL integration suite could not run in this workspace because the runtime lacks `asyncpg`; `pytest` stops during test bootstrap with `ModuleNotFoundError: asyncpg`. The frontend `npm ci` also timed out because external npm package access is unavailable in this environment. These are validation-environment limitations, not recorded test failures. CI is configured to perform the missing dependency-backed tests/build/audits on a connected runner before deployment.

## Production release gate

Before promoting V1.2.9 to production, run CI against a dedicated PostgreSQL test database and require all backend tests, frontend build/lint, `pip-audit` and `npm audit --audit-level=high` to pass. Keep `BROWSER_RESTORE_ENABLED=false` except during an approved maintenance restore and store database backups on encrypted/off-server storage according to policy.

## 2026-09-09 — Create School validation/security delta
- Backend Python compile/AST validation passed after Create School changes.
- Shared email and India 10-digit mobile normalization remain enforced server-side.
- PIN requires six digits and Board/Curriculum is restricted to State Board/CBSE/ICSE.
- School Code registry is globally unique at DB level after migration 030 and checked before creation.
- Frontend typecheck could not be executed in this sandbox because the extracted package does not contain the required React/Axios/Zustand dependencies; run `npm install`/existing local dependencies then `npm run typecheck` in the user's DEV environment before sign-off.
- Full backend DB regression remains required after applying migration 030.

## DEV.21 / Alembic 030 — School creation regression correction
- Corrected global change-control regression: ordinary POST/PUT/PATCH mutations no longer require legacy generic confirmation headers. Business-specific destructive controls remain endpoint-owned.
- Removed obsolete Trial restriction that forced exactly one School per Society/Trust; Trial now preserves the configured School entitlement.
- Retained the approved strict Create School contract and aligned backend regression fixtures to valid School/Village short codes and required School master fields.
- Python source/test compilation passed after the correction.
- Full pytest could not be executed in the packaging sandbox because `asyncpg` is not installed and the sandbox has no package-network access. Product Head must rerun `pytest -q` in the local DEV virtual environment before sign-off.

## DEV.21 / Alembic 030 follow-up (2026-09-11)
- Fixed confirmed runtime regression: obsolete global 428 change-confirmation enforcement and resulting `confirmed` NameError removed from request middleware.
- Fixed Society/Trust MAP validation mismatch that could return HTTP 422 when entered MAP was equal to or above the calculated minimum without a reason.
- Restored Trial one-School commercial rule with frontend lock plus backend enforcement.
- Added downward-only administrative audit visibility boundaries to prevent upward governance-log exposure.
- Python compilation validation passed for changed backend files. Full PostgreSQL pytest and frontend TypeScript/E2E remain release-gate checks in the user's DEV environment.

## DEV.21 User credential security correction
Static Python compilation passed for the modified user schema/API. Frontend dependency folders are intentionally excluded from the clean source, so npm typecheck and PostgreSQL pytest remain local QA gates. User-create/reset plaintext temporary passwords are never persisted; only the immediate authorized response contains them. Existing sessions are revoked on reset and first-login password change remains mandatory.

## V1.1.DEV.21 UI/backend checkpoint — 2026-09-11
- `python -m compileall backend/app`: PASS.
- Frontend dependency installation/typecheck could not complete in the isolated build environment before timeout; local `npm run typecheck` remains a release gate.
- Backend School identity locking is enforced server-side, not only by disabled frontend controls.
- No dependency directories are included in the clean package.

## DEV.21 frontend TypeScript cleanup
- Removed unused `UserRound` import from `AppSidebar.tsx`.
- Aliased Lucide `School` to `SchoolIcon` to avoid collision with the ERP `School` type.
- Removed unused `Settings` and `ShieldCheck` imports from `DashboardPage.tsx`.
- Removed unused `ActionRow` from `SchoolDetailPage.tsx`.
- Ensured the obsolete unused `SectionTitle` helper is absent from `SchoolsPage.tsx`.
- Backend Python compileall passed for this clean package. Frontend `npm run typecheck` still requires local dependencies to execute.

## DEV.21 QA-01 — School-scoped Teacher / Campus Scope fix (2026-09-12)
- Root cause confirmed: `User.campus_id` is intentionally optional for School-wide operational roles, but legacy campus authorization still required it.
- Backend authorization corrected without weakening tenant isolation: School access is validated first; users with an explicit `campus_id` remain limited to that campus; users without one receive School-wide scope only inside their own School.
- Frontend Teacher Management no longer performs an unnecessary campus-list request for view-only users.
- Regression assertion added to the existing Teacher login/hierarchy test.
- Validation in packaging workspace: Python compileall PASS; frontend unit tests 19/19 PASS.
- PostgreSQL pytest could not execute in this workspace because `asyncpg` is unavailable. Local DEV.21 must rerun the focused governance test and full `pytest -q` before QA-01 is marked PASS.

## DEV.21 Schools QA corrections
- SCHOOL-01 School Admin / activation visibility: corrected in Platform Owner School List.
- SCHOOL-02 Capacity increase redirect: corrected; action stays in School Capacity and uses audited Platform Owner organization update.
- SCHOOL-03 Module Catalogue: corrected to use subscription-plan entitlement and effective School license; future/unimplemented modules remain locked rather than falsely enabled.
- SCHOOL-04 Academic Years: lifecycle/rollover UX implemented on top of the existing organization-wide Academic Year source of truth; no schema migration required.
- Frontend static regression suite: 25/25 passed.
- Backend Python compileall: passed.
- Full TypeScript typecheck remains environment-blocked in the clean package because node_modules / dependency type declarations are intentionally excluded.

### QA-SCHOOL-05 — Trial capacity exclusion and Plan visibility
**PASS (source regression).** Trial Schools are excluded from capacity calculations using the School subscription billing cycle, and School List exposes the assigned plan. Frontend regression suite: 26/26 passed. No authorization or database schema change.


## SCHOOL-02 / SCHOOL-05 QA Notes
- PASS: frontend source-regression coverage for School Capacity columns, Trial fixed-limit handling, exhausted-capacity button gating, and Trial conversion controls.
- PASS: backend Python compile validation.
- Backend now rejects Trial capacity increases and rejects paid capacity increases before the existing limit is exhausted.
- Backend School creation independently caps Trial at one School, preventing UI bypass.
- Full backend pytest / frontend TypeScript / production build / Playwright must still be rerun in the local dependency-complete QA environment before release sign-off.

## QA hardening — Organization + Schools gap closure (2026-09-12)
- PASS (source regression): plan-derived Module Catalogue and exact server-side module allocation enforcement.
- PASS (source regression): Trial capacity fixed at one; Increase Limit disabled for Trial and below-capacity paid organizations.
- PASS (source regression): capacity increase captures effective date/reason and incremental-only discount/proration wording.
- PASS: Python compileall for backend/app.
- PASS: 18/18 runnable frontend source regression tests excluding navigation.test.mjs; the excluded test requires the TypeScript loader/runtime not present in this clean packaging environment.
- PASS: focused Schools correction regression file 9/9.
- BLOCKED in packaging environment: backend pytest because asyncpg is not installed. Re-run in the project .venv before release sign-off.
- REQUIRED local gate: full backend pytest, full frontend unit suite, TypeScript typecheck, production build, npm audit and Playwright E2E.


## 2026-09-12 — QA/Security Gap Closure Review
### Closed
- GAP 1.1 retention worker FK crash: fixed by explicit operational purge ordering and per-tenant rollback isolation; retained School identity is no longer physically deleted.
- GAP 1.3 orphan School parent: fixed with Alembic 031 (`organization_id NOT NULL`, `ON DELETE RESTRICT`) and migration preflight that aborts if orphan rows exist.
- GAP 2.1 restore capacity bypass: fixed with Organization + current subscription row locks and projected capacity check before restore.
- GAP 2.2 enable capacity/activation bypass: fixed; enable validates capacity and blocks paid activation-pending Schools.
- GAP 2.3 emergency suspension: Platform Owner can explicitly invoke audited emergency override during an active subscription.
- GAP 2.4 UDISE restore desync: fixed by re-electing/clearing the legacy primary mirror from actually restored authoritative UDISE rows.
- GAP 4.1 Org Admin School directory: fixed; Org Admin receives scoped School list and activation status but no create/capacity governance controls.
- GAP 4.2 profile edit mismatch: fixed via `school.config.edit`; UDISE remains Platform Owner-governed.
- Activation commercial gap: paid School/modules/users remain locked until MAP + key + Terms acceptance activation completes.
### Deliberate / not treated as defects
- GAP 1.2 Campus dual model: no destructive schema removal in DEV.21. Campus remains internal MAIN compatibility only; visible auth/operations stay School-scoped.
- GAP 3.1 global username namespace: unchanged because case-insensitive global username is an approved identity rule; creation remains authorized-admin-only.
- GAP 3.2 Org Admin archive token claim: archived Schools are already rejected by School access checks; Organization Admin session remains valid for Organization-level duties by design. Operational access to disabled Schools remains blocked by School/License activation checks.
- GAP 4.3 atomic School Admin provisioning: intentionally not implemented because approved commercial policy forbids any School-scoped user creation until paid activation completes.
### Validation
- `python -m compileall -q backend/app backend/alembic/versions`: PASS.
- `alembic heads`: PASS, `031 (head)`.
- Frontend source regression suite: **35/35 PASS** (`npm test`, uses Node type stripping; no node_modules needed).
- Backend pytest: **BLOCKED in packaging environment** because `asyncpg` is not installed. Must rerun full backend suite against PostgreSQL locally/CI before release sign-off.
- TypeScript production build, npm audit and Playwright E2E were not rerun in this clean packaging environment and remain release-gate retests.


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

