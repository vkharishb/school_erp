import { test, expect } from '@playwright/test';

test.describe('API security smoke tests through the browser origin', () => {
  test('protected API rejects anonymous access', async ({ request }) => {
    const response = await request.get('/api/v1/auth/me');
    expect([401, 403]).toContain(response.status());
  });

  test('malformed login payload is rejected without 5xx', async ({ request }) => {
    const response = await request.post('/api/v1/auth/login/json', { data: { account_type: 'SUPER_ADMIN', username: "' OR 1=1 --", password: 'x' } });
    expect(response.status()).toBeLessThan(500);
    expect([401, 422, 429]).toContain(response.status());
  });
});
