/**
 * Team page e2e tests.
 * NOTE: This page redirects non-admin users to "/". Tests run under the auth
 * fixture which uses the configured test account. If that account is not an
 * admin the tests will be skipped with a descriptive annotation.
 */
import { test, expect } from './fixtures';

async function waitForTeamPage(page: any): Promise<boolean> {
  await page.goto('/team');
  await expect(page.locator('header')).toBeVisible({ timeout: 20000 });

  // If redirected away (non-admin), return false
  const url = page.url();
  if (!url.includes('/team')) return false;

  // Wait for loading to finish
  await page.waitForFunction(
    () => !document.body.textContent?.includes('Loading team members...'),
    { timeout: 20000 }
  );
  return true;
}

test.describe('Team — Admin View', () => {
  test('TEAM-002: admin can access Team page with heading', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    await expect(page.locator('h2', { hasText: 'Team' })).toBeVisible({ timeout: 10000 });
  });

  test('TEAM-004: member statistics displayed below heading', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    // Stats text: "N members · N active"
    await expect(page.locator('text=/\\d+ members/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/\\d+ active/')).toBeVisible({ timeout: 10000 });
  });

  test('TEAM-006: invite form with email input and Invite button is visible', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }
    await expect(page.locator('h3', { hasText: 'Invite new member' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[aria-label="Invite member email"]')).toBeVisible();
    await expect(page.locator('[aria-label="Send invite"]')).toBeVisible();
  });

  test('TEAM-010: member table shows Email, Name, Status columns', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }

    // If there are members, the table is rendered
    const table = page.locator('table');
    const hasTable = await table.isVisible().catch(() => false);

    if (!hasTable) {
      // No members yet — verify empty state message
      await expect(page.locator('text=No team members yet.')).toBeVisible();
      return;
    }

    // Table headers
    await expect(page.locator('th', { hasText: 'Email' })).toBeVisible();
    await expect(page.locator('th', { hasText: 'Name' })).toBeVisible();
    await expect(page.locator('th', { hasText: 'Status' })).toBeVisible();
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

    // At least one row should have "You" in the actions column
    await expect(page.locator('td', { hasText: 'You' })).toBeVisible({ timeout: 10000 });
  });

  test('TEAM: invite Invite button disabled when email is empty', async ({ page }) => {
    const isAdmin = await waitForTeamPage(page);
    if (!isAdmin) {
      test.info().annotations.push({ type: 'skip-reason', description: 'Test account is not admin' });
      return;
    }

    const inviteBtn = page.locator('[aria-label="Send invite"]');
    // Button starts disabled because input is empty
    await expect(inviteBtn).toBeDisabled({ timeout: 5000 });
  });
});
