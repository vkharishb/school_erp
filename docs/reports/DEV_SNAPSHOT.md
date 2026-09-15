## 2026-09-12 — Final Org/Schools QA hardening
- Closed ORG-SCHOOL-SEC-01 by centralizing Platform Owner authorization for School lifecycle endpoints.
- Closed ORG-SCHOOL-CAP-01 in implementation by serializing same-Organization School creation around the capacity decision with row-level locks.
- No schema change; V1.1.DEV.21 / Alembic 030 unchanged.


## 2026-09-09 — Platform Owner Schools update
- Status: implemented in V1.1.DEV.21 source; Alembic head 030.
- Platform sidebar now exposes Add School / School List / School Capacity.
- School list and capacity screens use tables, not cards. School View uses compact action rows.
- Platform Owner exclusively controls School create/lifecycle/archive/restore governance.
- Audit visibility policy: Platform Owner, Organization Admin and School Admin only, scope-enforced by backend.
- Paid Increase Limit is handed to Subscriptions as a commercial adjustment boundary; Trial/paid adjustment accounting is not duplicated inside Schools.

# SCHOOL ERP — DEV Snapshot

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `DEV_SNAPSHOT.md`

# SCHOOL ERP — Continuous DEV Snapshot

## Current baseline
- Release: V1.1.DEV.21
- Frontend: 1.1.0-dev.21
- Alembic head: 029

## DEV.21 Society/Trust implementation
- Renamed Platform Owner-facing Organization identity to Society/Trust while preserving internal API/table compatibility.
- Replaced Society/Trust cards with searchable table/list and View workflow.
- Organization Admin contact email is the login email; designation is free-form with Group Admin default.
- Admin mobile is mandatory 10-digit input and normalized to India E.164 on onboarding.
- Temporary passwords are generated server-side, shown once, hashed only, force change on login, and can be regenerated with audit.
- Added transactional SMTP email service and Resend Email action; email delivery failure does not roll back onboarding.
- Discount reason is mandatory when discount applies.
- Minimum activation payment override requires a reason and records original/override audit fields; initial override is represented as the one permitted override.
- Disable/Enable requires a reason and is backend-locked until subscription expiry.
- Archive is backend-locked until 90 days after expiry.
- Retention worker informs Platform Owner before the 180-day deletion point and deletes only School-owned operational data, retaining Society/Trust, subscription and payment history.
- Added migration 029 for governance/retention/activation-override fields.

---

## Imported history/source: `docs/IMPLEMENTATION_STATUS.md`

# Implementation Status — V1.1.DEV.16

Phase 1 functional foundation is substantially implemented: authentication/session security, RBAC/tenant scope, Organizations/Schools, Organization-level Academic Years, Classes/Sections, Subjects, Users, licensing/modules, Students, Teachers, Attendance, Fees, Marks, Reports, Audit Logs, bulk imports and protected Backup/Restore.

V1.1.DEV.16 adds Platform Owner Payments and Subscriptions, Organization-level billing, per-School activation entitlements, restricted trials and Organization Admin ERP Activation. Earlier role-based shell, enrollment/import, System Settings and security controls remain in force. Alembic head is 026.

Current module delivery status is exposed directly in System Settings and intentionally distinguishes product-development status from customer licensing/entitlement.

Approved direction but intentionally deferred to the Phase 1 closing milestone: a separate internal Licensing/Activation Server will authorize ERP installation request codes and return signed activation responses. Production Platform Owner first-time creation will follow successful activation. The temporary development bootstrap remains development-only until that milestone.

Before Phase 1 can be closed, complete environment-backed QA: PostgreSQL/Redis regression tests, frontend dependency-backed production build, browser role/dashboard flows, backup→restore verification, Development Data Reset on a disposable lower-environment database, Licensing/Activation Server integration/security tests and the clean-install/Platform Owner setup workflow.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.10-dev.2.md`

# V1.1.10-dev.2 — Development Snapshot

## Purpose

Phase 1 UX/branding development for AKSHARA SCHOOL.

## Implemented

1. Desktop split-screen login: school branding left, credentials right.
2. Responsive mobile login with compact school identity header.
3. AKSHARA SCHOOL as the client identity.
4. configured provider as Technology Partner / Powered by identity.
5. Configurable public branding via Vite environment variables.
6. Version label V1.1.10-dev.2 shown on the login UI.
7. Application/backend version metadata synchronized.
8. `/api/v1/system/version` migration head corrected to 019.

## Database

No new migration is required for this snapshot. Alembic head remains `019`.

## Promotion

This remains a development snapshot. It should not be renamed to `-qa.1` until the development acceptance checks are completed and the Product Head approves QA promotion.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.10-dev.4.md`

# V1.1.10-dev.4 — Development Snapshot

Status: Development only. Not promoted to QA.
Alembic head: 020.

This snapshot contains the approved Phase 1 governance, ERP code, role/permission, Organization/School profile, optional multiple UDISE, Organization-level Academic Year, Parent/Student access, and annual ERP-access fee integration changes.

Before local use:

```powershell
cd backend
alembic upgrade head
alembic current
```

Expected current migration after upgrade: `020 (head)`.

Then run the backend regression suite and frontend build before considering the snapshot ready for QA.


## dev.4 Windows/build stabilization

- Fixed TypeScript ES2020 compatibility by replacing `String.replaceAll` usage and explicitly typing the report-label replacement callback.
- Reworked PostgreSQL backup command execution to use `asyncio.to_thread(subprocess.run, ...)`, avoiding `NotImplementedError` from Windows asyncio subprocess transports under ASGI reload/event-loop configurations.
- Added clear errors when `pg_dump` / `pg_restore` are not available on PATH or configured explicitly.
- No database schema change; Alembic head remains `020`.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.10-dev.5.md`

# V1.1.10-dev.5 — Development Snapshot

## Login branding visibility fix

- Fixed the AKSHARA SCHOOL branding panel rendering with insufficient contrast.
- Root cause: `bg-primary-950` was referenced while the Tailwind primary palette only defined shades through `900`.
- Added `primary.950` to the Tailwind palette and replaced the login branding panel with an explicit dark, high-contrast gradient.
- Improved AKSHARA SCHOOL title contrast, capability cards, technology-partner footer, decorative background and responsive presentation.
- Kept the account-type login flow unchanged.
- No database/schema change. Alembic head remains `020`.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.10-dev.6.md`

# V1.1.10-dev.6 — Development Snapshot

## School profile update stability

- Fixed `PATCH /api/v1/schools/{school_id}/profile` returning HTTP 500 with SQLAlchemy `MissingGreenlet`.
- Root cause: an AsyncSession request handler accessed the lazy `school.udise_codes` relationship.
- Current UDISE values are now loaded with an explicit async SELECT before applying profile changes.
- Added a regression test for updating a School profile that already has a UDISE code.

## Login footer cleanup

- Removed duplicate `Technology Partner` branding from the left panel.
- Kept one configurable `Powered by` line on the login side only.
- Provider name is blank by default and can be supplied later through `VITE_POWERED_BY_NAME`.
- `VITE_SHOW_POWERED_BY=false` can hide the line entirely.

## Database

- No schema change.
- Alembic head remains `020`.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.DEV.7.md`

# V1.1.DEV.7 — Development Snapshot

This snapshot is the continuation of the former `V1.1.10-dev.6` development line under the newly approved tag convention.

## Included work

- Case-insensitive staff usernames and normalized uniqueness.
- Temporary-password / mandatory first-change behavior for provisioned and reset accounts.
- Admin password-reset hierarchy with tenant restrictions, session revocation and audit.
- School Administration restricted to admin-level users in frontend routing/navigation.
- Platform Owner Organization Archive/Restore.
- Organization Disable preserves all data and child School status while suspending access.
- School Delete replaced operationally by Archive/Restore; no physical School deletion.
- ERP School codes remain permanently reserved.
- Backup checksums, status, optional off-site copy, tiered retention and optional recent-backup archive gate.
- Current login UI contains no provider attribution / `Powered by` area.
- Alembic head advanced from 020 to 021.

## Promotion status

Development only. Do not promote to QA until Windows DEV migration, PostgreSQL/Redis regression tests and the dependency-backed frontend production build pass.

---

## Imported history/source: `docs/history/DEV_SNAPSHOT_V1.1.DEV.8.md`

# V1.1.DEV.8 — Development Snapshot

This snapshot corrects Organization Admin authentication/visibility and the Users-module forced-logout behavior reported during Windows development testing.

## Included work

- Organization Admin may authenticate with either its configured username or registered login email.
- Username and email login matching are case-insensitive; passwords remain case-sensitive.
- New Organization Admin email values are protected against ambiguous reuse in the Organization Admin login namespace.
- Organization API responses and Organization tiles show both valid Organization Admin login identifiers.
- Organization Admin login UI explicitly accepts username or email.
- Local Vite development uses a same-origin `/api/v1` proxy to the configured backend target, avoiding `localhost` versus `127.0.0.1` strict-cookie failures.
- Refresh handling logs out only when the backend confirms session rejection with `401` or `403`.
- Network, connectivity and backend `5xx` refresh failures preserve current browser authentication state and surface a retryable error.
- Users module clears stale errors before reload and provides a visible Retry action.
- Backend regression tests cover username login, email login, case-insensitivity, Organization tile/API login fields and Organization Admin email uniqueness.

## Database

Migration `022` normalizes Organization Admin emails and adds a case-insensitive partial unique index. It blocks migration when duplicate Organization Admin emails already exist and requires those accounts to be corrected explicitly before retrying.

## Promotion status

Development only. Do not promote to QA until Windows DEV applies migration `021 → 022`, runs PostgreSQL/Redis regression tests, completes frontend production build/lint and passes an end-to-end browser check using both Organization Admin login identifiers.

## 2026-09-09 — Create School form revision
- ERP version remains V1.1.DEV.21.
- Alembic head advances to 030 for School district storage and global School Code registry uniqueness.
- `Add School` renamed to `Create School`.
- School Admin creation removed from School master creation workflow.
- School Code format: `<SCHOOL_SHORT_CODE>-<VILLAGE_SHORT_CODE>`; uppercase/alphanumeric parts, globally unique.

## 2026-09-12 — QA-01 Teacher login / School scope correction
- Corrected mismatch between the user model (where `campus_id` is optional for School-wide roles) and legacy authorization checks that treated Campus Scope as mandatory.
- `ensure_campus_access` now permits School-scoped users with no explicit campus assignment to access campuses belonging to their own School, while explicit campus assignments remain restricted.
- `/foundation/schools/{school_id}/campuses` now returns the School catalogue for authorized School-scoped users instead of raising `Campus scope is not assigned`.
- Teacher list UI avoids the campus catalogue request for view-only users.
- No schema migration and no version increase.

## DEV.21 Schools correction snapshot
Schools module correction batch applied without version or database schema change. Version remains V1.1.DEV.21; Alembic remains 030.


## School Capacity / Trial Conversion Final Rule
- ERP version remains **V1.1.DEV.21**; frontend remains **1.1.0-dev.21**; Alembic head remains **030**.
- Trial effective School Limit is fixed at 1.
- Paid Increase Limit is enabled only after the current limit is exhausted.
- Trial conversion captures target paid plan, billing cycle and paid School Limit, then moves the subscription to pending payment/activation flow.

## 2026-09-12 — Organization + Schools gap-closure snapshot
- Version remains V1.1.DEV.21; Alembic remains 030 (no schema migration required for this hardening batch).
- Module entitlement sync is now server-authoritative against the assigned plan.
- Capacity increase commercial linkage added: effective date, reason, incremental-only discount, proration, GST and audit metadata; incremental finalized amount is added to outstanding balance.
- Trial conversion audit enriched.
- Organization disable/re-enable semantics locked as parent access suspension with child School lifecycle-state preservation.
- Internal MAIN Campus compatibility remains isolated from visible School-scoped authorization.


## 2026-09-12 — Commercial Activation / Governance Gap Closure
- Baseline: V1.1.DEV.21.
- Alembic head: **031** (`031_activation_governance_hardening.py`).
- Activation invariant: `Organization Active × School Active × Paid Activation Active × Plan Entitlement × User Permission`. Trial is the explicit no-key exception.
- Paid School creation now produces `pending_activation` entitlement + inactive SchoolLicense + inactive School record until Organization Admin activation.
- Activation requires MAP/payment eligibility, valid School-bound one-time key, current versioned Terms acceptance, and transactional row locks.
- User provisioning and operational module APIs reject paid Schools still pending activation.
- Restore/enable capacity bypasses closed; restore consumes a slot only after locked capacity validation.
- Org Admin School directory access and permission-based School profile editing corrected.
- Campus is NOT physically removed in this batch. Internal MAIN Campus remains a compatibility projection only; School remains the visible tenant/auth boundary.


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

