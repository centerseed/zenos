import { test, expect } from './fixtures';

/**
 * Knowledge Map page interaction tests.
 *
 * Page structure (from page.tsx):
 * - AppNav (header with nav links)
 * - Left Sidebar (w-[230px]) with "Naruvia" heading and product filter buttons
 * - Main area with KnowledgeGraph (canvas)
 * - NodeDetailSheet shown when a node is selected
 *
 * Auth flow adds latency: Firebase IDB restore → onAuthStateChanged → partner fetch → render.
 * All assertions use generous timeouts to accommodate the network round-trip.
 */

const AUTH_TIMEOUT = 20000;

test.describe('Knowledge Map', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/knowledge-map');
    // Wait for Firebase auth + partner data fetch + AppNav to render
    await expect(page.locator('header')).toBeVisible({ timeout: AUTH_TIMEOUT });
  });

  test('sidebar displays after data loads', async ({ page }) => {
    // Sidebar shows "All Products" button once entities are fetched from API
    const allProductsBtn = page.locator('button', { hasText: 'All Products' });
    await expect(allProductsBtn).toBeVisible({ timeout: 15000 });
  });

  test('product filter button is clickable', async ({ page }) => {
    const allProductsBtn = page.locator('button', { hasText: 'All Products' });
    await expect(allProductsBtn).toBeVisible({ timeout: 15000 });

    // Clicking "All Products" should not crash the page
    await allProductsBtn.click();
    // Header should still be intact
    await expect(page.locator('header')).toBeVisible();
  });

  test('mobile menu toggle works', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/knowledge-map');
    await expect(page.locator('header')).toBeVisible({ timeout: AUTH_TIMEOUT });

    const menuBtn = page
      .locator('header button[aria-label="Open menu"]')
      .or(page.locator('header button[aria-label="開啟選單"]'))
      .or(page.locator('button', { hasText: 'Menu' }).first());
    await expect(menuBtn).toBeVisible({ timeout: 10000 });

    await menuBtn.click();
    const closeBtn = page
      .locator('header button[aria-label="Close menu"]')
      .or(page.locator('header button[aria-label="關閉選單"]'))
      .or(page.locator('button', { hasText: 'Close' }).first());
    await expect(closeBtn).toBeVisible({ timeout: 10000 });

    await closeBtn.click();
    await expect(menuBtn).toBeVisible({ timeout: 10000 });
  });

  test('page title is ZenOS', async ({ page }) => {
    await expect(page).toHaveTitle(/ZenOS/);
  });
});
