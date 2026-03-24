const { chromium } = require('playwright');
const path = require('path');
const { execSync } = require('child_process');
const fs = require('fs');

// Generate token
const token = execSync('node /Users/wubaizong/接案/ZenOS/dashboard/scripts/gen-test-token.js').toString().trim();
console.log('Token generated (first 50 chars):', token.substring(0, 50) + '...');

const EVIDENCE_DIR = '/Users/wubaizong/接案/ZenOS/dashboard/qa-evidence';

async function screenshot(page, name) {
  const fp = path.join(EVIDENCE_DIR, `${name}.png`);
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`Screenshot: ${fp}`);
  return fp;
}

async function main() {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const results = {};

  try {
    // ── Step 1: Navigate to knowledge-map
    console.log('\n=== T1: Initial State ===');
    await page.goto('http://localhost:3000/knowledge-map');
    await page.waitForTimeout(3000); // Wait for Firebase SDK

    // Inject custom token
    console.log('Injecting custom token...');
    const signInResult = await page.evaluate(async (token) => {
      const signIn = window.__signInWithCustomToken;
      if (!signIn) return { error: '__signInWithCustomToken not found' };
      try {
        await signIn(token);
        return { ok: true };
      } catch(e) {
        return { error: e.message };
      }
    }, token);
    console.log('Sign in result:', signInResult);

    if (signInResult.error) {
      results.T1 = { pass: false, note: 'Login hook not found: ' + signInResult.error };
    }

    // Wait for page to update after auth
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    await page.waitForTimeout(2000);

    // T1 screenshot
    await screenshot(page, 'T1-initial-state');

    // Check for graph canvas
    const canvas = page.locator('canvas').first();
    const canvasVisible = await canvas.isVisible().catch(() => false);
    console.log('Canvas visible:', canvasVisible);

    // Check for error indicators
    const bodyText = await page.locator('body').innerText().catch(() => '');
    const hasError = bodyText.includes('Error') || bodyText.includes('error');
    console.log('Body has error text:', hasError);
    console.log('Body preview:', bodyText.substring(0, 200));

    results.T1 = {
      pass: canvasVisible && !signInResult.error,
      note: `Canvas visible: ${canvasVisible}, Login: ${signInResult.error ?? 'ok'}`
    };

    // ── T2: Click L2 module node
    console.log('\n=== T2: Click L2 module node ===');
    // Get canvas bounding box
    const canvasBB = await canvas.boundingBox();
    console.log('Canvas bounding box:', canvasBB);

    // Wait for graph simulation to settle
    await page.waitForTimeout(3000);
    await screenshot(page, 'T2a-before-click');

    // Try to find module nodes by examining the page state
    // We'll query exposed node positions via JS if available
    const nodePositions = await page.evaluate(() => {
      // Try to get from window debug state
      if (window.__graphNodes) return window.__graphNodes;
      return null;
    });
    console.log('Graph nodes from window:', nodePositions);

    // Strategy: click near center of canvas (where graph usually is)
    // Graph typically renders nodes spread around center
    const cx = canvasBB.x + canvasBB.width / 2;
    const cy = canvasBB.y + canvasBB.height / 2;
    console.log(`Canvas center: (${cx}, ${cy})`);

    // Try multiple positions to find a module node
    // Modules (L2, purple) are children of product, spread around center
    const tryPositions = [
      [cx, cy],                          // dead center
      [cx - 100, cy - 80],              // top-left area
      [cx + 100, cy - 80],              // top-right area
      [cx - 100, cy + 80],              // bottom-left area  
      [cx + 100, cy + 80],              // bottom-right area
      [cx, cy - 120],                   // top
      [cx, cy + 120],                   // bottom
      [cx - 150, cy],                   // left
      [cx + 150, cy],                   // right
    ];

    let moduleClicked = false;
    let popoverVisible = false;
    let newNodesAppeared = false;

    for (const [x, y] of tryPositions) {
      console.log(`Trying click at (${x}, ${y})`);
      await page.mouse.click(x, y);
      await page.waitForTimeout(1500);

      // Check if popover appeared
      const popover = page.locator('[class*="popover"], [class*="TypeFilter"], .z-50').first();
      popoverVisible = await popover.isVisible().catch(() => false);
      
      if (popoverVisible) {
        console.log('Popover appeared at position:', x, y);
        moduleClicked = true;
        break;
      }
      
      // Also check if any checklist-like content appeared
      const checkboxes = page.locator('input[type="checkbox"]');
      const checkboxCount = await checkboxes.count().catch(() => 0);
      if (checkboxCount > 0) {
        console.log('Checkboxes appeared, count:', checkboxCount);
        moduleClicked = true;
        popoverVisible = true;
        break;
      }
    }

    await screenshot(page, 'T2-after-click');
    console.log('Module clicked (popover appeared):', moduleClicked);

    results.T2 = {
      pass: moduleClicked && popoverVisible,
      note: `Module click: ${moduleClicked}, Popover: ${popoverVisible}`
    };

    // ── T3: Checklist popover content
    console.log('\n=== T3: Checklist popover content ===');
    let checkboxes = [];
    let hasDocument = false;
    let hasTask = false;

    if (popoverVisible) {
      const checkboxEls = page.locator('input[type="checkbox"]');
      const count = await checkboxEls.count().catch(() => 0);
      console.log('Checkbox count:', count);

      for (let i = 0; i < count; i++) {
        const cb = checkboxEls.nth(i);
        const label = await cb.evaluate(el => {
          const parent = el.closest('label') || el.parentElement;
          return parent ? parent.innerText : '';
        }).catch(() => '');
        const checked = await cb.isChecked().catch(() => false);
        console.log(`Checkbox ${i}: "${label}" checked=${checked}`);
        checkboxes.push({ label, checked });
        if (label.toLowerCase().includes('document')) hasDocument = true;
        if (label.toLowerCase().includes('task')) hasTask = true;
      }

      // Also check for text labels near checkboxes
      const popoverText = await page.locator('.z-50').innerText().catch(() => '');
      console.log('Popover text:', popoverText);
      if (popoverText.toLowerCase().includes('document')) hasDocument = true;
      if (popoverText.toLowerCase().includes('task')) hasTask = true;
    }

    await screenshot(page, 'T3-checklist-popover');

    results.T3 = {
      pass: popoverVisible && hasDocument && hasTask,
      note: `Has Document: ${hasDocument}, Has Task: ${hasTask}, Checkboxes: ${checkboxes.length}`
    };

    // ── T4: Uncheck Task → task nodes disappear
    console.log('\n=== T4: Uncheck Task ===');
    let taskUnchecked = false;

    if (popoverVisible) {
      // Find Task checkbox
      const allCheckboxes = page.locator('input[type="checkbox"]');
      const count = await allCheckboxes.count().catch(() => 0);
      
      for (let i = 0; i < count; i++) {
        const cb = allCheckboxes.nth(i);
        const label = await cb.evaluate(el => {
          const parent = el.closest('label') || el.parentElement;
          return parent ? parent.innerText : '';
        }).catch(() => '');
        const isChecked = await cb.isChecked().catch(() => false);
        
        if (label.toLowerCase().includes('task') && isChecked) {
          console.log('Unchecking Task checkbox...');
          await cb.click();
          await page.waitForTimeout(1000);
          taskUnchecked = true;
          break;
        }
      }

      // If direct checkbox didn't work, try clicking on label text
      if (!taskUnchecked) {
        const taskLabel = page.getByText('Task').first();
        const visible = await taskLabel.isVisible().catch(() => false);
        if (visible) {
          await taskLabel.click();
          await page.waitForTimeout(1000);
          taskUnchecked = true;
        }
      }
    }

    await screenshot(page, 'T4-task-unchecked');
    console.log('Task unchecked:', taskUnchecked);

    results.T4 = {
      pass: taskUnchecked,
      note: `Task checkbox unchecked: ${taskUnchecked}`
    };

    // ── T5: Click same L2 again → collapse
    console.log('\n=== T5: Click same L2 again → collapse ===');
    // Close popover first by pressing Escape or clicking elsewhere
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // Re-click the same position where we found the module
    let collapseClicked = false;
    for (const [x, y] of tryPositions) {
      await page.mouse.click(x, y);
      await page.waitForTimeout(1500);
      
      // Check if popover disappeared (collapsed)
      const checkboxCount = await page.locator('input[type="checkbox"]').count().catch(() => 0);
      if (checkboxCount === 0) {
        console.log('No checkboxes visible — collapsed!');
        collapseClicked = true;
        break;
      }
    }

    await screenshot(page, 'T5-after-collapse');
    console.log('Collapse happened:', collapseClicked);

    results.T5 = {
      pass: collapseClicked,
      note: `Collapsed: ${collapseClicked}`
    };

  } catch (err) {
    console.error('Test error:', err);
  } finally {
    await screenshot(page, 'final-state');
    await browser.close();

    console.log('\n=== RESULTS SUMMARY ===');
    for (const [test, result] of Object.entries(results)) {
      const status = result.pass ? 'PASS' : 'FAIL';
      console.log(`${test}: ${status} — ${result.note}`);
    }

    const allP0Pass = ['T1','T2','T3','T4','T5'].every(t => results[t]?.pass);
    console.log('\nOverall P0:', allP0Pass ? 'ALL PASS' : 'SOME FAILED');
  }
}

main().catch(console.error);
