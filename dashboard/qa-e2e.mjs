import { chromium } from '/Users/wubaizong/clients/ZenOS/dashboard/node_modules/playwright/index.mjs';

const browser = await chromium.launch({ headless: false, slowMo: 500 });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

// Navigate to local dev (which has __signInWithCustomToken in dev mode)
console.log('Navigating to localhost:3000...');
await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 15000 });
await page.waitForTimeout(2000);
console.log('URL:', page.url());

const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 300));
console.log('Body:', bodyText);

await page.screenshot({ path: '/tmp/qa-screenshots/local-login.png' });

await browser.close();
