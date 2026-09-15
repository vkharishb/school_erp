## 2026-09-09 — Schools checkpoint
Full Playwright E2E is intentionally deferred until all approved phases are complete. No School-module Playwright sign-off is claimed for this package.

# SCHOOL ERP — Playwright / E2E Report

## Current Package
- ERP Version: **V1.1.DEV.21**
- Alembic Head: **030**
- Reporting policy: continuously maintained in `reports/`; version history retained in this file.

---

## Imported history/source: `PLAYWRIGHT_E2E_TEST_MATRIX.md`

# School ERP Playwright E2E Test Matrix — V1.1.DEV.19

| ID | Area | Automated assertion |
|---|---|---|
| E2E-001 | Security | Protected UI redirects anonymous users to login |
| E2E-002 | Authentication | Platform Owner can sign in |
| E2E-003 | Authentication | Invalid password is rejected |
| E2E-004 | Governance | Platform Owner can open Organizations, Schools, Payments, Subscriptions, System Settings |
| E2E-005 | Subscription | Lifecycle is Plan → Organization Subscription → School Entitlement → Activation Key → ERP Activation |
| E2E-006 | Trial | UI states 30-day restriction, no key and blocked downloads/exports |
| E2E-007 | Plans | BASIC, STANDARD, PREMIUM, CUSTOMIZED, PAYG are visible when seeded |
| E2E-008 | Commercial UI | Plans, Subscriptions, Entitlements, Keys, Renewals, Reminders tabs are present |
| E2E-009 | Organization | Onboarding requires subscription plan and Organization Admin credentials |
| E2E-010 | School | Onboarding is Organization-scoped and creates School Admin credentials |
| E2E-011 | Mutation | Optional isolated-QA Trial Organization creation succeeds |
| E2E-012 | Entitlements | Module Catalogue states subscription-based/locked behavior |
| E2E-013 | API security | Anonymous `/auth/me` is rejected |
| E2E-014 | API security | Malformed login never produces HTTP 5xx |

Mutation tests are disabled unless `E2E_RUN_MUTATIONS=1`.

---

## Imported history/source: `PLAYWRIGHT_FIX_NOTES_DEV19.md`

# V1.1.DEV.19 Playwright Fix Notes

Fixes from the 7 passed / 4 failed / 2 skipped browser run:

- Fixed bootstrap refresh/login race in `authStore.ts` so a stale anonymous refresh cannot clear a newly authenticated Platform Owner session.
- Replaced ambiguous Organization Admin Login locator with heading role locator.
- Replaced ambiguous Create School locator with separate heading and button role locators.
- Replaced fragile System Settings copy assertion with route authorization, page heading, and access-policy assertion.
- Added per-route Playwright steps to identify the exact governance route if a future authentication redirect occurs.

Validation in packaging environment:
- Frontend regression suite: 17/17 passed.
- Full Playwright browser rerun requires the user's running frontend/backend and QA credentials.
- Frontend typecheck/build could not be validated in the packaging environment because the packaged root frontend dependencies are not installed there.

---

## Imported history/source: `frontend/E2E_PLAYWRIGHT.md`

# Playwright End-to-End QA — School ERP V1.1.DEV.19

This suite adds genuine browser automation; it is separate from the existing Node source-regression tests.

## Covered
- Anonymous route protection and Platform Owner login.
- Invalid-login security behavior.
- Platform Owner access to Organizations, Schools, Payments, Subscriptions and System Settings.
- Subscription lifecycle wording and seeded BASIC/STANDARD/PREMIUM/CUSTOMIZED/PAYG catalog visibility.
- Trial restrictions: 30 days, no activation key, downloads/exports blocked.
- Organization onboarding form and subscription requirement.
- School onboarding form and School Admin creation contract.
- Platform-only governance access.
- Subscription-based Module Catalogue / locked-module behavior.
- Anonymous protected API and malformed-login smoke checks.
- Optional real Trial Organization creation against an isolated QA database.

## Install
From `frontend/e2e`:

```powershell
npm install
npx playwright install chromium
```

## Required environment
Run the backend and frontend first. The frontend defaults to `http://127.0.0.1:5173`.

```powershell
$env:E2E_BASE_URL="http://127.0.0.1:5173"
$env:E2E_SUPER_ADMIN_USERNAME="<your-platform-owner-username>"
$env:E2E_SUPER_ADMIN_PASSWORD="<your-platform-owner-password>"
npm test
```

To let Playwright start Vite itself (backend must still be running):

```powershell
$env:E2E_MANAGE_SERVERS="1"
npm test
```

## Mutation tests
Mutation tests are skipped by default because they create data. Run them ONLY on a disposable/isolated QA database:

```powershell
$env:E2E_RUN_MUTATIONS="1"
npm test
```

The suite automatically accepts the ERP change-confirmation dialog and supplies a QA change reason for mutation tests.

## Evidence
Failures retain screenshots, video and Playwright traces. HTML report:

```powershell
npm run report
```

## Release gate
A release candidate should pass, in order:

```powershell
cd backend
pytest -q
cd ..\frontend
npm run test
npm run build
cd e2e
npm test
```

Do not treat Playwright as a substitute for backend pytest. Both are required.
