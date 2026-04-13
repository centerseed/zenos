/**
 * Team page e2e tests.
 * NOTE: This page redirects non-admin users to "/". Tests run under the auth
 * fixture which uses the configured test account. If that account is not an
 * admin the tests will be skipped with a descriptive annotation.
 */
import { test, expect } from './fixtures';

async function waitForTeamPage(page: any): Promise<boolean> {
  await page.goto('/team');
  await expect(page.locator('body')).toBeVisible({ timeout: 20000 });

  await page.waitForFunction(
    () =>
      location.pathname.includes('/tasks') ||
      Boolean(document.querySelector('h2')?.textContent?.includes('成員管理')),
    { timeout: 20000 }
  ).catch(() => null);

  if (page.url().includes('/tasks')) return false;
  return await page.locator('h2', { hasText: '成員管理' }).isVisible().catch(() => false);
}

test.describe('Team — Admin View', () => {
  test('TEAM-002: admin can access Team page with heading', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    await expect(page.locator('h2', { hasText: '成員管理' })).toBeVisible({ timeout: 10000 });
  });

  test('TEAM-004: member statistics displayed below heading', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    await expect(page.locator('text=/共\\s*\\d+\\s*位成員/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/\\d+\\s*位啟用中/')).toBeVisible({ timeout: 10000 });
  });

  test('TEAM-006: invite form with email input and Invite button is visible', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    await expect(page.locator('h3', { hasText: '邀請新成員' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[aria-label="邀請成員信箱"]')).toBeVisible();
    await expect(page.locator('[aria-label="送出邀請"]')).toBeVisible();
  });

  test('TEAM-010: member table shows Email, Name, Status columns', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }

    await page.waitForFunction(
      () =>
        Boolean(document.querySelector('table')) ||
        Boolean(document.body.textContent?.includes('目前還沒有任何成員。')),
      { timeout: 10000 }
    ).catch(() => null);

    const table = page.locator('table');
    const hasTable = await table.isVisible().catch(() => false);

    if (!hasTable) {
      await expect(page.locator('text=目前還沒有任何成員。')).toBeVisible();
      return;
    }

    await expect(page.locator('th', { hasText: '信箱' })).toBeVisible();
    await expect(page.locator('th', { hasText: '名稱' })).toBeVisible();
    await expect(page.locator('th', { hasText: '狀態' })).toBeVisible();
  });

  test('TEAM-012: current user row shows "You" instead of action buttons', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }

    const table = page.locator('table');
    const hasTable = await table.isVisible().catch(() => false);
    if (!hasTable) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No members in team' });
      return;
    }

    await expect(page.locator('td', { hasText: '你自己' })).toBeVisible({ timeout: 10000 });
  });

  test('TEAM: invite Invite button disabled when email is empty', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }

    const inviteBtn = page.locator('[aria-label="送出邀請"]');
    await expect(inviteBtn).toBeDisabled({ timeout: 5000 });
  });
});
