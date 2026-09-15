## V1.1.DEV.21 — Org/School final QA hardening (2026-09-12)
- ORG-SCHOOL-SEC-01 closed: School status, archive and restore now use the shared `get_current_active_superuser` dependency instead of repeated inline superuser checks.
- ORG-SCHOOL-CAP-01 closed in source: School creation now acquires a PostgreSQL row lock for the Organization and active OrganizationSubscription before counting used School slots, serializing concurrent creation attempts for the same Society/Trust.
- Trial effective limit remains 1; paid School limits remain subscription-authoritative.
- Added regression assertions for lifecycle dependency centralization and lock-before-capacity-check ordering.
- Version remains V1.1.DEV.21; Alembic remains 030. No migration added.


## V1.1.DEV.21 — Platform Owner Schools design update (2026-09-09)
- Added Platform Owner Schools navigation: Add School, School List, School Capacity.
- Replaced School card directory with searchable table/list UI.
- Added School Capacity table with Active, Total Allowed and Available values; disabled Schools continue consuming entitlement.
- Redesigned School View into compact action rows with one-line descriptions; no action cards.
- School Disable/Enable and Archive are Platform Owner-only and require a business reason recorded in audit metadata.
- Audit Log viewing remains limited to Platform Owner, Organization Admin and School Admin within authorized scope.
- Applied shared email/mobile validation to touched School schemas and UI; backend normalizes 10-digit India mobile numbers to +91 E.164.
- Paid capacity increase action routes to Subscriptions for commercial adjustment; original agreement is not rewritten by the Schools UI.
- Version remains V1.1.DEV.21; Alembic head remains 029 (no schema migration required).

# SCHOOL ERP — Release Notes

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `RELEASE_INFO.md`

# SCHOOL ERP — Continuous Release Notes

## Current release candidate
- Version: V1.1.DEV.21
- Frontend: 1.1.0-dev.21
- Alembic head: 029
- Baseline: V1.1.DEV.20 / 028

## DEV.21
Platform Owner → Society/Trust management implementation: searchable list/View workflow, Society/Trust naming, atomic onboarding, Organization Admin login/contact consolidation, server-generated one-time temporary credentials, transactional email/resend support, discount reasons, activation override governance, expiry-gated disable/enable, 3-month manual archive eligibility, and 6-month operational-data retention lifecycle while retaining basic/subscription/payment history.

See `DEV_SNAPSHOT.md` and `QA_SECURITY_NOTES.md` for implementation and validation detail.

---

## Imported history/source: `docs/RELEASE_HISTORY.md`

# Release History

## V1.1.DEV.16 payments/subscriptions update — 2026-09-06

- Added separate Platform Owner Payments and Subscriptions modules.
- Added Organization billing, per-School activation, secure keys, receipts and reminders.
- Added restricted keyless 30-day trials and expiry enforcement.
- Added predefined/customized plans and Alembic 026.

## V1.1.DEV.15 maintenance update — 2026-09-06

- Approved Organization (Society/Trust) → School architecture; each physical branch
  is represented as a School and Campus is removed from the user-facing product model.
- Added Organization-first Platform Owner navigation, editable and audited My Profile,
  expanded Platform Dashboard overview, and School Subscriptions overview.
- Adopted Subscription, Core ERP and Add-ons terminology in active Platform Owner screens.
- Retained one hidden internal School compatibility scope for existing academic/finance
  foreign keys; full database flattening remains a controlled follow-up migration.
- Added Platform Owner experience regressions; frontend suite is now 14/14 passing.

- Added accessible show/hide password controls to all Account Security password
  fields by reusing the shared `PasswordInput` component.
- Preserved masked-by-default behavior and corrected browser autocomplete semantics.
- Frontend regression tests: 12/12 passed; production/PWA build passed.

- V1.1.DEV.15 — Shared ERP shell redesign, role-based operational/financial dashboards,
  reusable UI and centralized navigation cleanup, environment-only runtime secrets,
  dependency/security hardening, and Platform Owner visibility of the governing
  Organization Admin with backend-enforced hierarchy protection; Alembic remains 025.
- V1.1.DEV.13 — User designation/profile identity, Organization/School admin setup improvements, sidebar identity redesign, case-insensitive Platform Owner username regression coverage, and first-login/password-change flow corrections; Alembic head 025.
- V1.1.DEV.12 — Merged Class & Section bulk import with simple `Class Name | Name of Section` template, comma-separated Sections, automatic codes/sort order, preview/reuse validation and compatibility-hidden legacy endpoints; no schema migration (head remains 024).
- V1.1.DEV.11 — Targeted bugfix: Organization Admin Academic Year create/manage UI permission alignment; Audit Log actor full-name/username display; no schema migration (head remains 024).
- V1.1.DEV.10 — Organization Admin core-navigation correction; operational Organization dashboard with collection, dues, marked-record attendance and finalized-marks metrics; metric-to-branch report navigation; mandatory Phase 1 core-module enforcement through Alembic 024; all-role frontend navigation regression matrix; approved offline per-School licensing governance plan.
- V1.1.DEV.9 — Live PostgreSQL QA corrections: Campus archive model/schema synchronization through Alembic 023; `school_config` licensing/bootstrap/provisioning restoration; validator-compatible email fixtures; standardized duplicate-email error assertion.
- V1.1.DEV.8 — Organization Admin dual username/email login and tile visibility; case-insensitive unique Organization Admin email index; same-origin Vite API proxy; retryable Users-module backend failures; logout only on confirmed refresh-session rejection; Alembic head 022.
- V1.1.DEV.7 — New version-tag convention; case-insensitive usernames; temporary-password gate; admin password-reset hierarchy; admin-only School Administration navigation; Organization Archive/Restore; non-destructive School Archive/Restore; Organization Disable preserves child School state; optional off-site/tiered backup retention and recent-backup archive gate; provider attribution removed from current UI; Alembic head 021.
- V1.1.10-dev.6 — Fixed async School profile update failure (`MissingGreenlet`) by explicitly loading UDISE values; added regression coverage; simplified login footer to one configurable `Powered by` line with blank provider name by default. No database migration; Alembic head remains 020.
- V1.1.10-dev.5 — Login branding visibility/contrast fix for AKSHARA SCHOOL; Tailwind primary-950 palette correction and modern high-contrast split-screen branding panel. No database migration; Alembic head remains 020.
- V1.1.10-dev.4 — Phase 1 governance/data-model cleanup: ERP business codes, Organization head/admin provisioning and School limits, merged School profile/configuration, Organization-level Academic Year, optional multiple UDISE codes, predefined account types/custom Super Admin roles, mandatory reason/confirmation/audit controls, Parent/Student access and annual ERP-access fee integration; Alembic head 020.
- V1.1.10-dev.2 — AKSHARA SCHOOL branded login UX: modern responsive split-screen login, configurable client branding, synchronized application version metadata; Alembic head remains 019.
- V1.1.10-dev.1 — New versioning baseline mapped from the final Rev4 development state (Organization/School lifecycle and archived School identifier reuse).

## Legacy version labels

The entries below use the historical package naming that existed before the project adopted `V<Enhancement>.<Phase>.<Revision>-<snapshot>` versioning. They are retained for audit traceability.

- V1.2.9 — QA/security hardening release: tenant authorization, secure browser sessions, dependency upgrades, Student CRUD, dashboards and backup operations.
- v2.9.4 — project cleanup, current docs, dead/generated-file removal, secure PWA cache policy.
- v2.9.3 — Class/Section template download fix.
- v2.9.2 — Class & Section bulk import.
- v2.9.1 — actionable API/form/import errors.
- v2.9 — Reports module.
- v2.8.x — academic edit, centralized imports and navigation fixes.
- v2.7 — academic setup and bulk-import security.
- v2.6.x — user security, permission sidebar and password policy.
- v2.5 — admin navigation/RBAC/user fixes.
- v2.4 — campus schema sync.
- v2.3 — Windows timezone/license compatibility.
- v2.2/v2.1 — Alembic revision-chain corrections.

## V1.1.DEV.21 — Schools Create School revision (2026-09-09)
- Renamed Add School to Create School.
- Reworked School creation as a School-master-only process; School Admin creation is separate.
- Added approved parent/capacity, school-code, board, contact and address fields.
- School Code now uses School Short Code + Village Short Code and is globally unique.
- Alembic head: 030.

## 2026-09-11 — Approved modern UI/governance update
Modern Platform Owner dashboard/application shell, Society/Trust detail flow, School detail flow, persistent collapsible sidebar, and School Edit identity/mandatory-field governance were updated while retaining ERP version V1.1.DEV.21.

## 2026-09-12 — School-scoped user / legacy Campus Scope fix
- Fixed DEV.21 authorization regression where School-scoped operational users (including Teachers) without `campus_id` received `403: Campus scope is not assigned` while loading the School campus catalogue.
- `campus_id` remains optional for School-wide users; an explicitly assigned campus still narrows access to that campus.
- Teacher Management no longer calls the campus catalogue for view-only users; it loads campus data only when teacher creation needs it.
- Added backend regression coverage proving a School-scoped Teacher can read the School campus catalogue without a fake/default campus assignment.
- Version remains V1.1.DEV.21; Alembic remains 030 (head).

## DEV.21 Schools module correction batch
- School List now resolves the actual active School Admin account and shows activation state per School plus Activated / Total summary.
- School Capacity "Increase Limit" now stays in the School Capacity view and updates the audited Society/Trust School limit directly; the governing subscription School count remains synchronized by the existing backend rule.
- Module Catalogue now derives entitlement from the assigned subscription plan and shows Enabled, Disabled (not in plan / sync required), or Locked (not implemented) states. Platform Owner can synchronize implemented School modules to the assigned plan.
- Academic Years UI now exposes Current, Draft/Upcoming and Historical lifecycle states and an explicit Activate / Rollover action; activating a Draft closes the previous Active year and preserves history as read-only.
- Universal floating Back button retained; page-specific Schools back link removed to avoid duplicate navigation controls.

### DEV.21 School Capacity / Plan visibility correction
- Trial-plan Schools are excluded from School Capacity consumption and Active/Total capacity counts.
- School List now shows each School's assigned subscription Plan.
- Disabled paid-plan Schools continue to consume paid entitlement; Trial Schools do not.


## DEV.21 School Capacity & Trial Conversion Finalization
- School Capacity now means Schools Created versus approved School Limit, not activation count.
- Trial Society/Trust capacity is forcibly treated as 1 School; stale higher stored values no longer expand Trial capacity.
- Increase Limit is disabled for Trial and for paid organizations with unused slots; it becomes available only when Schools Created equals School Limit.
- Added Plan, Schools Created, School Limit and Available Slots to the School Capacity table.
- Added Trial → Paid conversion beside School lifecycle controls and beside Disable in Subscription activation-key management.
- After conversion, the Convert control becomes disabled as “Converted to Paid Plan”; the paid School Limit is captured during conversion and normal capacity rules apply.
- Backend School creation and Organization capacity updates enforce the same Trial/exhaustion rules.

## DEV.21 Organization + Schools gap-closure hardening — 2026-09-12
- School Module Catalogue is now backend-bound to the exact implemented entitlement of the School's assigned subscription plan; manual API attempts to add/remove plan modules are rejected.
- School Capacity increase remains disabled until paid capacity is exhausted and is always disabled for Trial.
- Paid capacity increases now require an effective date and business reason and calculate a prorated incremental charge for the remaining subscription term. Optional discount applies only to the incremental charge; GST follows the governing subscription tax settings. The adjustment is captured in the audit trail and added to the outstanding commercial balance.
- Trial conversion audit now records Trial origin, target plan, billing cycle, school limit, conversion timestamp, activation minimum and due date context.
- Organization disable continues as a reversible parent access suspension: School records retain their own lifecycle state while tenant login/API access is blocked at the Organization boundary, so re-enable does not guess or overwrite School state.
- Academic-year integrity remains enforced through the Organization Academic Year -> School MAIN projection -> StudentEnrollment/fees/marks relationships; historical years are read-only and rollover preserves prior records.
- Campus is retained only as the internal MAIN compatibility scope for the current schema; School remains the visible authorization/operational boundary and users are not required to receive a Campus assignment.


## DEV.21 — Organization / School Commercial & Governance Hardening (2026-09-12)
- Version remains **V1.1.DEV.21**. Alembic advances to **031**.
- Paid School lifecycle is now gated: subscription assignment does not activate ERP access. Paid Schools remain disabled and School licenses remain inactive until Organization Admin activation succeeds.
- Activation is atomic and backend-authoritative: active Society/Trust, unexpired paid subscription, Minimum Activation Payment satisfied, valid one-time activation key, current Terms & Conditions acceptance, School/Subscription/Key row locking, license enablement, School activation, and audit all occur in one transaction.
- Added versioned activation Terms acceptance evidence: accepted_at, accepted_by, terms_version and IP address on SchoolSubscription.
- School-scoped user creation is blocked for paid Schools until ERP activation completes, including Platform Owner attempts.
- Module/API access is centrally blocked while paid activation is pending.
- School restore now re-checks purchased School capacity under row locks; School enable also validates capacity and cannot bypass pending paid activation.
- Society/Trust emergency suspension override added for active subscriptions with mandatory reason and audit metadata.
- Retention worker no longer deletes retained School identity rows. It purges operational child data in reverse dependency order, deactivates retained School/user access, isolates per-tenant failures, and preserves Society/Trust, School identity, subscription and Organization payment history.
- School.organization_id is now mandatory with RESTRICT parent deletion semantics; migration 031 refuses to proceed if historical orphan Schools exist.
- UDISE restore now reconciles the legacy School.udise_code mirror with authoritative active UDISE rows and clears/reassigns it when conflicts exist.
- Organization Admin can view its own School directory; School create/capacity/lifecycle governance remains Platform Owner-only.
- School/Organization Admin profile editing now follows school.config.edit permission; UDISE governance remains Platform Owner-only.
- Initial School Admin is intentionally NOT auto-created during School creation: the approved activation gate requires user provisioning only after paid School activation.


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

