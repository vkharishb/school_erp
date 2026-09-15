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
