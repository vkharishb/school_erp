import { expect, Page } from '@playwright/test';

export const creds = {
  username: process.env.E2E_SUPER_ADMIN_USERNAME || '',
  password: process.env.E2E_SUPER_ADMIN_PASSWORD || '',
};

export function requireCredentials() {
  if (!creds.username || !creds.password) {
    throw new Error('Set E2E_SUPER_ADMIN_USERNAME and E2E_SUPER_ADMIN_PASSWORD before running Playwright.');
  }
}

export async function loginPlatformOwner(page: Page) {
  requireCredentials();
  await page.goto('/login');
  await page.locator('#accountType').selectOption('SUPER_ADMIN');
  await page.locator('#username').fill(creds.username);
  await page.locator('#password').fill(creds.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login$/);
}

export async function approveChangeDialogs(page: Page, reason = 'Playwright E2E QA validation') {
  page.on('dialog', async dialog => {
    if (dialog.type() === 'confirm') await dialog.accept();
    else if (dialog.type() === 'prompt') await dialog.accept(reason);
    else await dialog.dismiss();
  });
}

export async function expectNoServerErrors(page: Page) {
  const errors: string[] = [];
  page.on('response', r => { if (r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });
  return async () => expect(errors, `Unexpected HTTP 5xx responses:\n${errors.join('\n')}`).toEqual([]);
}
