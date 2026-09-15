import { test, expect } from '@playwright/test';
import { loginPlatformOwner, expectNoServerErrors } from './helpers';

test.describe('Authentication and Platform Owner navigation', () => {
  test('unauthenticated protected route redirects to login', async ({ page }) => {
    await page.goto('/subscriptions');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });

  test('Platform Owner can sign in and access governance modules', async ({ page }) => {
    const verifyNo5xx = await expectNoServerErrors(page);
    await loginPlatformOwner(page);
    await expect(page.getByText(/Dashboard/i).first()).toBeVisible();

    for (const route of ['/organizations', '/schools', '/payments', '/subscriptions', '/system-settings']) {
      await test.step(`Platform Owner opens ${route}`, async () => {
        await page.goto(route);
        await expect(page, `Platform Owner was redirected while accessing ${route}`).not.toHaveURL(/\/login/);
      });
    }
    await verifyNo5xx();
  });

  test('invalid password is rejected without exposing protected UI', async ({ page }) => {
    const user = process.env.E2E_SUPER_ADMIN_USERNAME;
    test.skip(!user, 'E2E_SUPER_ADMIN_USERNAME is required');
    await page.goto('/login');
    await page.locator('#accountType').selectOption('SUPER_ADMIN');
    await page.locator('#username').fill(user!);
    await page.locator('#password').fill('Definitely-Wrong-Password-123!');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText(/Login failed|incorrect|invalid/i)).toBeVisible();
  });
});
