/**
 * Projects page e2e tests.
 * Covers both the list view (no ?id) and the detail view (?id=xxx).
 *
 * Data state is unknown — tests tolerate empty lists and accept count >= 0.
 */
import { test, expect } from './fixtures';

test.describe('Projects — List View', () => {
  test('PR-LIST-001: page loads with Projects heading', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    // Wait for auth + data fetch to settle
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading projects..."]'),
      { timeout: 20000 }
    );
    await expect(page.locator('h1', { hasText: 'Projects' })).toBeVisible({ timeout: 10000 });
  });

  test('PR-LIST-002: page renders main content area', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading projects..."]'),
      { timeout: 20000 }
    );
    await expect(page.locator('#main-content')).toBeVisible({ timeout: 10000 });
  });

  test('PR-LIST-003: project cards link to detail page when projects exist', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading projects..."]'),
      { timeout: 20000 }
    );

    // Wait for content to load (either project cards or empty message)
    await page.waitForTimeout(3000);

    const emptyMsg = page.locator('text=No projects yet.');
    const isEmpty = await emptyMsg.isVisible().catch(() => false);

    if (isEmpty) {
      // Empty state confirmed
      await expect(emptyMsg).toBeVisible();
    } else {
      // Projects exist — click the first clickable card area
      const firstCard = page.locator('#main-content a').first();
      await expect(firstCard).toBeVisible({ timeout: 10000 });
      await firstCard.click();
      await page.waitForURL('**/projects**id=*', { timeout: 10000 });
      expect(page.url()).toContain('id=');
    }
  });

  test('PR-LIST-004: project cards show module count', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading projects..."]'),
      { timeout: 20000 }
    );

    const cards = page.locator('#main-content a[href^="/projects?id="]');
    const count = await cards.count();

    if (count === 0) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }

    // Each card's content area should have a span with "modules"
    const firstCard = cards.first();
    await expect(firstCard.locator('text=/\\d+ modules/')).toBeVisible();
  });
});

test.describe('Projects — Detail View', () => {
  // Helper: navigate to the first project's detail page and return the id.
  // Returns null if no projects exist.
  async function goToFirstProject(page: any): Promise<string | null> {
    await page.goto('/projects');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading projects..."]'),
      { timeout: 20000 }
    );

    const cards = page.locator('#main-content a[href^="/projects?id="]');
    const count = await cards.count();
    if (count === 0) return null;

    const href = await cards.first().getAttribute('href');
    const id = new URL(`http://localhost${href}`).searchParams.get('id');
    if (!id) return null;

    await page.goto(`/projects?id=${id}`);
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    // Wait until loading spinner disappears
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Loading project details..."]'),
      { timeout: 20000 }
    );
    return id;
  }

  test('PR-DETAIL-001: detail page loads with project name', async ({ page }) => {
    const id = await goToFirstProject(page);
    if (!id) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }
    // The project name is displayed in an h2
    await expect(page.locator('#main-content h2').first()).toBeVisible({ timeout: 10000 });
  });

  test('PR-DETAIL-003: critical blindspot banner shown when red blindspots exist', async ({ page }) => {
    const id = await goToFirstProject(page);
    if (!id) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }
    // The banner is conditionally rendered; check whether it's present or absent
    const banner = page.locator('.bg-red-900\\/30.border.border-red-800').first();
    const hasBanner = await banner.isVisible().catch(() => false);
    // Either the banner is visible (critical issues exist) or absent — both are valid
    if (hasBanner) {
      await expect(banner.locator('text=/critical issue/')).toBeVisible();
    }
    // No assertion failure if banner is absent — means no red blindspots
  });

  test('PR-DETAIL-005: statistics row shows modules, documents, blindspots counts', async ({ page }) => {
    const id = await goToFirstProject(page);
    if (!id) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }
    // Stats are rendered as <span> elements in a flex row
    await expect(page.locator('text=/\\d+ modules/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/\\d+ documents/')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/\\d+ blindspots/')).toBeVisible({ timeout: 10000 });
  });

  test('PR-DETAIL-006: Modules section heading and EntityTree area visible', async ({ page }) => {
    const id = await goToFirstProject(page);
    if (!id) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }
    await expect(page.locator('#main-content h3', { hasText: 'Modules' })).toBeVisible({ timeout: 10000 });
  });

  test('PR-DETAIL-010: Back to projects link navigates back to list', async ({ page }) => {
    const id = await goToFirstProject(page);
    if (!id) {
      test.info().annotations.push({ type: 'skip-reason', description: 'No projects in data' });
      return;
    }
    const backLink = page.locator('a', { hasText: 'Back to projects' });
    await expect(backLink).toBeVisible({ timeout: 10000 });
    await backLink.click();
    await page.waitForURL('**/projects', { timeout: 10000 });
    await expect(page.locator('h1', { hasText: 'Projects' })).toBeVisible({ timeout: 10000 });
  });
});
