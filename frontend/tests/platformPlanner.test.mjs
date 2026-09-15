import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("Platform Owner planner is routed, linked and backed by API contracts", async () => {
  const [app, sidebar, page, api, types, router, catalog, migration] = await Promise.all([
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/components/shell/AppSidebar.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/PlannerPage.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/services/api.ts", import.meta.url), "utf8"),
    readFile(new URL("../src/types/index.ts", import.meta.url), "utf8"),
    readFile(new URL("../../backend/app/api/v1/router.py", import.meta.url), "utf8"),
    readFile(new URL("../../backend/app/core/platform_catalog.py", import.meta.url), "utf8"),
    readFile(new URL("../../backend/alembic/versions/032_platform_planner.py", import.meta.url), "utf8"),
  ]);

  assert.match(app, /path="planner" element={<SuperuserRoute><PlannerPage\/><\/SuperuserRoute>}/);
  assert.match(sidebar, /label:"Planner",to:"\/planner"/);
  assert.equal((sidebar.match(/label:"Planner"/g) || []).length, 1);
  assert.match(page, /Calendar Planner/);
  assert.match(page, /plannerApi\.agenda\(45\)/);
  assert.match(page, /plannerApi\.complete/);
  assert.match(api, /export const plannerApi/);
  assert.match(api, /"\/planner\/agenda"/);
  assert.match(api, /`\/planner\/items\/\$\{id\}\/complete`/);
  assert.match(types, /export interface PlannerAgenda/);
  assert.match(router, /include_router\(planner\.router\)/);
  assert.match(catalog, /"code": "planner"/);
  assert.match(migration, /platform_planner_items/);
});
