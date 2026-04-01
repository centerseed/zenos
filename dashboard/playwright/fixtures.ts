/**
 * Extended Playwright fixtures for ZenOS Dashboard e2e tests.
 *
 * Provides a `page` fixture that automatically seeds Firebase IndexedDB with
 * real auth tokens before each test, enabling authenticated page navigation
 * without relying on storageState (which doesn't capture IndexedDB).
 */
import { test as base, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const INIT_SCRIPT_PATH = path.join(__dirname, '.auth/firebase-init.js');

/**
 * Extended test fixture that seeds Firebase IndexedDB auth before each test.
 * Falls back gracefully if the init script doesn't exist (e.g., on first run).
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    if (fs.existsSync(INIT_SCRIPT_PATH)) {
      await page.addInitScript({ path: INIT_SCRIPT_PATH });
    }
    await use(page);
  },
});

export { expect };
