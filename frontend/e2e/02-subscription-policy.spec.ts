import { test, expect } from '@playwright/test';
import { loginPlatformOwner } from './helpers';

test.describe('Subscription policy', () => {
  test.beforeEach(async ({ page }) => { await loginPlatformOwner(page); await page.goto('/subscriptions'); });

  test('subscription lifecycle and Trial restrictions are visible', async ({ page }) => {
    await expect(page.getByText(/Plan catalog.*Organization subscription.*School entitlement.*Activation key.*ERP activation/i)).toBeVisible();
    await expect(page.getByText(/Platform Owner.*each plan/i)).toBeVisible();
    await expect(page.getByText(/Trial.*30 days.*no activation key.*blocks all downloads\/exports/i)).toBeVisible();
  });

  test('plan catalog exposes BASIC, STANDARD, PREMIUM, CUSTOMIZED and PAYG when seeded', async ({ page }) => {
    for (const code of ['BASIC', 'STANDARD', 'PREMIUM', 'CUSTOMIZED', 'PAYG']) {
      await expect(page.getByText(code, { exact: true })).toBeVisible();
    }
  });

  test('commercial tabs are available to Platform Owner', async ({ page }) => {
    for (const tab of ['plans', 'subscriptions', 'entitlements', 'keys', 'renewals', 'reminders']) {
      await expect(page.getByRole('button', { name: tab, exact: true })).toBeVisible();
    }
  });
});
