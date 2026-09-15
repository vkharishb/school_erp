## 2026-09-12 — SEC-01 / CAP-01 implementation
School status/archive/restore now use the shared Platform Owner dependency. School creation now locks the parent Organization and applicable OrganizationSubscription rows before reading current School count and enforcing capacity, preventing concurrent requests from independently consuming the same final slot. No migration was required.


## 2026-09-09 — Platform Owner Schools implementation
Implemented approved Platform Owner Schools architecture: Add School, School List, School Capacity; searchable table directory; capacity table; compact School View action rows; Platform Owner-only lifecycle governance with mandatory reasons; admin-only audit visibility; and shared contact validation on touched School flows. Version remains V1.1.DEV.21 / Alembic 029.

# SCHOOL ERP — Implementation Report

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **031**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `IMPLEMENTATION_V1.1.DEV.20.md`

# School ERP V1.1.DEV.20 — Subscription Renewal & Platform Status

## Why the version changed
This delivery adds database migration 028 (`organization_subscriptions.grace_until`) and new subscription API contracts. A DEV version bump is therefore required rather than silently retaining DEV.19.

## Implemented
- Trial → paid plan conversion remains data-preserving; surfaced in Renewals as **Convert to Paid Plan**.
- Organization Subscriptions now show Start Date, End Date and Grace Until.
- Organization Subscriptions replaces generic Action with **Send Reminder** and shows last reminder time.
- Yearly paid subscriptions align to **31 May**. Monthly subscriptions retain monthly cycle behavior.
- Paid subscriptions receive **30 days renewal grace**; Trial receives no renewal grace.
- Paid school entitlement/license access is extended through the grace date while the commercial End Date remains unchanged.
- Renewal and exceptional expiry extension are separate operations.
- Renewal requires renewal start date, Organization representative communicated with, communication method, and optional remarks. Logged-in Platform Owner is audit-captured automatically.
- Extension requires new end date, reason, communicated-with, communication method, and optional remarks; old/new dates are audit-captured.
- Platform Status now reports ERP version, live Alembic current/head status, DB connectivity, API health and environment.
- Playwright locator/authentication fixes from DEV.19 are retained.

## Migration
- Alembic head: 028
- 028 backfills paid Organization grace dates and extends existing paid School entitlements/licenses through the 30-day grace window.

## QA performed in build environment
- Python compileall: PASS
- Frontend Node regression tests: 19/19 PASS
- Backend pytest: not executable in build environment (`asyncpg` unavailable); must run on the project's PostgreSQL QA environment.
- Frontend production build: not executable in build environment because packaged frontend dependencies are incomplete (React/axios/zustand types unavailable).
- Playwright: must run against the user's live QA backend/frontend.

---

## Imported history/source: `IMPLEMENTATION_V1.1.DEV.21.md`

# SCHOOL ERP V1.1.DEV.21 — Society/Trust Management

Implementation candidate built from V1.1.DEV.20 / Alembic 028.

## Delivered
- Platform Owner Society/Trust list/search/View UI.
- Society/Trust terminology for Platform Owner navigation.
- Atomic Society/Trust + Organization Admin creation retained at transaction level.
- Admin Contact Email is login email; Group Admin/free-form designation.
- Mandatory 10-digit admin mobile onboarding validation with +91 normalization.
- Server-generated one-time temporary password; reset generates a new temporary password.
- Transactional SMTP account-information email and Resend Email action.
- Discount reason and minimum-activation override reason enforcement.
- Activation override original/current/audit persistence.
- Expiry-gated Disable/Enable with mandatory reason and actor audit.
- Manual archive eligibility only after 90 days from expiry.
- Hourly retention worker: Platform Owner information before 180-day point; deletes School-owned operational data at 180 days while retaining Society/Trust, subscription and payment records.
- Alembic migration 029.

## Validation state
See QA_SECURITY_NOTES.md. Full DB/frontend/E2E release validation remains required in the normal development environment.

## Platform Owner → Schools: Create School master form (2026-09-09)
Approved Create School workflow now separates School master creation from School Admin creation. The form contains parent Society/Trust, read-only allocated/total capacity, School Name, School Short Code, Village Short Code, generated permanent `SCHOOL-VILLAGE` School Code, Board/Curriculum (State Board/CBSE/ICSE), optional UDISE, School Email, 10-digit School Mobile, Address, City/Town, District, State and 6-digit PIN. School Type is intentionally excluded. School Code is globally unique and is no longer sequence-generated. Backend schema enforces the required master fields and School creation no longer accepts/creates a School Admin.

## DEV.21 approved governance fixes (2026-09-11)
- Removed obsolete global mutation confirmation middleware; normal POST/PUT/PATCH operations no longer require generic confirmation/reason headers.
- Trial plan now enforces exactly one School server-side; selecting Trial in Society/Trust creation sets School Count to 1 and locks the field.
- MAP reduction rule aligned: a reason is mandatory only when entered MAP is below the calculated 50% minimum. Equal/higher values require no override reason.
- Audit read visibility hardened: Platform Owner can investigate platform-wide; Organization Admin cannot read Platform Owner audit events; School Admin cannot read Platform Owner or Organization Admin governance events; operational users remain denied audit-log access.
- Subscription-backed School module entitlement continues to use the selected Plan mapping rather than a mandatory/core bundle; Platform Owner retains School module enable/disable control within the Organization entitlement.

## DEV.21 User Creation correction
- Removed the obsolete School Operational Scope/campus selector from New User UI.
- Society/Trust and School assignments are now shown explicitly on school-scoped user creation.
- Removed administrator-entered temporary passwords. Backend now generates a strong random temporary password for create/reset, stores only its hash, marks the account for mandatory first-login password change, and returns plaintext only in the immediate create/reset response.
- Reset Temporary Password now invalidates the old credential/sessions and shows the newly generated value once to the admin performing the reset.
- New User UI requires Email and 10-digit Phone and displays mandatory red asterisks; backend normalizes/validates supplied contacts and requires contacts for school-level account creation.

## V1.1.DEV.21 — Approved UI governance implementation (2026-09-11)
- Reworked the application shell to the approved compact global header and single left sidebar.
- Platform Owner sidebar now supports persistent expanded/icon-only collapse state and uses platform-governance navigation only.
- Platform Owner dashboard rebuilt around the approved KPI/analytics/attention/recent-activity layout using existing live ERP APIs.
- Society/Trust List -> View now switches to a dedicated detail surface; the list/search is not rendered above the selected record.
- School detail page rebuilt in the approved modern card/action layout with contextual Back to School List navigation.
- Normal Edit School now locks School identity fields and strengthens mandatory Board, email, mobile, address, city/town, district, state and PIN validation.
- Backend independently rejects normal-edit attempts to change School identity fields and validates required profile fields.
- Ticketing/Helpdesk remains a post-MVP roadmap enhancement and is not included in the MVP completion gate.

### School Capacity / Plan correction
Updated `frontend/src/pages/SchoolsPage.tsx` so capacity maps count only non-Trial School subscriptions. The School directory now includes a Plan column sourced from the School subscription. Capacity copy explicitly documents that Trial Schools do not consume entitlement.


## School Capacity + Trial Conversion Implementation
Implemented final Product Head rules: Trial = one School and no Increase Limit; paid Increase Limit only after capacity exhaustion; Trial conversion available beside School Disable controls; conversion captures paid School Limit and synchronizes Organization/subscription capacity; converted state disables the conversion action.

## Organization + Schools gap closure — implemented 2026-09-12
1. Module Catalogue entitlement is enforced in the backend against the assigned subscription plan.
2. Direct URL/API module access continues to pass through SchoolLicense checks; bulk imports already enforce their owning module.
3. School Capacity paid increases require exhausted capacity, effective date and reason; Trial remains non-increasable until conversion.
4. Incremental capacity charge is prorated over the remaining subscription term, with discount scoped only to the incremental charge and tax inherited from the account.
5. Trial conversion audit is expanded to preserve conversion context.
6. Organization disable is a reversible parent access suspension; School records keep their own state for deterministic re-enable behavior.
7. Academic-year history continues to be first-class through StudentEnrollment and academic-year-bound fee/marks records; historical years remain read-only.
8. Legacy Campus is isolated as an internal MAIN compatibility record and is not a mandatory user scope.


## 2026-09-12 — Gap Closure Implementation
Implemented commercial activation gate, versioned Terms acceptance, mandatory School parent migration, retention purge correction, restore/enable capacity hardening, emergency Society/Trust suspension override, UDISE restore reconciliation, Org Admin School directory access, and permission-aligned School profile editing. Version remains V1.1.DEV.21; Alembic head is 031.


## DEV.21 TypeScript compatibility correction
- Fixed Dashboard quick-action icon alias (`SchoolIcon`) so the imported `School` domain type is not used as a runtime value.
- Replaced `String.replaceAll()` with ES-compatible `replace(/_/g, " ")` in Module Catalogue and Schools views, preserving the current TypeScript target.
- No version bump and no database migration.
