import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const page=readFileSync(new URL('../src/pages/SubscriptionsPage.tsx', import.meta.url),'utf8');
const api=readFileSync(new URL('../src/services/api.ts', import.meta.url),'utf8');
test('Organization Subscriptions exposes start/end/grace and Send Reminder',()=>{
  for(const text of ['Start Date','End Date','Grace Until','Send Reminder']) assert.match(page,new RegExp(text));
  assert.match(page,/actionLabel="Reminder"/);
});
test('renewal separates renew, exceptional extension and Trial conversion',()=>{
  for(const text of ['Convert to Paid Plan','Renew','Extend Expiry','Communicated with']) assert.match(page,new RegExp(text));
  assert.match(api,/accounts\/\$\{id\}\/extend/);
});
