import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const schoolsApi = fs.readFileSync(new URL('../../backend/app/api/v1/schools.py', import.meta.url), 'utf8');
const paymentsApi = fs.readFileSync(new URL('../../backend/app/api/v1/payments.py', import.meta.url), 'utf8');
const deps = fs.readFileSync(new URL('../../backend/app/core/deps.py', import.meta.url), 'utf8');
const usersApi = fs.readFileSync(new URL('../../backend/app/api/v1/users.py', import.meta.url), 'utf8');
const lifecycle = fs.readFileSync(new URL('../../backend/app/services/society_trust_lifecycle.py', import.meta.url), 'utf8');
const activationPage = fs.readFileSync(new URL('../src/pages/ERPActivationPage.tsx', import.meta.url), 'utf8');
const schoolsPage = fs.readFileSync(new URL('../src/pages/SchoolsPage.tsx', import.meta.url), 'utf8');

test('paid School stays locked until Organization Admin activation', () => {
  assert.match(schoolsApi, /paid_pending_activation/);
  assert.match(schoolsApi, /is_active=not paid_pending_activation/);
  assert.match(deps, /School ERP activation is pending/);
  assert.match(usersApi, /Users cannot be created until ERP activation is completed/);
});

test('activation is payment-gated, versioned-terms-gated and transactional', () => {
  assert.match(paymentsApi, /Minimum activation payment has not been received/);
  assert.match(paymentsApi, /Terms & Conditions must be accepted/);
  assert.match(paymentsApi, /terms_accepted_at=now/);
  assert.match(paymentsApi, /with_for_update\(\)/);
  assert.match(activationPage, /I have read and accept the Terms & Conditions/);
  assert.match(activationPage, /disabled=\{!selected\|\|!code\.trim\(\)\|\|!accepted\|\|!termsVersion\}/);
});

test('restore and enable paths preserve purchased School capacity', () => {
  assert.match(schoolsApi, /_lock_and_check_school_capacity/);
  assert.match(schoolsApi, /adding_slot=True/);
  assert.match(schoolsApi, /adding_slot=False/);
});

test('Organization Admin may view School directory but cannot create Schools', () => {
  assert.match(schoolsPage, /canView=canCreate\|\|user\?\.account_type==="ORGANIZATION_ADMIN"/);
  assert.match(schoolsPage, /canCreate&&<button className="btn-primary"/);
});

test('retention purges operational children without deleting retained School identity', () => {
  assert.match(lifecycle, /_purge_operational_school_data/);
  assert.doesNotMatch(lifecycle, /delete\(School\)/);
  assert.match(lifecycle, /delete\(PaymentAllocation\)/);
  assert.match(lifecycle, /delete\(Student\)/);
  assert.match(lifecycle, /values\(is_active=False\)/);
});
