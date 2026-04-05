import { chromium } from '/Users/wubaizong/clients/ZenOS/dashboard/node_modules/playwright/index.mjs';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

console.log('Step 1: Navigate to knowledge-map...');
try {
  await page.goto('https://narugo-6782b.web.app/knowledge-map', { waitUntil: 'networkidle', timeout: 30000 });
} catch(e) {
  console.log('Navigation error:', e.message);
}

await page.screenshot({ path: '/tmp/qa-screenshots/01-initial-load.png', fullPage: false });
console.log('Screenshot 01 taken. URL:', page.url());
console.log('Title:', await page.title());

const currentUrl = page.url();
console.log('Current URL after load:', currentUrl);

const pageContent = await page.content();
const hasLogin = pageContent.includes('login') || pageContent.includes('Login') || pageContent.includes('Sign in');
console.log('Has login content:', hasLogin);

// Check what's visible
const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 500));
console.log('Body text preview:', bodyText);

await browser.close();
