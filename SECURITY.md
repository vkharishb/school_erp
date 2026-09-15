# Security Baseline — V1.1.DEV.16

Implemented controls include:

- Server-side RBAC plus Organization / School / Campus tenant enforcement.
- Organization, School and license checks on protected APIs; role permissions remain the operation-level boundary.
- Mandatory Phase 1 core entitlements cannot be disabled; Phase 2+ modules remain optional and must require explicit School-level entitlement.
- Rotating single-use refresh sessions with replay-family revocation.
- Browser refresh tokens in `HttpOnly`, `SameSite=Strict` cookies; access token kept in application memory.
- Production requirements for unique signing secret, HTTPS CORS origins and Secure refresh cookies.
- Redis-backed login throttling.
- Case-insensitive staff usernames with normalized uniqueness; Organization Admin additionally accepts its unique registered email as a login ID; passwords remain case-sensitive.
- Refresh failure handling distinguishes genuine `401/403` session rejection from temporary network/backend failure so availability incidents do not silently destroy valid browser state.
- Password strength validation, self-service change-password and active-session revocation after credential changes.
- Newly provisioned/reset accounts require a password change before normal ERP APIs are usable.
- Password reset restricted to admin-level users and enforced by hierarchy/tenant scope.
- Platform-only Modules, custom Roles & Permissions, System Settings and Backup & Restore.
- School Administration UI restricted to admin-level accounts; backend permissions remain authoritative.
- Audit logging for confirmed mutating operations, including tenant scope and mandatory change reason enforced by request middleware.
- Scoped reports and protected Excel export with spreadsheet-formula-injection protection.
- Checksum-protected PostgreSQL backups and guarded restore flow.

The approved offline School license design is documented in `docs/PHASE1_LICENSE_GOVERNANCE.md`. Signed offline-file activation is still planned and must not be represented as implemented until its cryptographic and recovery acceptance gates pass. Customer artifacts must never contain the Platform Owner private signing key.

## Organization / School lifecycle

- Organization Disable is a reversible access suspension. Organization data and child School status/data are preserved; tenant authentication/API access is blocked by the parent Organization state and active Organization sessions are revoked.
- Only Platform Owner / Super Admin may Archive or Restore an Organization.
- Archived Organizations are historical/read-only and remain disabled. Restore returns them to Disabled state; explicit Enable is required afterward.
- School Archive is non-destructive and requires the School to be Disabled first.
- Super Admin or the owning Organization Admin may Archive/Restore a School; School Admin cannot perform lifecycle archive operations.
- Archived School ERP codes remain permanently reserved and are not reused.
- Historical UDISE rows remain traceable. Their active uniqueness can be released after School archive so a legitimate replacement School can receive the identifier.
- Active sessions are revoked when Organization/School access is disabled or archived.

## Backup / recovery controls

- Local backups use PostgreSQL custom format and SHA-256 checksum sidecars.
- Optional `BACKUP_OFFSITE_DIR` can point to a different physical disk, network share or externally synchronized secure storage location.
- Off-site retention is tiered/configurable: daily, weekly and monthly recovery points.
- `REQUIRE_RECENT_BACKUP_FOR_ARCHIVE=true` can enforce a recent backup before Organization/School archive operations.
- Restore remains disabled by default and must be opened deliberately for an approved maintenance window.
- A pre-restore safety backup is created and checksum verification is performed.

A backup on the same failing disk is not disaster recovery. Production should use a physically separate encrypted/off-site destination and periodic restore verification.

## Production security gates still required

- Full PostgreSQL + Redis integration/regression suite.
- Tenant/RBAC negative tests across all functional endpoints.
- Frontend production build and dependency audit in a network-enabled build environment.
- Real backup → restore drill on non-production data.
- Secret/configuration scan of final production artifact.
- MFA/step-up authentication and financial maker-checker remain later hardening work unless explicitly brought into Phase 1.
