import { test, expect } from '@playwright/test';
import { loginPlatformOwner } from './helpers';

test.describe('Phase A - A3 Global Confirmation Policy', () => {
  test('Create Society/Trust must NOT show confirmation or prompt dialog', async ({ page }) => {
    const unexpectedDialogs: string[] = [];

    page.on('dialog', async (dialog) => {
      if (dialog.type() === 'confirm' || dialog.type() === 'prompt') {
        unexpectedDialogs.push(
          `${dialog.type()}: ${dialog.message()}`
        );

        // Prevent an unexpected confirmation from completing the mutation.
        await dialog.dismiss();
        return;
      }

      await dialog.dismiss();
    });

    await loginPlatformOwner(page);
    await page.goto('/organizations');

    await page
      .getByRole('button', { name: 'Add Society/Trust' })
      .click();

    const stamp = Date.now();

    await page.getByLabel('Society/Trust Name *')
      .fill(`PW A3 Baseline ${stamp}`);

    await page.getByLabel('Number of Schools *')
      .fill('1');

    await page.getByLabel('Admin Person Name *')
      .fill('Playwright Phase A Admin');

    await page.getByLabel('Designation *')
      .fill('Group Admin');

    await page.getByLabel('Admin Contact / Login Email *')
      .fill(`pw.a3.${stamp}@example.test`);

    await page.getByLabel('Admin Phone *')
      .fill('9876543210');

    await page.getByLabel('Username *')
      .fill(`pwa3${stamp}`);

    await page.getByLabel('Plan *')
      .selectOption({ label: /Trial/i });

    const createButton = page.getByRole('button', {
      name: 'Create Society/Trust',
    });

    await expect(createButton).toBeVisible();
    await createButton.click();

    await page.waitForTimeout(500);

    expect(
      unexpectedDialogs,
      [
        'A3 GLOBAL CONFIRMATION POLICY VIOLATION',
        'Create/Save/Edit/Update/Activate/Enable/Disable and other',
        'non-delete operations must execute without confirmation.',
        '',
        `Detected dialogs: ${unexpectedDialogs.join(' | ')}`,
      ].join('\n')
    ).toEqual([]);
  });
});