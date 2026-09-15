# School ERP

**Current development snapshot:** V1.1.24.01  
**Phase:** 1  
**Alembic head:** 032

Multi-tenant School ERP using FastAPI, PostgreSQL, React, Vite and TypeScript.

## Release status

V1.1.24.01 is a development snapshot with the Platform Owner Calendar Planner, subscription/payment follow-up agenda, and Alembic 032 planner storage. Frontend source tests, typecheck, production build, backend planner compile, and local Alembic upgrade have passed.

- [Release notes](reports/RELEASE_NOTES.md)
- [QA & Security notes](reports/QA_SECURITY_NOTES.md)
- [Validation report](reports/VALIDATION_REPORT.md)
- [Release history](docs/RELEASE_HISTORY.md)

## Hierarchy

Platform Owner → Organization (Society/Trust) → School → scoped users and operational data.

Every physical branch/campus is represented as a **School**. Branch and Campus are
not user-facing business entities. V1.1.24.01 temporarily retains one automatically
managed internal compatibility record per School for existing academic/finance foreign
keys; it cannot be separately administered and will be flattened in a later migration.

Backend authorization is the security boundary. Frontend navigation is role/permission aware, but hiding a menu never replaces API authorization.

## Phase 1 scope

Dashboard, School Administration, Student Management, Teacher Management, Attendance, Fee Management, Marks, Reports, Users, Roles/Permissions foundation, Audit Logs, bulk imports and protected Backup/Restore.

School Configuration is merged into the School create-view-edit profile. Academic Year is owned at Organization level and projected to Schools/Campuses as required by existing module compatibility.

## V1.1.24.01 Platform Owner Calendar Planner

- Adds a Platform Owner-only Calendar Planner module in the sidebar and protected route.
- Adds manual planner tasks/reminders with Society/Trust, School and subscription links.
- Adds automatic agenda follow-ups for payment dues, trial conversion, subscription renewals and pending School activation.
- Adds Alembic 032 with `platform_planner_items` and System Settings metadata for migration head 032.

## V1.1.DEV.16 Platform Payments, Subscriptions and Activation

- One Organization-level commercial account covers the agreed School count.
- Each School has a separate entitlement, activation key and activation state.
- Payments and Subscriptions are separate Platform Owner-only modules.
- Organization Admin receives only the minimal ERP Activation screen and reminders.
- Trial access is keyless, limited, export-blocked and automatically expires after 30 days.
- Monthly/yearly renewals extend existing active School expiries without new keys.
- Alembic head is 026.

## V1.1.DEV.15 Role-Based ERP Shell & Dashboard

- Platform Owner navigation is Organization-first and uses the approved Organization → School hierarchy.
- Platform Owner has a dedicated editable My Profile page and account-security link.
- Platform Dashboard now summarizes Organizations, Schools, active/inactive Schools,
  administrative quick actions and the Core ERP + Add-ons subscription model.
- A Platform Owner-only Subscriptions overview reports School subscription status,
  expiry, user allowance and whether add-ons are present.
- Active Platform Owner screens use School and Subscription terminology; Branch/Campus
  and License remain internal compatibility identifiers only where required by existing APIs.

- Shared ERP shell redesigned around a clear header, centered School/Branch context, date/time and a user account tray containing Account Security and Logout.
- School-scoped users receive a scrolling student-birthday and system-reminder strip below the header.
- Main navigation now supports expandable permission-aware shortcuts while backend RBAC remains authoritative.
- Platform Owner receives a separate Platform Control Center.
- Organization Admin receives consolidated branch and financial/operational KPIs.
- School Admin and Accountant receive permitted financial KPIs; Receptionist and Teacher receive operational dashboards without financial exposure.
- Layout, account labels and dashboard UI primitives were refactored into reusable components.
- No database migration is required; Alembic remains 025.

## V1.1.DEV.15 cleanup and security hardening

- Reusable UI primitives and centralized navigation policies reduce duplicated
  components and permission drift.
- Runtime secrets, database connection details and bootstrap credentials must be
  supplied through environment configuration; production values are not embedded
  in source.
- Platform Owner can see the governing Organization Admin in a school-scoped Users
  list. The backend prevents lower roles from enabling that expanded hierarchy view.
- Account Security reuses the accessible shared password input for Current, New and
  Confirm New Password, with independent show/hide controls and masked defaults.
- Dependency, static-security, build and source-quality results are documented in
  the linked QA report.

## V1.1.DEV.13 Identity & Authentication

- Admin user profiles include Name + Designation while permissions continue to use account type/role.
- Sidebar identity shows Organization/School Name → Person Name → Designation.
- Organization Admin designation: Secretary and Correspondent / Chairman.
- School Admin designation: Principal / Headmaster / School Administrator.
- Platform Owner username login is case-insensitive; passwords remain case-sensitive.
- First-login password change routes directly to Account Security and signs the user out after a successful change.
- Alembic head is 025 (`users.designation`).

## V1.1.DEV.12 Class & Section bulk import

- Class and Section bulk upload is merged into one user-facing **Class & Section Import** workflow.
- The template is intentionally simple: `Class Name* | Name of Section*`; multiple sections are comma-separated, for example `Class 1 | A,B`.
- ERP generates technical Class/Section codes and Class sort order automatically.
- Preview reports new/existing Classes and Sections before confirmation; existing active records are reused and only missing records are created.
- Both original bulk permissions are required because the merged operation can create both entity types.
- Legacy separate Class/Section import APIs are retained only for compatibility and hidden from the API schema.
- No database migration is required; Alembic head remains 024.

## V1.1.DEV.11 targeted bug fixes carried forward

- Organization Admin can now open the organization-wide Academic Year manager and create/activate academic years when `academic_year.manage` is granted.
- Academic Year UI authorization now follows the permission returned by `/auth/me` instead of incorrectly excluding the `ORGANIZATION_ADMIN` account type.
- Audit Logs now display the actor full name and username while retaining the UUID in the API for traceability.
- No database migration is required; Alembic head remains 024.

## V1.1.DEV.10 Organization Admin and core governance carried forward

- Organization Admin `/auth/me` now receives the Organization-wide effective core entitlement, so permission-authorized Students, Teachers, Fees, Marks, Attendance and Reports navigation is visible.
- Organization dashboard cards show today's posted collection amount, outstanding and overdue dues, Student and Teacher present/marked attendance and finalized-marks performance.
- Dashboard metric links preserve their report/date request through School selection and generate the detailed report.
- Phase 1 contains nine mandatory core modules. They are enabled by default, cannot be disabled through Organization or School license updates, and migration 024 normalizes existing records.
- All seven account types have automated frontend navigation-matrix coverage.
- Separate per-School, signed offline licensing is approved in the Phase 1 plan. The cryptographic activation workflow remains pending and is not claimed as implemented.

## V1.1.DEV.9 live-test corrections carried forward

- Migration 023 creates the Campus archive columns required by the ORM.
- Phase 1 licensing/bootstrap/provisioning includes `school_config`.
- Backend email fixtures and standardized error assertions pass the live PostgreSQL regression suite.

## V1.1.DEV.8 authentication and resilience changes carried forward

- Organization Admin can sign in with either the configured username or registered login email; both are case-insensitive.
- Organization tiles display both Organization Admin login identifiers.
- Organization Admin emails are unique within the Organization Admin login namespace.
- Local Vite development uses a same-origin `/api/v1` proxy, preventing `localhost`/`127.0.0.1` SameSite cookie mismatches.
- Network and backend `5xx` refresh failures preserve the browser session and show a retryable error; confirmed `401/403` refresh rejection still logs out securely.
- Users module provides an explicit Retry action when backend loading fails.

## Carried-forward governance controls

- Staff usernames are normalized and authenticated case-insensitively; passwords remain case-sensitive.
- Newly provisioned/reset credentials are temporary and require password change before normal ERP use.
- Password reset is limited to admin-level users and follows tenant/role hierarchy.
- School Administration navigation is limited to Super Admin, Organization Admin and School Admin; backend authorization remains enforced on every underlying API.
- Organization disable is reversible and preserves all School/data state while blocking tenant access.
- Platform Owner can Archive/Restore an Organization without deleting its records.
- School lifecycle is non-destructive: Archive/Restore replaces physical delete behavior and ERP School Codes remain reserved permanently.
- Local PostgreSQL backups support checksums, optional off-site replication and configurable tiered off-site retention.
- High-risk archive operations can require a recent successful backup.
- Provider / `Powered by` branding is intentionally not shown in this snapshot and can be introduced later when approved.

## Windows local development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.scripts.bootstrap
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --log-level info
```

For native Windows backups, configure the actual PostgreSQL paths in `backend\.env`, for example:

```env
BACKUP_DIR=./backups
PG_DUMP_PATH=C:/Program Files/PostgreSQL/18/bin/pg_dump.exe
PG_RESTORE_PATH=C:/Program Files/PostgreSQL/18/bin/pg_restore.exe
```

Frontend:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run build
npm run dev -- --host localhost --port 5173 --strictPort
```

The development frontend calls same-origin `/api/v1`; Vite proxies it to `VITE_DEV_API_TARGET` (`http://127.0.0.1:8001` by default). This keeps strict refresh cookies on the browser's current hostname.

Never commit `.env`, `.env.local`, database dumps, backup data, keys, certificates, `.venv`, `node_modules` or generated build directories.

## Release documentation policy

Every functional, security, dependency or deployment change must update all
applicable release documentation in the same commit:

1. `README.md` for current capabilities, setup or operator-facing behavior.
2. `reports/RELEASE_NOTES.md` for release changes.
3. `reports/QA_SECURITY_NOTES.md` and `reports/VALIDATION_REPORT.md` for test,
   vulnerability and deployment-gate evidence.

Do not report a blocked or unexecuted check as passed.

Offline license governance is described in `docs/PHASE1_LICENSE_GOVERNANCE.md`. Notifications remain planned for Phase 2 and are intentionally not enabled in this snapshot. See `PLANNING_NOTIFICATIONS.md`.

The Phase 1 account-purpose and tenant-scope matrix is documented in `docs/ROLE_GOVERNANCE.md`.
