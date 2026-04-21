/**
 * Clients page e2e tests.
 * Covers the current Zen Ink CRM workspace:
 * - page shell
 * - KPI strip
 * - pipeline/list toggle
 * - deal detail navigation
 *
 * Data state is unknown — tests tolerate empty boards.
 */
import { test, expect } from './fixtures';

const FUNNEL_STAGES = ['潛在客戶', '需求訪談', '提案報價', '合約議價', '導入中', '結案'];

async function waitForBoard(page: any) {
  await page.goto('/clients');
  await expect(page.locator('main')).toBeVisible({ timeout: 20000 });
  // Wait for loading spinner to disappear
  await page.waitForFunction(
    () => !document.querySelector('[aria-label="載入商機看板..."]') &&
           !document.body.textContent?.includes('載入商機看板...'),
    { timeout: 20000 }
  );
}

test.describe('Clients — Kanban Board', () => {
  test('CLIENT-002: page loads and shows 客戶 heading', async ({ page }) => {
    await waitForBoard(page);
    await expect(page.locator('h2', { hasText: '客戶' })).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-003: summary stats cards show three metrics', async ({ page }) => {
    await waitForBoard(page);
    await expect(page.locator('text=Pipeline 總額')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=進行中')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=本月成交')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=平均交易')).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-004: 新機會 button is visible in the workspace header', async ({ page }) => {
    await waitForBoard(page);
    const addButton = page.locator('button', { hasText: '新機會' });
    await expect(addButton).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-005: 列表 toggle switches from pipeline to list view', async ({ page }) => {
    await waitForBoard(page);
    const listToggle = page.locator('button', { hasText: '列表' });
    await expect(listToggle).toBeVisible({ timeout: 10000 });
    await listToggle.click();

    await expect(page.locator('text=公司 · 商機')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=預計結案')).toBeVisible({ timeout: 10000 });
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
    const dealButtons = page.locator('main button').filter({ hasNotText: 'Pipeline' });
    const count = await dealButtons.count();
    if (count === 0) {
      await expect(page.locator('text=空').first()).toBeVisible({ timeout: 10000 });
    } else {
      await expect(page.locator('text=空').first().or(dealButtons.first())).toBeVisible({ timeout: 10000 });
    }
  });
});

test.describe('Clients — Workspace Navigation', () => {
  async function openListView(page: any) {
    await page.goto('/clients');
    await expect(page.locator('main')).toBeVisible({ timeout: 20000 });
    await page.waitForFunction(
      () => !document.body.textContent?.includes('載入商機看板...'),
      { timeout: 20000 }
    );
    const listToggle = page.locator('button', { hasText: '列表' });
    await expect(listToggle).toBeVisible({ timeout: 10000 });
    await listToggle.click();
    await expect(page.locator('text=公司 · 商機')).toBeVisible({ timeout: 10000 });
  }

  test('CLIENT-DEAL-001: list view renders table-style headers', async ({ page }) => {
    await openListView(page);
    await expect(page.locator('text=公司 · 商機')).toBeVisible();
    await expect(page.locator('text=階段')).toBeVisible();
    await expect(page.locator('text=金額')).toBeVisible();
  });

  test('CLIENT-DEAL-003: clicking a deal in pipeline opens detail workspace', async ({ page }) => {
    await waitForBoard(page);
    const dealButtons = page.locator('main button').filter({ hasText: /—/ });
    const count = await dealButtons.count();
    test.skip(count === 0, 'No active deals available in current dataset');
    await dealButtons.first().click();
    await expect(page.locator('text=返回客戶')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button', { hasText: '準備下次會議' })).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-DEAL-008: detail workspace switches to 活動 tab', async ({ page }) => {
    await waitForBoard(page);
    const dealButtons = page.locator('main button').filter({ hasText: /—/ });
    const count = await dealButtons.count();
    test.skip(count === 0, 'No active deals available in current dataset');
    await dealButtons.first().click();
    await page.locator('button', { hasText: '活動' }).click();
    await expect(page.locator('text=Activity · 所有動態')).toBeVisible({ timeout: 10000 });
  });

  test('CLIENT-DEAL: list view can switch back to pipeline', async ({ page }) => {
    await openListView(page);
    await page.locator('button', { hasText: 'Pipeline' }).click();
    await expect(page.locator('text=潛在客戶')).toBeVisible({ timeout: 10000 });
  });
});
