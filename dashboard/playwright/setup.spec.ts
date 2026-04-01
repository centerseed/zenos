/**
 * Setup page e2e tests.
 * Covers page load, MCP config block, and tab switching.
 */
import { test, expect } from './fixtures';

async function waitForSetupPage(page: any) {
  await page.goto('/setup');
  await expect(page.locator('header')).toBeVisible({ timeout: 20000 });
  // Wait until the partner data is available and the page renders
  await expect(page.locator('h2', { hasText: 'Set up your AI Agent' })).toBeVisible({ timeout: 20000 });
}

test.describe('Setup Page', () => {
  test('SETUP-002: page loads with heading and description', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('h2', { hasText: 'Set up your AI Agent' })).toBeVisible();
    await expect(page.locator('text=Connect your AI agent to ZenOS')).toBeVisible();
  });

  test('SETUP-003: MCP config block shows API key and config section', async ({ page }) => {
    await waitForSetupPage(page);
    // McpConfigBlock renders "Your API Key" text and a Show/Hide button
    await expect(page.locator('text=Your API Key')).toBeVisible({ timeout: 10000 });
    // The Show/Hide button for the API key
    await expect(page.locator('button', { hasText: /Show|Hide/ }).first()).toBeVisible({ timeout: 10000 });
    // The config block (pre or code element)
    await expect(page.locator('pre').first()).toBeVisible({ timeout: 10000 });
  });

  test('SETUP-004: clicking Claude Code tab activates it', async ({ page }) => {
    await waitForSetupPage(page);
    // Claude Code tab is the default; verify it's active
    const claudeCodeTab = page.locator('button', { hasText: 'Claude Code' }).first();
    await expect(claudeCodeTab).toBeVisible({ timeout: 10000 });
    // The active tab has border-blue-500 class
    await expect(claudeCodeTab).toHaveClass(/border-blue-500/);

    // Click it (idempotent — re-select already active tab)
    await claudeCodeTab.click();
    await expect(claudeCodeTab).toHaveClass(/border-blue-500/);
  });

  test('SETUP-005: clicking Claude.ai tab switches Setup steps content', async ({ page }) => {
    await waitForSetupPage(page);
    // There are two sets of Claude.ai tabs: one in McpConfigBlock (Select your agent),
    // one in Setup steps. We want the Setup steps one (under h3 "Setup steps").
    const setupStepsSection = page.locator('h3', { hasText: 'Setup steps' }).locator('..');
    const claudeAiTab = setupStepsSection.locator('button', { hasText: 'Claude.ai' });
    await expect(claudeAiTab).toBeVisible({ timeout: 10000 });
    await claudeAiTab.click();

    // After switch, Claude.ai step 1: "Connect MCP" should appear
    await expect(page.locator('h4', { hasText: 'Connect MCP' })).toBeVisible({ timeout: 5000 });
  });

  test('SETUP: Copy MCP config button is present', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('[aria-label="Copy MCP config"]')).toBeVisible({ timeout: 10000 });
  });

  test('SETUP: Setup steps section with numbered steps visible', async ({ page }) => {
    await waitForSetupPage(page);
    await expect(page.locator('h3', { hasText: 'Setup steps' })).toBeVisible({ timeout: 10000 });
    // Claude Code is default tab — step 1 "Install Claude Code"
    await expect(page.locator('h4', { hasText: 'Install Claude Code' })).toBeVisible({ timeout: 10000 });
  });
});
