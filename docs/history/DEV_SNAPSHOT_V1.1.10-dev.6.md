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
