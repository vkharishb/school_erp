# Notifications Module — Product Planning

Status: **Planned (Phase 2)**  
Current development baseline: **V1.1.DEV.16**

General notifications are intentionally not enabled as a runtime module in V1.1.DEV.16. Audited subscription payment reminders are limited to Organization Admins; this document records the broader planned scope.

## Initial channels

1. In-app notifications
2. Email
3. SMS / WhatsApp / push after provider approval/integration

## Targeting / scope

- Platform Owner / Super Admin
- Organization Admin
- School Admin
- Accounts
- Receptionist
- Teacher
- Parent / Student
- Organization-wide, School-wide, role-specific and user-specific delivery

## Planned event types

- Organization enabled / disabled / archived / restored
- School enabled / disabled / archived / restored
- User created / enabled / disabled
- Password reset / password changed / suspicious login
- License approaching expiry / expired
- Fee payment / cancellation / approval events
- Import success / failure
- Backup success / failure / off-site sync failure
- Restore started / completed / failed
- Security and system announcements

## Security requirements

Every notification must respect tenant scope and must never expose information the recipient cannot access through the underlying authorized API. Passwords, secrets and unnecessary financial identifiers must never be placed in notification bodies.
