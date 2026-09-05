import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("student bulk import uses campus only and per-row academic placement", async () => {
  const source = await readFile(new URL("../src/pages/BulkImportsPage.tsx", import.meta.url), "utf8");
  assert.equal(source.includes("Student Import Setup"), false);
  assert.equal(source.includes("Students must be imported into an existing Academic Year, Class and Section"), false);
  assert.match(source, /const studentContext=useMemo\(\(\)=>\(\{campus_id:campusId\}\)/);
  assert.match(source, /Each student row contains its own Academic Year, Class and Section/);
  assert.match(source, /Create \/ Manage Classes & Sections/);
  assert.match(source, /to=\{`\/schools\/\$\{schoolId\}\/classes-sections`\}/);
});
