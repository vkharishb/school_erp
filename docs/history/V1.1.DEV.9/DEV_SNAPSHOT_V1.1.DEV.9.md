# V1.1.DEV.9 — Development Snapshot

This snapshot corrects the failures exposed when V1.1.DEV.8 was executed against the Windows development PostgreSQL database.

## Included corrections

- Added Alembic migration `023` so the `campuses` table contains the nullable `archived_at` and `archived_by` fields already declared by the Campus ORM model.
- Added the Campus archive timestamp index and `archived_by → users.id` foreign key with `ON DELETE SET NULL`.
- Restored `school_config` to Phase 1 licensing, the bootstrap module catalogue and frontend school-provisioning defaults; `IMPLEMENTED_MODULES` inherits it from `PHASE1_MODULES`.
- Replaced invalid `.test` email fixtures with validator-compatible `example.com` addresses without weakening production email validation.
- Updated the duplicate Organization Admin email regression test to assert against the standardized `error.message` response envelope.

## Carried forward

- Organization Admin login with either username or registered email, case-insensitively.
- Organization tile/API visibility of both valid Organization Admin login identifiers at authorized levels.
- Case-insensitive Organization Admin email uniqueness.
- Same-origin Vite API proxying and session preservation on retryable network/backend failures.
- Users-module Retry behavior without forced logout on availability failures.

## Database

Alembic head is `023`. Existing V1.1.DEV.8 databases at `022` must run `alembic upgrade head` before starting or testing this release.

## Promotion status

Development only. Re-run the complete Windows PostgreSQL suite after applying migration `023`; then complete the frontend build/lint and browser release gates before QA promotion.
