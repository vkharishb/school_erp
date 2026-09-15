# CI / CT / CD

Before production CD:
1. Separate development, staging/test and production databases.
2. Store credentials only in secrets.
3. Block merges/deploys on migrations, backend tests and frontend build/type checks.
4. Never run destructive tests against production.
5. Require manual production approval.
6. Verify a usable backup before production migrations.
