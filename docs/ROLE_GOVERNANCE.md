# Phase 1 Role Governance

Backend permissions and tenant scope are authoritative. Frontend navigation is a convenience and never grants access by itself. Phase 1 core modules are available to every licensed School, while each account sees only the operations assigned to its role.

| Account type | Tenant scope | Primary Phase 1 purpose |
|---|---|---|
| Platform Owner / Super Admin | Entire platform | Organizations, School licenses, system governance, backup/restore and controlled support |
| Organization Admin | One Organization and every active School / Branch in it | Consolidated oversight plus authorized operational administration across branches |
| School / Branch Admin | One School / Branch | Day-to-day School administration and operational control |
| Accounts | One School / Branch | Fee setup, collection, dues, exports and finance reports |
| Teacher | Assigned School / Campus | Student lookup, attendance, marks and permitted reports |
| Receptionist | One School / Branch | Limited front-office fee/teacher lookup; no student mutation or reports by default |
| Parent / Student | Explicitly linked students only | Read-only portal for linked attendance, finalized marks and fees |

## Organization Admin decisions

An Organization Admin may, across its own Organization:

- create and edit Schools / Branches within the licensed School limit;
- create/edit students and archive/reactivate them instead of physical deletion;
- create/edit teachers;
- configure and collect fees, view outstanding/overdue dues and use authorized exports;
- mark/view Student and Teacher attendance;
- enter/finalize marks and view performance reports;
- create School-level users, reset them within hierarchy and view audit records;
- manage the Organization Academic Year shared by all its Schools;
- view branch-wise consolidated collection, dues, attendance and finalized-marks performance.

An Organization Admin may not manage Platform Owner accounts, sign/generate licenses, alter the private signing trust, manage platform settings/backup restore, assign platform-only custom roles, exceed its Organization boundary, or physically erase business history.

## Separation within an Organization

The Organization Admin does not need to personally perform every daily activity. Recommended delegation is:

- School Admin for complete one-branch operations;
- Accounts for collection and dues;
- Teacher for attendance and marks;
- Receptionist for limited front-office work;
- Parent / Student for linked read-only self-service.

This separation improves audit accountability: every collection, attendance change, marks finalization, password reset and lifecycle action is attributable to the actual account that performed it.
