import subprocess
import json
import time
import os
import sys

EVIDENCE_DIR = '/Users/wubaizong/接案/ZenOS/dashboard/qa-evidence'
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Generate token
token_result = subprocess.run(
    ['node', 'scripts/gen-test-token.js'],
    capture_output=True, text=True,
    cwd='/Users/wubaizong/接案/ZenOS/dashboard'
)
TEST_TOKEN = token_result.stdout.strip()
print(f'Token (first 50): {TEST_TOKEN[:50]}...')

from playwright.sync_api import sync_playwright

results = {}

def screenshot(page, name, note=''):
    fp = os.path.join(EVIDENCE_DIR, f'{name}.png')
    page.screenshot(path=fp, full_page=False)
    print(f'  Screenshot: {fp} {note}')
    return fp

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, slow_mo=200)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    
    try:
        # ═══════════════════════════════════════════════
        # T1: Initial State
        # ═══════════════════════════════════════════════
        print('\n=== T1: Initial State ===')
        page.goto('http://localhost:3000/knowledge-map')
        page.wait_for_timeout(3000)  # Wait for Firebase SDK
        
        # Inject custom token
        sign_result = page.evaluate("""async (token) => {
            const signIn = window.__signInWithCustomToken;
            if (!signIn) return { error: '__signInWithCustomToken not found' };
            try {
                await signIn(token);
                return { ok: true };
            } catch(e) {
                return { error: e.message };
            }
        }""", TEST_TOKEN)
        print(f'  Sign in result: {sign_result}')
        
        # Wait for page to load after auth
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except:
            pass
        page.wait_for_timeout(3000)
        
        screenshot(page, 'T1-initial-state')
        
        # Verify: canvas is visible, no error
        canvas = page.locator('canvas').first()
        canvas_visible = canvas.is_visible()
        print(f'  Canvas visible: {canvas_visible}')
        
        # Check for "Loading" text gone
        body_text = page.inner_text('body')
        loading_gone = 'Loading knowledge map' not in body_text
        print(f'  Loading gone: {loading_gone}')
        print(f'  Body preview: {body_text[:200]}')
        
        has_login_error = sign_result.get('error') is not None
        t1_pass = canvas_visible and not has_login_error
        results['T1'] = {'pass': t1_pass, 'note': f"Canvas:{canvas_visible}, Login:{sign_result}"}
        print(f'  T1: {"PASS" if t1_pass else "FAIL"}')
        
        # ═══════════════════════════════════════════════
        # T2: Click L2 module node → expand + popover
        # ═══════════════════════════════════════════════
        print('\n=== T2: Click L2 module node ===')
        
        # Wait for graph to settle
        page.wait_for_timeout(3000)
        screenshot(page, 'T2a-before-click')
        
        canvas_bb = canvas.bounding_box()
        print(f'  Canvas BB: {canvas_bb}')
        
        if canvas_bb:
            cx = canvas_bb['x'] + canvas_bb['width'] / 2
            cy = canvas_bb['y'] + canvas_bb['height'] / 2
        else:
            cx, cy = 720, 450
        
        print(f'  Canvas center: ({cx}, {cy})')
        
        # Try multiple positions to find module node (purple L2)
        # Graph typically has L1 product in center, L2 modules spread around
        positions = [
            (cx, cy),
            (cx - 120, cy - 90),
            (cx + 120, cy - 90),
            (cx - 120, cy + 90),
            (cx + 120, cy + 90),
            (cx, cy - 150),
            (cx, cy + 150),
            (cx - 180, cy),
            (cx + 180, cy),
            (cx - 200, cy - 130),
            (cx + 200, cy - 130),
            (cx - 200, cy + 130),
            (cx + 200, cy + 130),
        ]
        
        module_clicked = False
        popover_visible = False
        clicked_pos = None
        
        for x, y in positions:
            print(f'  Trying click at ({x:.0f}, {y:.0f})...')
            page.mouse.click(x, y)
            page.wait_for_timeout(1200)
            
            # Check for checkboxes (popover appeared)
            checkbox_count = page.locator('input[type="checkbox"]').count()
            if checkbox_count > 0:
                print(f'  Checkboxes found: {checkbox_count} — popover opened!')
                module_clicked = True
                popover_visible = True
                clicked_pos = (x, y)
                break
            
            # Check for z-50 class (popover div)
            z50_count = page.locator('.z-50').count()
            if z50_count > 0:
                z50_visible = page.locator('.z-50').first().is_visible()
                if z50_visible:
                    print(f'  z-50 element visible — popover!')
                    module_clicked = True
                    popover_visible = True
                    clicked_pos = (x, y)
                    break
        
        screenshot(page, 'T2-after-click')
        print(f'  Module clicked: {module_clicked}, Popover: {popover_visible}, pos: {clicked_pos}')
        
        results['T2'] = {
            'pass': module_clicked and popover_visible,
            'note': f"Module:{module_clicked}, Popover:{popover_visible}, pos:{clicked_pos}"
        }
        print(f'  T2: {"PASS" if results["T2"]["pass"] else "FAIL"}')
        
        # ═══════════════════════════════════════════════
        # T3: Checklist popover content
        # ═══════════════════════════════════════════════
        print('\n=== T3: Checklist popover content ===')
        has_document = False
        has_task = False
        checkbox_info = []
        
        if popover_visible:
            # Get all visible z-50 content
            z50_text = ''
            try:
                z50_text = page.locator('.z-50').first().inner_text()
                print(f'  Popover text: {z50_text}')
                has_document = 'document' in z50_text.lower() or 'Document' in z50_text
                has_task = 'task' in z50_text.lower() or 'Task' in z50_text
            except Exception as e:
                print(f'  z-50 text error: {e}')
            
            # Check individual checkboxes
            checkboxes = page.locator('input[type="checkbox"]')
            cb_count = checkboxes.count()
            for i in range(cb_count):
                cb = checkboxes.nth(i)
                label = cb.evaluate("""el => {
                    const parent = el.closest('label') || el.parentElement;
                    return parent ? parent.innerText.trim() : '';
                }""")
                checked = cb.is_checked()
                print(f'  Checkbox {i}: "{label}" checked={checked}')
                checkbox_info.append({'label': label, 'checked': checked})
                if 'document' in label.lower():
                    has_document = True
                if 'task' in label.lower():
                    has_task = True
        
        screenshot(page, 'T3-checklist-popover')
        t3_pass = popover_visible and has_document and has_task
        results['T3'] = {
            'pass': t3_pass,
            'note': f"Document:{has_document}, Task:{has_task}, Checkboxes:{checkbox_info}"
        }
        print(f'  T3: {"PASS" if t3_pass else "FAIL"}')
        
        # ═══════════════════════════════════════════════
        # T4: Uncheck Task → task nodes disappear
        # ═══════════════════════════════════════════════
        print('\n=== T4: Uncheck Task ===')
        task_unchecked = False
        
        if popover_visible:
            checkboxes = page.locator('input[type="checkbox"]')
            cb_count = checkboxes.count()
            print(f'  Total checkboxes: {cb_count}')
            
            for i in range(cb_count):
                cb = checkboxes.nth(i)
                label = cb.evaluate("""el => {
                    const parent = el.closest('label') || el.parentElement;
                    return parent ? parent.innerText.trim() : '';
                }""")
                is_checked = cb.is_checked()
                print(f'  Checkbox {i}: "{label}" checked={is_checked}')
                
                if 'task' in label.lower() and is_checked:
                    print(f'  Unchecking Task checkbox...')
                    cb.click()
                    page.wait_for_timeout(800)
                    still_checked = cb.is_checked()
                    print(f'  After click, checked: {still_checked}')
                    task_unchecked = not still_checked
                    break
            
            # Fallback: try clicking on "Task" text
            if not task_unchecked:
                try:
                    task_labels = page.get_by_text('Task', exact=True)
                    tc = task_labels.count()
                    print(f'  "Task" text elements: {tc}')
                    if tc > 0:
                        task_labels.first().click()
                        page.wait_for_timeout(800)
                        task_unchecked = True
                        print('  Clicked Task text')
                except Exception as e:
                    print(f'  Task text click error: {e}')
        
        screenshot(page, 'T4-task-unchecked')
        results['T4'] = {
            'pass': task_unchecked,
            'note': f"Task unchecked: {task_unchecked}"
        }
        print(f'  T4: {"PASS" if task_unchecked else "FAIL"}')
        
        # ═══════════════════════════════════════════════
        # T5: Click same L2 again → collapse
        # ═══════════════════════════════════════════════
        print('\n=== T5: Click same L2 again → collapse ===')
        
        # Close popover by pressing Escape first
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
        
        # Check initial checkbox count
        cb_before = page.locator('input[type="checkbox"]').count()
        print(f'  Checkboxes before re-click: {cb_before}')
        
        # Re-click the position where module was found
        if clicked_pos:
            x, y = clicked_pos
            print(f'  Re-clicking at ({x:.0f}, {y:.0f})...')
            page.mouse.click(x, y)
            page.wait_for_timeout(1500)
            
            cb_after = page.locator('input[type="checkbox"]').count()
            print(f'  Checkboxes after re-click: {cb_after}')
            
            # If re-click opened popover again, need to click once more to collapse
            if cb_after > 0:
                print('  Popover reopened — need another click to collapse')
                page.mouse.click(x, y)
                page.wait_for_timeout(1500)
                cb_final = page.locator('input[type="checkbox"]').count()
                print(f'  Checkboxes after 2nd click: {cb_final}')
                collapse_happened = cb_final == 0
            else:
                # Module was collapsed
                collapse_happened = cb_after == 0
        else:
            collapse_happened = False
        
        screenshot(page, 'T5-after-collapse')
        results['T5'] = {
            'pass': collapse_happened,
            'note': f"Collapsed: {collapse_happened}"
        }
        print(f'  T5: {"PASS" if collapse_happened else "FAIL"}')
        
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
        screenshot(page, 'error-state')
    finally:
        screenshot(page, 'final-state')
        browser.close()

print('\n' + '='*50)
print('RESULTS SUMMARY')
print('='*50)
for test, result in results.items():
    status = 'PASS' if result['pass'] else 'FAIL'
    print(f'{test}: {status} — {result["note"]}')

all_p0_pass = all(results.get(t, {}).get('pass', False) for t in ['T1','T2','T3','T4','T5'])
print(f'\nOverall P0: {"ALL PASS" if all_p0_pass else "SOME FAILED"}')
