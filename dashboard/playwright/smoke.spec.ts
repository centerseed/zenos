import { test, expect } from './fixtures';

test.describe('Smoke Tests', () => {
  test('knowledge-map page loads', async ({ page }) => {
    await page.goto('/knowledge-map');
    await expect(page).toHaveTitle(/ZenOS/);
    // Wait for Firebase auth + partner fetch + AppNav render
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    // ZenOS brand link in header
    await expect(page.locator('header a', { hasText: 'ZenOS' })).toBeVisible({ timeout: 5000 });
  });

  test('projects page loads', async ({ page }) => {
    await page.goto('/projects');
    await expect(page).toHaveTitle(/ZenOS/);
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  });

  test('tasks page loads', async ({ page }) => {
    await page.goto('/tasks');
    await expect(page).toHaveTitle(/ZenOS/);
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  });

  test('team page loads', async ({ page }) => {
    await page.goto('/team');
    await expect(page).toHaveTitle(/ZenOS/);
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  });

  test('clients page loads', async ({ page }) => {
    await page.goto('/clients');
    await expect(page).toHaveTitle(/ZenOS/);
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  });

  test('navigation links are present in desktop nav', async ({ page }) => {
    await page.goto('/knowledge-map');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });

    // Desktop nav (hidden md:flex) contains the main route links
    const desktopNav = page.locator('header nav').first();
    await expect(desktopNav.locator('a', { hasText: '知識地圖' })).toBeVisible();
    await expect(desktopNav.locator('a', { hasText: '專案' })).toBeVisible();
    await expect(desktopNav.locator('a', { hasText: '任務' })).toBeVisible();
    await expect(desktopNav.locator('a', { hasText: '客戶' })).toBeVisible();
  });

  test('navigation to projects page works', async ({ page }) => {
    await page.goto('/knowledge-map');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });

    const projectsLink = page.locator('header nav a', { hasText: '專案' }).first();
    await projectsLink.click();
    await page.waitForURL('**/projects');
    await expect(page).toHaveTitle(/ZenOS/);
  });
});
