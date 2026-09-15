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
