/**
 * Setup page e2e tests.
 * Covers page load, MCP config block, and tab switching.
 */
import { test, expect } from './fixtures';

async function waitForSetupPage(page: any) {
  await page.goto('/setup');
  await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('main#main-content')).toBeVisible({ timeout: 20000 });
  await expect(
    page.locator('h1', { hasText: /選擇你的 AI 工具|Set up your AI Agent|Select your AI/i })
  ).toBeVisible({ timeout: 20000 });
}

test.describe('Setup Page', () => {
  test('SETUP-002: page loads with heading and description', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('h1', { hasText: /選擇你的 AI 工具|Set up your AI Agent/i })).toBeVisible();
    await expect(page.locator('text=開始安裝')).toBeVisible();
  });

  test('SETUP-003: MCP config block shows API key and config section', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('h2', { hasText: '複製你的 MCP 連結' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="mcp-url-display"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button', { hasText: 'Copy' }).first()).toBeVisible({ timeout: 10000 });
  });

  test('SETUP-004: clicking Claude Code tab activates it', async ({ page }) => {
    await waitForSetupPage(page);
    const claudeCodeTab = page.locator('button', { hasText: 'Claude Code' }).first();
    await expect(claudeCodeTab).toBeVisible({ timeout: 10000 });
    await claudeCodeTab.click();
    await expect(page.locator('[data-testid="mcp-url-display"]')).toContainText('/mcp?api_key=');
  });

  test('SETUP-005: clicking Gemini CLI tab switches MCP protocol to SSE', async ({ page }) => {
    await waitForSetupPage(page);
    const geminiTab = page.locator('button', { hasText: 'Gemini CLI' }).first();
    await expect(geminiTab).toBeVisible({ timeout: 10000 });
    await geminiTab.click();
    await expect(page.locator('[data-testid="mcp-url-display"]')).toContainText('/sse?api_key=');
    await expect(page.locator('text=SSE 協議 (/sse)')).toBeVisible({ timeout: 10000 });
  });

  test('SETUP: Copy MCP config button is present', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('[data-testid="setup-prompt"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button', { hasText: 'Copy' }).nth(1)).toBeVisible({ timeout: 10000 });
  });

  test('SETUP: Setup steps section with numbered steps visible', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('text=Step 1')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Step 2')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Step 3')).toBeVisible({ timeout: 10000 });
  });
});
