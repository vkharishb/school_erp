import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const schools = fs.readFileSync(new URL('../src/pages/SchoolsPage.tsx', import.meta.url), 'utf8');
const modules = fs.readFileSync(new URL('../src/pages/ModulesPage.tsx', import.meta.url), 'utf8');
const years = fs.readFileSync(new URL('../src/pages/AcademicYearsPage.tsx', import.meta.url), 'utf8');

test('school list shows School Admin and activation summary', () => {
  assert.match(schools, /School Activation/);
  assert.match(schools, /Activated \/ Total Schools/);
  assert.match(schools, /account_type==="SCHOOL_ADMIN"/);
  assert.match(schools, /activation_status/);
});

test('school capacity increase stays on the capacity page', () => {
  assert.match(schools, /Increase School Limit/);
  assert.match(schools, /organizationApi\.update/);
  assert.doesNotMatch(schools, /action=increase-school-limit/);
});

test('module catalogue derives effective state from assigned plan', () => {
  assert.match(modules, /subscriptionApi\.plans/);
  assert.match(modules, /planModules/);
  assert.match(modules, /Enabled/);
  assert.match(modules, /Disabled · Not in plan/);
  assert.match(modules, /Locked · Not implemented/);
  assert.match(modules, /Sync Modules with Plan/);
});

test('academic year page exposes draft active history and rollover workflow', () => {
  assert.match(years, /Current Academic Year/);
  assert.match(years, /Draft \/ Upcoming/);
  assert.match(years, /Historical Years/);
  assert.match(years, /Activate \/ Rollover/);
  assert.match(years, /previous Active year is now preserved as read-only history/);
});

test('trial School Capacity is fixed at one and School List shows plan', () => {
  assert.match(schools, /billing_cycle==="trial"/);
  assert.match(schools, /Trial is fixed at one School/);
  assert.match(schools, /effectiveLimit/);
  assert.match(schools, /<th className="pr-4">Plan<\/th>/);
  assert.match(schools, /sub\?\.plan_name\|\|orgAct\?\.plan_name\|\|"Not assigned"/);
});

test('school capacity enforces trial and exhausted-limit rules', () => {
  assert.match(schools, /Trial is fixed at one School/);
  assert.match(schools, /Schools Created/);
  assert.match(schools, /School Limit/);
  assert.match(schools, /Available Slots/);
  assert.match(schools, /disabled=\{trial\|\|!exhausted\}/);
  assert.match(schools, /Increase Limit stays disabled while any School slot is available/);
});

test('trial conversion is exposed beside school lifecycle actions', () => {
  const detail = fs.readFileSync(new URL('../src/pages/SchoolDetailPage.tsx', import.meta.url), 'utf8');
  const subscriptions = fs.readFileSync(new URL('../src/pages/SubscriptionsPage.tsx', import.meta.url), 'utf8');
  assert.match(detail, /Convert Trial to Paid Plan/);
  assert.match(detail, /Converted to Paid Plan/);
  assert.match(detail, /Paid School Limit after conversion/);
  assert.match(subscriptions, /Convert Trial to Paid Plan/);
  assert.match(subscriptions, /Converted to Paid Plan/);
});

test('capacity increase captures effective date, reason and incremental discount only', () => {
  assert.match(schools, /Capacity Effective Date is required/);
  assert.match(schools, /capacity_effective_at/);
  assert.match(schools, /capacity_reason/);
  assert.match(schools, /capacity_discount_type/);
  assert.match(schools, /Only the additional School slots are charged/);
  assert.match(schools, /prorated from the Effective Date/);
});

test('module allocation is server-bound to the assigned plan', () => {
  const api = fs.readFileSync(new URL('../../backend/app/api/v1/schools.py', import.meta.url), 'utf8');
  assert.match(api, /School modules must exactly match the assigned plan/);
  assert.match(api, /plan_for_school/);
  assert.match(api, /effective_modules\(plan/);
});

test('school profile exposes governed logo upload', () => {
  const detail = fs.readFileSync(new URL('../src/pages/SchoolDetailPage.tsx', import.meta.url), 'utf8');
  const api = fs.readFileSync(new URL('../src/services/api.ts', import.meta.url), 'utf8');
  const backend = fs.readFileSync(new URL('../../backend/app/api/v1/schools.py', import.meta.url), 'utf8');
  const main = fs.readFileSync(new URL('../../backend/app/main.py', import.meta.url), 'utf8');
  assert.match(detail, /School Logo/);
  assert.match(detail, /type="file"/);
  assert.match(detail, /accept="image\/png,image\/jpeg,image\/webp"/);
  assert.match(detail, /Upload Logo/);
  assert.match(api, /\/schools\/\$\{schoolId\}\/logo/);
  assert.match(backend, /upload_school_logo/);
  assert.match(backend, /school\.logo\.uploaded/);
  assert.match(backend, /Logo must be PNG, JPG or WEBP/);
  assert.match(main, /app\.mount\("\/uploads"/);
});