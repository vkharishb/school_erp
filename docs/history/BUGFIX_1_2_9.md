# V1.2.9 Blocker Fix Amendment

Version remains **V1.2.9**.

## BUG-1 — Refresh-token rotation FK ordering

Fixed `backend/app/api/v1/auth.py::_issue_tokens` so the new `UserSession` is flushed to PostgreSQL before `parent_session.replaced_by_session_id` is assigned. This prevents the self-referential foreign-key violation (`sqlstate=23503`) during token rotation.

Regression coverage remains in `tests/test_auth_refresh.py::test_refresh_cookie_rotation_and_replay_protection`.

## BUG-2 — `school_config` licensing catalog

Added `school_config` to `PHASE1_MODULES`, which also places it in `IMPLEMENTED_MODULES`. School provisioning may now include the academic configuration module consistently with the permissions defined by bootstrap.

Added `tests/test_licensing_modules.py::test_school_config_is_a_phase1_implemented_module`.
