# Architecture — V1.1.DEV.16

## Approved tenant hierarchy

Platform Owner → Organization → School.

- Organization is the Society, Trust or educational group.
- School is a physical operating school; a real-world branch/campus is stored as a School.
- Organization Admin receives consolidated access to all authorized Schools.
- School Admin and operational users are School-scoped.
- Subscriptions are per School and consist of Core ERP plus future add-ons.

The former Campus layer is no longer part of the product model. Existing Phase 1
academic and finance tables still reference a single automatically managed internal
compatibility record per School. It is intentionally not presented as a separately
manageable entity. This boundary prevents a high-risk all-module rewrite while the
remaining foreign keys are progressively moved directly to School.

React/Vite → same-origin `/api/v1` development/production proxy → FastAPI → PostgreSQL, with Redis used for login throttling/session-related runtime support.

Authorization flow:

Authenticated session → active user → temporary-password gate → Organization active/not archived → School active/not archived/subscription → module entitlement → permission → tenant/scope → operation.

Phase 1 module entitlement is a mandatory core baseline. Role permission still decides whether an account may see or change data. Phase 2+ modules will be optional, signed per-School entitlements. The approved offline-license trust boundary is recorded in `PHASE1_LICENSE_GOVERNANCE.md`.

Primary domains:

School Administration, Students, Teachers, Attendance, Fees, Marks, Reports, RBAC, licensing, audit/governance, bulk imports, Parent/Student access and Backup/Restore.

Lifecycle operations are designed to preserve business history. Organization/School Archive is state transition, not physical data erasure. ERP School business codes remain historical identifiers and are not reused.

Backups consist of PostgreSQL database recovery points plus a separate strategy for file assets if/when the ERP stores uploaded binary documents locally. A production deployment should maintain an off-host copy.

The PWA may cache static application assets only. Authenticated `/api/v1` data must not be service-worker cached because it can contain student, staff and financial information.
