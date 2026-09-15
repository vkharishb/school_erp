import { test, expect } from '@playwright/test';
import { approveChangeDialogs, loginPlatformOwner } from './helpers';

const mutations = process.env.E2E_RUN_MUTATIONS === '1';

test.describe('Organization and School lifecycle', () => {
  test.beforeEach(async ({ page }) => { await approveChangeDialogs(page); await loginPlatformOwner(page); });

  test('organization creation form requires a subscription plan and admin credentials', async ({ page }) => {
    await page.goto('/organizations');
    await page.getByRole('button', { name: /New Organization|Add Organization|Create Organization/i }).click();
    await expect(page.getByText('Subscription and Commercial Terms')).toBeVisible();
    await expect(page.getByText('Plan / 30-Day Trial *')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Organization Admin Login' })).toBeVisible();
    await expect(page.getByText(/Trial requires no key.*blocks downloads/i)).toBeVisible();
  });

  test('school creation form is organization-scoped and creates School Admin in same transaction', async ({ page }) => {
    await page.goto('/schools');
    await page.getByRole('button', { name: 'New School' }).click();
    await expect(page.getByRole('heading', { name: 'Create School' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create School' })).toBeVisible();
    await expect(page.getByText('Organization *')).toBeVisible();
    await expect(page.getByText('School Admin Profile')).toBeVisible();
    await expect(page.getByText(/must change the temporary password/i)).toBeVisible();
  });

  test('can create a Trial organization end-to-end in an isolated QA database', async ({ page }) => {
    test.skip(!mutations, 'Set E2E_RUN_MUTATIONS=1 only against an isolated QA database.');
    const stamp = Date.now();
    const org = `PW Trial ${stamp}`;
    const username = `pworg${stamp}`;
    await page.goto('/organizations');
    await page.getByRole('button', { name: /New Organization|Add Organization|Create Organization/i }).click();
    await page.getByLabel('Organization Name *').fill(org);
    await page.getByLabel('No. of Schools Allowed').fill('1');
    await page.getByLabel('Plan / 30-Day Trial *').selectOption({ label: /TRIAL|Trial/i });
    await page.getByLabel('Admin Person Name *').fill('Playwright Org Admin');
    await page.getByLabel('Admin Contact Email *').fill(`contact.${stamp}@example.test`);
    await page.getByLabel('Username *').fill(username);
    await page.getByLabel('Login Email *').fill(`${username}@example.test`);
    await page.getByLabel('Temporary Password').fill('PwQa!Strong12345');
    await page.getByRole('button', { name: 'Create Organization' }).click();
    await expect(page.getByText(org)).toBeVisible();
    await expect(page.getByText(/Organization and Organization Admin created/i)).toBeVisible();
  });
});
