import { test, expect } from './fixtures';

const LIVE_BASE_URL = 'https://zenos-naruvia.web.app';
const HELPER_TOKEN = 'mk-aqzb9nk7n9kd';

test.describe('CRM Briefing Live', () => {
  test('opens briefing on live site', async ({ page }) => {
    test.setTimeout(180000);
    await page.context().grantPermissions(['local-network-access'], { origin: LIVE_BASE_URL });

    await page.addInitScript((token) => {
      window.localStorage.setItem('zenos.marketing.cowork.helperToken', token);
      window.localStorage.setItem('zenos.marketing.cowork.helperBaseUrl', 'http://127.0.0.1:4317');
      window.localStorage.setItem('zenos.marketing.cowork.model', 'sonnet');
    }, HELPER_TOKEN);

    await page.goto(`${LIVE_BASE_URL}/clients`, { waitUntil: 'networkidle' });
    await expect(page.locator('header')).toBeVisible({ timeout: 30000 });
    await page.waitForFunction(
      () => !document.body.textContent?.includes('載入商機看板...'),
      { timeout: 30000 }
    );

    const dealLinks = page.locator('a[href*="/clients/deals/"]');
    await expect(dealLinks.first()).toBeVisible({ timeout: 30000 });
    const dealHref = await dealLinks.first().getAttribute('href');
    if (!dealHref) {
      throw new Error('No live deal link found on /clients');
    }

    await page.goto(`${LIVE_BASE_URL}${dealHref}`, { waitUntil: 'networkidle' });
    await expect(page.locator('button', { hasText: '準備下次會議' })).toBeVisible({ timeout: 30000 });
    await page.locator('button', { hasText: '準備下次會議' }).click();

    await expect(page.locator('text=AI 會議準備')).toBeVisible({ timeout: 30000 });
    await expect(page.getByPlaceholder('追問或調整重點...')).toBeVisible({ timeout: 120000 });
    await expect(page.locator('text=Claude')).toHaveCount(1, { timeout: 120000 });
    await expect(page.locator('button', { hasText: '另存新 briefing' })).toBeVisible({ timeout: 120000 });

    const briefingOpenButtons = page.locator('button', { hasText: '開啟' });
    await expect(briefingOpenButtons.first()).toBeVisible({ timeout: 120000 });
    const initialBriefingCount = await briefingOpenButtons.count();

    await expect(page.locator('button', { hasText: '複製最新準備摘要' })).toBeVisible({ timeout: 120000 });
    await expect(page.locator('button', { hasText: '另存新 briefing' })).toBeEnabled({ timeout: 120000 });

    if (process.env.PW_CRM_LIVE_MUTATION !== '1') {
      return;
    }

    await page.locator('button', { hasText: '另存新 briefing' }).click();
    await expect
      .poll(async () => await page.locator('button', { hasText: '開啟' }).count(), { timeout: 120000 })
      .toBeGreaterThan(initialBriefingCount);

    const briefingDialog = page.getByRole('dialog');
    await briefingDialog.getByRole('button', { name: /Close|關閉/ }).click();
    await expect(briefingDialog).toHaveCount(0);
    await briefingOpenButtons.first().click();
    await expect(page.locator('text=AI 會議準備')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('button', { hasText: '複製最新準備摘要' })).toBeVisible({ timeout: 30000 });
    await briefingDialog.getByRole('button', { name: /Close|關閉/ }).click();
    await expect(briefingDialog).toHaveCount(0);

    page.once('dialog', (dialog) => dialog.accept());
    const deleteButtons = page.locator('button', { hasText: '刪除' });
    await deleteButtons.first().click();
    await expect
      .poll(async () => await page.locator('button', { hasText: '開啟' }).count(), { timeout: 120000 })
      .toBe(initialBriefingCount);

    const errorText = page.locator('text=/請先啟動 Local Helper|Invalid helper token|permission denied|串流失敗|發生錯誤/');
    await expect(errorText).toHaveCount(0);
  });
});
