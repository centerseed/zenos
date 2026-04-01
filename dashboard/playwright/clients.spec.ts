/**
 * Clients page e2e tests.
 * Covers the Kanban board, summary stats, new-deal modal, and company list link.
 *
 * Data state is unknown — tests tolerate empty boards.
 */
import { test, expect } from './fixtures';

const FUNNEL_STAGES = ['潛在客戶', '需求訪談', '提案報價', '合約議價', '導入中', '結案'];

test.describe('Clients — Kanban Board', () => {
  async function waitForBoard(page: any) {
    await page.goto('/clients');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    // Wait for loading spinner to disappear
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="載入商機看板..."]') &&
             !document.body.textContent?.includes('載入商機看板...'),
      { timeout: 20000 }
    );
  }

  test('CLIENT-002: page loads and shows 客戶 heading', async ({ page }) => {
    await waitForBoard(page);
    await expect(page.locator('h2', { hasText: '客戶' })).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-003: summary stats cards show three metrics', async ({ page }) => {
    await waitForBoard(page);
    // Stats are in a 3-column grid; check the labels
    await expect(page.locator('text=進行中商機')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=本月新增')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=成交案值')).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-004: + 新增商機 button opens NewDealModal', async ({ page }) => {
    await waitForBoard(page);
    const addButton = page.locator('button', { hasText: '+ 新增商機' });
    await expect(addButton).toBeVisible({ timeout: 10000 });
    await addButton.click();

    // Modal header
    await expect(page.locator('h3', { hasText: '新增商機' })).toBeVisible({ timeout: 5000 });
  });

  test('CLIENT-005: 公司列表 link navigates to companies page', async ({ page }) => {
    await waitForBoard(page);
    const companiesLink = page.locator('a', { hasText: '公司列表' });
    await expect(companiesLink).toBeVisible({ timeout: 10000 });
    // Verify href
    const href = await companiesLink.getAttribute('href');
    expect(href).toContain('/clients/companies');
  });

  test('CLIENT-008: Kanban board shows all six funnel stage columns', async ({ page }) => {
    await waitForBoard(page);
    for (const stage of FUNNEL_STAGES) {
      // Each column header renders the stage name as text
      await expect(page.locator(`text=${stage}`).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('CLIENT-010: deal cards are draggable elements (cursor-grab)', async ({ page }) => {
    await waitForBoard(page);
    // The draggable wrapper has class cursor-grab
    const draggables = page.locator('.cursor-grab');
    const count = await draggables.count();
    if (count === 0) {
      // No deals; verify empty column placeholder text exists
      const placeholders = page.locator('text=拖曳商機至此');
      await expect(placeholders.first()).toBeVisible({ timeout: 10000 });
    } else {
      // At least one draggable deal card is present
      await expect(draggables.first()).toBeVisible();
    }
  });
});

test.describe('Clients — NewDealModal', () => {
  async function openModal(page: any) {
    await page.goto('/clients');
    await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.body.textContent?.includes('載入商機看板...'),
      { timeout: 20000 }
    );
    const addButton = page.locator('button', { hasText: '+ 新增商機' });
    await expect(addButton).toBeVisible({ timeout: 10000 });
    await addButton.click();
    await expect(page.locator('h3', { hasText: '新增商機' })).toBeVisible({ timeout: 5000 });
  }

  test('CLIENT-DEAL-001: NewDealModal shows title input and company select', async ({ page }) => {
    await openModal(page);
    await expect(page.locator('label', { hasText: '商機標題' })).toBeVisible();
    await expect(page.locator('label', { hasText: '所屬公司' })).toBeVisible();
  });

  test('CLIENT-DEAL-003: submitting with empty title shows validation error', async ({ page }) => {
    await openModal(page);
    // Click submit without filling anything
    await page.locator('button[type="submit"]', { hasText: '建立商機' }).click();
    await expect(page.locator('text=請輸入商機標題')).toBeVisible({ timeout: 5000 });
  });

  test('CLIENT-DEAL-008: modal closes on 取消 button click', async ({ page }) => {
    await openModal(page);
    await page.locator('button', { hasText: '取消' }).click();
    // Modal should be gone
    await expect(page.locator('h3', { hasText: '新增商機' })).not.toBeVisible({ timeout: 5000 });
  });

  test('CLIENT-DEAL: selecting NEW_COMPANY shows new company name field', async ({ page }) => {
    await openModal(page);
    // Select the "+ 新增新公司..." option
    await page.locator('select').first().selectOption('NEW_COMPANY');
    await expect(page.locator('label', { hasText: '新公司名稱' })).toBeVisible({ timeout: 5000 });
  });
});
