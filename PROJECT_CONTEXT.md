# Project Context

- **Project name:** School ERP
- **Repo:** github.com/vkharishb/school_erp — dev branch
- **Backend stack:** FastAPI (Python)
- **Frontend stack:** React / TypeScript PWA
- **Database:**
  - Cloud: Neon (managed Postgres)
  - Local dev: local PostgreSQL instance (VS Code + venv, Windows)
  - Local Postgres is kept schema-identical to Neon — every migration must
    be applied to both. Local Postgres is not authoritative on its own;
    Neon test branch remains the reference for CI/automated tests.
- **Deployment/infra:** Docker Compose; hybrid architecture — on-prem edge
  server per campus + central cloud
- **Architecture notes:**
  - Data hierarchy: Organization → School → Campus
  - Edge server (on-prem, per campus) is source of truth for staff LAN
    read/write operations
  - Cloud holds Chairman/Director dashboard + Parent PWA (read API), fed by
    sync from edge
  - Multi-tenant — every schema/query decision must respect row-level
    isolation between tenants (RLS)
  - Attendance module is offline-first
  - Client base is K-12 school trusts only — no Higher Ed assumptions
- **Test/data safety rule:** Tests must run against a separate Neon test
  branch — never the live/production database. Local Postgres is a free
  sandbox: agents may create, drop, and seed data there without asking,
  as long as schema changes are still applied via proper migrations (not
  hand-edited) so it stays in sync with Neon.
- **Conventions:** ⚠️ Currently no git tracking at all — just files on disk.
  Strongly recommended before running agents on real work: run `git init`
  locally (no push/remote needed yet) so agent changes can be reviewed via
  `git diff` and rolled back if needed. Once git is in use: no PR review
  step required — agents produce a diff/summary, Harish reviews and
  approves directly, then commits locally. Pushing to GitHub only happens
  after the QA agent reports a clean pass on a feature-complete module AND
  Harish separately approves the push — DevSecOps enforces both. Branch
  naming and linting/formatting tools: still open, add once decided.

## Agent record folder (shared across all agents)
```
/docs/records/
├── architecture/          ← Architect's approved designs, one file per feature
├── status.md              ← shared coordination file: Database/Backend/Frontend
│                             claim tasks here and log progress, working in parallel
├── qa-review-<module>.md  ← QA's Full Module Readiness Review reports
└── PROJECT_LOG.md         ← single consolidated doc, maintained by Documentation agent
```
Create this folder structure at the repo root before running agents for
real. QA's full six-part review (functional, regression, penetration,
security, Playwright, k6) runs only when a module is marked feature-
complete in status.md — not after every small task.

## Current priorities (Phase 0)
- Security hardening
- RLS enforcement
- Edge/cloud deployment split
- Docker Compose installer for edge deployment
- Sync engine design (edge ↔ cloud)
- Neon test-branch separation
