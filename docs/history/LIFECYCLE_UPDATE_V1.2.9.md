# V1.2.9 Rev3 — Organization / School Lifecycle Update

Product version remains **V1.2.9**.

## Implemented

1. **Organization disable cascades to Schools**
   - `PATCH /api/v1/organizations/{organization_id}/status` with `is_active=false` sets every active, non-deleted child School/Branch to inactive.
   - Organization user sessions are revoked.
   - Re-enabling the Organization does not automatically re-enable Schools.

2. **School cannot be enabled under a disabled Organization**
   - Backend returns HTTP 409:
     `Organization is disabled. Please activate the Organization before enabling this School.`
   - Frontend displays the backend message as an alert/error.

3. **Disabled School can be deleted**
   - `DELETE /api/v1/schools/{school_id}` is Platform-Super-Admin-only.
   - Active Schools return HTTP 409 and must be disabled first.
   - Delete is a soft archive: `deleted_at` and `deleted_by` are stored, normal lists hide the School, users/campuses/license are disabled, sessions are revoked, and historical records remain in PostgreSQL.
   - Alembic migration: `018_school_lifecycle_soft_delete.py`.

4. **Notifications added to planning**
   - See `PLANNING_NOTIFICATIONS.md`.
   - Notifications are not exposed as an unfinished runtime module in V1.2.9.

## Windows QA harness improvement

- `backend/tests/conftest.py` forces `APP_ENV=test` before application imports so Redis login-rate-limit state does not interfere with integration test logins.
- `bootstrap.py` synchronizes the Super Admin password only in `test`/`ci`. Development and production bootstrap continue to preserve an existing password.

## Regression gate

A new lifecycle integration test covers Organization disable cascade, blocked School enable, manual re-enable after Organization activation, delete-disabled-only behavior and archived-School hiding.

## Rev4 — Recreate an archived School with the same identifiers
A soft-deleted School no longer permanently reserves its Unit Code or UDISE Code. Migration `019_reuse_archived_school_identifiers.py` changes uniqueness to active rows only (`deleted_at IS NULL`). This preserves the archived School/history while allowing a newly created active School to reuse the exact same Unit Code and UDISE Code.
