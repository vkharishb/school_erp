import { test, expect } from '@playwright/test';
import { loginPlatformOwner } from './helpers';

test.describe('Access control and locked modules', () => {
  test('Platform Owner sees platform-only commercial and system areas', async ({ page }) => {
    await loginPlatformOwner(page);
    await page.goto('/subscriptions');
    await expect(page.getByRole('heading', { name: 'Subscriptions' })).toBeVisible();
    await page.goto('/payments');
    await expect(page).not.toHaveURL(/\/login/);
    await page.goto('/system-settings');
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'System Settings' })).toBeVisible();
    await expect(page.getByText(/Normal Organization and School administrators cannot access System Settings/i)).toBeVisible();
  });

  test('module catalogue describes subscription-based entitlement and lock behavior', async ({ page }) => {
    await loginPlatformOwner(page);
    await page.goto('/schools');
    const school = page.locator('a[href^="/schools/"]').first();
    test.skip(await school.count() === 0, 'No School exists in the QA database.');
    const href = await school.getAttribute('href');
    const id = href?.split('/')[2];
    test.skip(!id, 'Could not resolve a School id.');
    await page.goto(`/schools/${id}/modules`);
    await expect(page.getByText(/Modules are subscription-based/i)).toBeVisible();
    await expect(page.getByText(/unavailable modules remain visible as locked/i)).toBeVisible();
  });
});
