import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Platform Owner has separate Payments and Subscriptions modules", async () => {
  const [sidebar, app] = await Promise.all([
    readFile(new URL("../src/components/shell/AppSidebar.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(sidebar, /label:"Payments",to:"\/payments"/);
  assert.match(sidebar, /label:"Subscriptions",to:"\/subscriptions"/);
  assert.match(app, /path="payments" element={<SuperuserRoute>/);
  assert.match(app, /path="subscriptions" element={<SuperuserRoute>/);
});

test("Organization Admin activation is isolated from School Admin", async () => {
  const [sidebar, app, page] = await Promise.all([
    readFile(new URL("../src/components/shell/AppSidebar.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/ERPActivationPage.tsx", import.meta.url), "utf8"),
  ]);
  assert.match(sidebar, /user\?\.account_type==="ORGANIZATION_ADMIN"/);
  assert.match(app, /OrganizationAdminRoute/);
  assert.match(page, /Payment and financial details remain with the Platform Owner/);
});

test("Trial UX documents restricted access, no keys and no exports", async () => {
  const source = await readFile(new URL("../src/pages/SubscriptionsPage.tsx", import.meta.url), "utf8");
  assert.match(source, /blocks all downloads\/exports/);
  assert.match(source, /needs no activation key/);
});

test("Subscriptions cleanup batch 1 replaces prompts with governed actions", async () => {
  const [page, api, schemas, backend] = await Promise.all([
    readFile(new URL("../src/pages/SubscriptionsPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/services/api.ts", import.meta.url), "utf8"),
    readFile(new URL("../../backend/app/schemas/subscription.py", import.meta.url), "utf8"),
    readFile(new URL("../../backend/app/api/v1/payments.py", import.meta.url), "utf8"),
  ]);
  assert.doesNotMatch(page, /window\.prompt/);
  assert.match(page, /Convert Trial/);
  assert.match(page, /Key History/);
  assert.match(page, /Revoke Reason/);
  assert.match(page, /Disable Reason/);
  assert.match(page, /Module Catalog/);
  assert.match(page, /Modules included in this plan/);
  assert.match(page, /Selected modules for this plan/);
  assert.match(page, /communication/);
  assert.match(page, /Planned/);
  assert.match(page, /setTab\(requestedTab\);setShowPlan\(false\);setAction\(null\);/);
  assert.match(api, /activationKeys/);
  assert.match(api, /revokeKey/);
  assert.match(api, /disableSchool: async \(id:string,reason:string\)/);
  assert.match(schemas, /class SchoolSubscriptionDisable/);
  assert.match(backend, /subscription\.activation_key\.revoked/);
  assert.match(backend, /Payment Due Date is required when converting Trial to a paid plan/);
  assert.match(backend, /Reason is required when Minimum Activation Payment is below the calculated minimum/);
});