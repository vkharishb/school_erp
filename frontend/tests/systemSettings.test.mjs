import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("system settings exposes platform status, version, module checklist and lower-environment reset", async () => {
  const page = await readFile(new URL("../src/pages/SystemSettingsPage.tsx", import.meta.url), "utf8");
  const api = await readFile(new URL("../src/services/api.ts", import.meta.url), "utf8");
  assert.match(page, /Platform Status/);
  assert.match(page, /Platform Version/);
  assert.match(page, /Platform Module Status Checklist/);
  assert.match(page, /Development Data Reset/);
  assert.match(api, /\/system\/platform-status/);
  assert.match(api, /\/system\/development-reset/);
});
