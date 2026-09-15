# V1.1.DEV.8 — Development Snapshot

This snapshot corrects Organization Admin authentication/visibility and the Users-module forced-logout behavior reported during Windows development testing.

## Included work

- Organization Admin may authenticate with either its configured username or registered login email.
- Username and email login matching are case-insensitive; passwords remain case-sensitive.
- New Organization Admin email values are protected against ambiguous reuse in the Organization Admin login namespace.
- Organization API responses and Organization tiles show both valid Organization Admin login identifiers.
- Organization Admin login UI explicitly accepts username or email.
- Local Vite development uses a same-origin `/api/v1` proxy to the configured backend target, avoiding `localhost` versus `127.0.0.1` strict-cookie failures.
- Refresh handling logs out only when the backend confirms session rejection with `401` or `403`.
- Network, connectivity and backend `5xx` refresh failures preserve current browser authentication state and surface a retryable error.
- Users module clears stale errors before reload and provides a visible Retry action.
- Backend regression tests cover username login, email login, case-insensitivity, Organization tile/API login fields and Organization Admin email uniqueness.

## Database

Migration `022` normalizes Organization Admin emails and adds a case-insensitive partial unique index. It blocks migration when duplicate Organization Admin emails already exist and requires those accounts to be corrected explicitly before retrying.

## Promotion status

Development only. Do not promote to QA until Windows DEV applies migration `021 → 022`, runs PostgreSQL/Redis regression tests, completes frontend production build/lint and passes an end-to-end browser check using both Organization Admin login identifiers.
