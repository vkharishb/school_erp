# Phase 1 Licensing & Activation Governance

Status: **Approved architecture direction; implementation intentionally deferred to the Phase 1 closing milestone**

## Current decision

The customer School ERP will not be trusted to generate or extend its own license. A separate internal Licensing & Activation System, operated by the product owner, will become the authority for installation activation.

Until that internal server is provisioned, DEV environments may use the existing bootstrap flow for development/testing only. It is not the final production provisioning model.

## Planned trust flow

1. A fresh School ERP installation creates a permanent Installation UUID and an **Activation Request Code** containing non-secret installation metadata.
2. The request code is submitted to the private internal Licensing Portal/Server.
3. An authorized internal licensing user selects the customer, commercial terms, limits and entitlements.
4. The Licensing Server signs an **Activation Response / License** using an asymmetric private signing key held only on the internal server.
5. The School ERP receives the signed response online or by copy/paste/offline file and verifies it with the embedded public verification key.
6. Successful activation unlocks one-time **Platform Owner creation**. Production must not depend on a known permanent `superadmin` credential.
7. Once Platform Owner creation succeeds, initial setup is locked and normal login begins.

## Internal Licensing System

The internal system is a separate application/repository and must not be distributed with School ERP. Minimum capabilities:

- Customers
- Products / editions
- Licenses and validity
- Organization/School/user/module limits
- Installation IDs
- Activation requests and responses
- Renewal, suspend, deactivate and controlled transfer/rebind
- Immutable licensing audit log
- Internal users/roles
- Encrypted backup and signing-key recovery procedure

The private signing key must never be stored in customer source packages, Docker images, `.env.example`, customer databases or ordinary backups.

## Activation states

- NOT_ACTIVATED
- ACTIVE
- GRACE_PERIOD
- EXPIRED
- SUSPENDED
- TRANSFER_PENDING
- DEACTIVATED

License expiry must not destroy or hide school data. The final commercial policy should preserve safe read/recovery access and allow the Platform Owner to renew/reactivate.

## Installation scope

Production installation planning includes:

- Backend API
- Frontend
- PostgreSQL database
- Redis / required services
- Reverse proxy / HTTPS as applicable
- Automated Alembic migrations
- Backup configuration and restore verification
- Product activation
- Platform Owner first-time creation

## Platform Owner provisioning

After successful product activation, the one-time setup collects:

- Full Name
- Permanent Username (suggested default: `PLATFORM_ADMIN`, editable)
- Strong Password + confirmation
- Email
- Mobile
- Designation fixed to Platform Owner

The internal account type remains `PLATFORM_SUPER_ADMIN`. Usernames are case-insensitive; passwords are case-sensitive.

## Phase 1 acceptance gates

Licensing/activation must not be marked complete until tests cover request-code generation, signed response verification, tamper detection, invalid/expired responses, installation binding, duplicate/replayed activation, renewal, suspend, transfer/rebind, offline activation, loss/recovery procedures, absence of private signing material from customer packages, one-time Platform Owner creation and setup lockout after completion.
