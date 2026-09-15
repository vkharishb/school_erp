# School Re-create Fix — V1.2.9 Rev4

## Issue
Rev3 introduced soft-delete for Schools. The archived School row retained its `code` and `udise_code`, while the database still enforced global unique indexes. As a result, recreating a deleted School with the same identifiers incorrectly returned `School code already exists` or `UDISE code already exists`.

## Fix
- Product version remains **V1.2.9**.
- Added Alembic migration **019**.
- School code and UDISE uniqueness now applies only to non-deleted Schools (`deleted_at IS NULL`).
- Application duplicate checks ignore archived Schools.
- Historical archived rows remain untouched for audit/history integrity.
- Added regression coverage: create → disable → delete/archive → recreate using the exact same School code and UDISE must return `201 Created` with a new School ID.

## Upgrade
Run from `backend`:

```powershell
alembic upgrade head
alembic current
```

Expected head: `019`.
