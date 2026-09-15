## V1.1.DEV.16 Platform Payments and Subscriptions

- Adds Organization-level subscription billing, discounts, GST/non-GST tax,
  partial/full payments, balances, receipts, statements and reminders.
- Adds predefined/customized plans and separate per-School activation entitlements.
- Adds secure one-time activation keys and Organization Admin ERP Activation.
- Adds restricted keyless 30-day trials with export blocking and automatic expiry.
- Restricts School creation and all commercial controls to Platform Owner.
- Adds Alembic revision 026.

## V1.1.DEV.15 Platform Owner System Settings

- Adds Platform Status and Platform Version summary cards.
- Adds a 28-module phase/status checklist backed by one product catalog.
- Adds lower-environment Development Data Reset with production hard-block, password + typed confirmation, mandatory safety backup, Platform Owner preservation, and forced re-login.
- Alembic remains 025.

## V1.1.DEV.15 role-based shell/dashboard

- Dashboard summary now returns active-student birthdays and real system reminders without weakening tenant scope.
- Frontend shell/dashboard changes are documented at repository level; no backend schema migration is required.

# Backend fixes in this package

- `imports.py`: adds one controlled Class & Section bulk workflow using a simple two-column workbook; ERP generates technical codes/sort order, reuses existing active records and creates only missing Classes/Sections.
- Legacy separate Class/Section import endpoints remain available for backward compatibility but are hidden from the API schema.
- `auth.py` / `module_access.py`: Organization Admin receives Organization-wide effective core modules; School users receive valid School/Organization entitlement intersection.
- `organizations.py`: consolidated daily Organization metrics for posted collections, outstanding/overdue dues, marked-record attendance and finalized marks.
- `licensing.py`, Organization/School license APIs and Alembic 024: all Phase 1 modules are mandatory core and cannot be disabled.
- Regression suite: Organization Admin core entitlement, all-role navigation contract, dashboard calculation and core-license rejection coverage.
- `schools.py`: the school configuration PATCH now requires `school.config.edit` and consistently uses the dependency-injected user.
- `bootstrap.py`: existing super-admin credentials are reset only when `APP_ENV` is `test` or `ci`; production/development accounts are left untouched.
- `requirements.txt`: pins `bcrypt==4.0.1`, compatible with `passlib==1.7.4`, removing the known bcrypt metadata warning.

## Important

Run CI against a dedicated test database. Do not point CT at production.

For local deterministic authentication tests, set `APP_ENV=test`, point `DATABASE_URL` to a disposable test database, run migrations, then run the bootstrap script before pytest.

## V1.1.DEV.13 in-place Student enrolment alignment

- Aligned manual New Student enrolment with the approved 20-field Student model.
- Student Bulk Upload now uses the same 20 fields, including per-row Academic Year, Class and Section.
- Student template download now includes an ERP Reference sheet scoped to the selected Campus.
- Removed Prior Year Due from Student Import; opening dues remain in the dedicated Fee Management import.
- No schema migration; Alembic remains 025.
