// Real Next + disposable basic_ui_server.py API/SQLite. Auth and failures are fixtures.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.BASIC_WEB_ORIGIN || 'http://localhost:15102';
const artifacts = fileURLToPath(new URL('../../test-results/basic-form/', import.meta.url));
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const U = '10000000-0000-4000-8000-000000000001', D = '20000000-0000-4000-8000-000000000001';
const goal = '동아리 러닝 기록을 분석해서 훈련량과 기록 변화의 관계를 알아보고 싶어요.';
const report = [];
async function poll(check, label) { for (let i = 0; i < 200; i++) { if (await check()) return; await delay(100); } throw Error('Timeout: ' + label); }
try {
 for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  const context = await browser.newContext({ viewport });
  await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({ json: { access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer', user: { id: '12345678-0000-4000-8000-000000000002', is_anonymous: true, aud: 'authenticated' } } }));
  const page = await context.newPage(), errors = [], writes = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', dialog => dialog.accept());
  page.on('request', r => { if (/\/api\/roadmap-inputs\/[^/]+$/.test(r.url()) && r.method() === 'PATCH') writes.push(r.postDataJSON()); });
  const button = name => page.getByRole('button', { name, exact: true });
  const field = name => page.locator(`[name=${name}]`);
  const status = page.locator('.basic-save-status');
  const go = path => page.goto(origin + path);
  const get = () => page.evaluate(async () => (await fetch('/api/roadmap-inputs/' + sessionStorage.getItem('roadmap_request_id'))).json());
  const ready = () => poll(() => button('저장').isEnabled(), 'catalog ready');
  const saved = () => poll(() => status.textContent().then(t => t === '저장됨'), 'saved');
  const save = async () => { await ready(); await button('저장').click(); await saved(); };
  async function expanded(expected) { await poll(() => field('university_id').isVisible().then(v => v === expected), 'academic disclosure'); }
  async function change() { await button('변경').click(); await expanded(true); }
  async function layout() {
   assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow');
   const boxes = await Promise.all(['.stepper', '.page-title-row', '.academic-bar', '.career-card'].map(s => page.locator(s).boundingBox()));
   assert.ok(boxes.every(b => Math.abs(b.x - boxes[0].x) <= 1), 'aligned left edges');
   assert.equal(boxes[2].width, boxes[3].width, 'academic and career widths');
   const target = await field('target_role').boundingBox(), textarea = await field('career_goal').boundingBox();
   assert.equal(target.x, textarea.x, 'role aligned left');
   assert.ok(viewport.width > 700 ? target.width <= 300 : Math.abs(target.width - textarea.width) <= 1, 'responsive role width');
  }
  try {
   await go('/'); await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic'); await expanded(true);
   assert.equal(await status.textContent(), '');
   assert.ok(await field('department_id').isDisabled());
   assert.equal(await page.locator('.notice').count(), 0, 'no top save banner');
   await button('저장 후 다음 →').click();
   await page.locator('#career-goal-error').waitFor();
   assert.ok(await field('career_goal').evaluate(el => el === document.activeElement));
   assert.equal(writes.length, 0, 'empty goal sends no PATCH');
   await field('career_goal').fill(goal); await field('target_role').fill('데이터 분석가');
   await field('university_id').selectOption(U); await expanded(true);
   await field('department_id').selectOption(D); await expanded(false); await ready();
   assert.equal(await status.textContent(), '변경사항 있음', 'collapse must not claim saved');
   assert.equal(writes.length, 0);
   assert.ok((await page.locator('.academic-summary-text').innerText()).includes('한빛대학교 (예시) · 컴퓨터공학과'));
   const beforeChange = writes.length;
   await change(); assert.equal(await field('university_id').inputValue(), U); assert.equal(await field('department_id').inputValue(), D);
   assert.equal(await field('career_goal').inputValue(), goal); assert.equal(await field('target_role').inputValue(), '데이터 분석가');
   await button('접기').click(); await expanded(false); assert.equal(writes.length, beforeChange);
   await layout();

   // Navigation waits for a successful PATCH; inputs and all save controls lock in flight.
   let release, started;
   const gate = new Promise(resolve => release = resolve), pending = new Promise(resolve => started = resolve);
   await page.route(/\/api\/roadmap-inputs\/[^/]+$/, async route => {
    if (route.request().method() !== 'PATCH') return route.continue();
    started(); await gate; await route.continue();
   });
   await button('저장 후 다음 →').click(); await pending;
   assert.equal(await status.textContent(), '저장 중');
   assert.ok(page.url().endsWith('/input/basic'));
   assert.ok(await field('career_goal').isDisabled()); assert.ok(await button('저장').isDisabled());
   assert.ok(await button('저장 후 다음 →').isDisabled());
   release(); await page.waitForURL('**/input/documents'); await page.unroute(/\/api\/roadmap-inputs\/[^/]+$/);
   assert.equal((await get()).input.catalog_id, '30000000-0000-4000-8000-000000000001');
   await go('/input/basic'); await expanded(false); await saved();
   await page.reload(); await expanded(false); await ready();
   assert.equal(await field('career_goal').inputValue(), goal); assert.equal(await field('target_role').inputValue(), '데이터 분석가');
   await layout();
   await page.addStyleTag({ content: 'nextjs-portal{display:none}' }); await page.evaluate(() => document.fonts.ready);
   if (viewport.width === 1440) {
    await page.screenshot({ path: artifacts + 'desktop-collapsed.png', animations: 'disabled' });
    if (process.env.CAPTURE_HELP === '1') await page.locator('#main-content').screenshot({ path: fileURLToPath(new URL('../../public/help/basic.png', import.meta.url)), animations: 'disabled' });
   } else {
    await change(); await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: artifacts + 'mobile-expanded.png', animations: 'disabled' });
    await page.screenshot({ path: artifacts + 'mobile-expanded-full.png', fullPage: true, animations: 'disabled' });
    await button('접기').click();
   }
   // Opening the example keeps the draft and disclosure; keyboard focus returns to ?.
   await field('career_goal').fill(goal + ' 매주 비교하고 싶어요.');
   const draft = await field('career_goal').inputValue(), beforeHelp = writes.length;
   await button('기본 정보 예시 보기').click();
   const dialog = page.getByRole('dialog'); await dialog.waitFor();
   await poll(() => dialog.locator('img').evaluate(el => el.complete && el.naturalWidth >= 1000), 'updated help image');
   await page.keyboard.press('Escape');
   assert.equal(await field('career_goal').inputValue(), draft); assert.equal(writes.length, beforeHelp);
   assert.ok(await button('기본 정보 예시 보기').evaluate(el => el === document.activeElement));

   // Changing school clears both links and preserves the career draft, including after reload.
   await change(); await field('university_id').selectOption('basic-other'); await expanded(true);
   assert.equal(await field('department_id').inputValue(), '');
   assert.equal(await field('career_goal').inputValue(), draft); assert.equal(await field('target_role').inputValue(), '데이터 분석가');
   await save(); assert.equal(writes.at(-1).changes.department_id, null); assert.equal(writes.at(-1).changes.catalog_id, null);
   assert.equal((await get()).input.department_id, null); assert.equal((await get()).input.catalog_id, null);
   await page.reload(); await expanded(true); assert.equal(await field('university_id').inputValue(), 'basic-other');
   await field('department_id').selectOption('basic-data'); await expanded(false); await ready();
   assert.equal(await status.textContent(), '변경사항 있음'); await save(); assert.equal((await get()).input.catalog_id, 'basic-current');
   await change(); await field('catalog_id').selectOption('basic-previous'); await save();
   await page.reload(); await expanded(false); await ready(); await change();
   assert.equal(await field('catalog_id').inputValue(), 'basic-previous', 'saved catalog retained');

   // A delayed old catalog response cannot reattach after another school is selected.
   let releaseCatalog, startedCatalog;
   const catalogGate = new Promise(resolve => releaseCatalog = resolve), catalogStarted = new Promise(resolve => startedCatalog = resolve);
   await page.route(`**/departments/${D}/catalogs`, async route => {
    const response = await route.fetch(); startedCatalog(); await catalogGate;
    await route.fulfill({ response }).catch(() => {});
   });
   await field('university_id').selectOption(U); await field('department_id').selectOption(D); await catalogStarted;
   await change(); await field('university_id').selectOption('basic-other'); await field('department_id').selectOption('basic-empty');
   await ready(); releaseCatalog(); await delay(200); await page.unroute(`**/departments/${D}/catalogs`);
   await save(); assert.equal((await get()).input.department_id, 'basic-empty'); assert.equal((await get()).input.catalog_id, null);

   // Catalog failure can recover, and a user can clear the optional school to proceed.
   await change(); await field('university_id').selectOption(U);
   await page.route(`**/departments/${D}/catalogs`, route => route.fulfill({ status: 503, json: { message: '과목 목록을 불러오지 못했습니다.' } }), { times: 1 });
   await field('department_id').selectOption(D); await button('목록 다시 불러오기').waitFor();
   assert.ok(await button('저장').isDisabled()); await button('목록 다시 불러오기').click(); await ready();
   await change(); await field('university_id').selectOption(''); await expanded(true);
   await save(); assert.equal((await get()).input.university_id, null); assert.equal((await get()).input.catalog_id, null);
   await page.reload(); await expanded(true); await ready(); assert.equal(await field('university_id').inputValue(), '');

   // Empty/whitespace validation applies to all save destinations.
   await field('career_goal').fill('   ');
   const count = writes.length;
   for (const action of ['저장', '저장 후 다음 →']) {
    await button(action).click(); assert.ok(await field('career_goal').evaluate(el => el === document.activeElement));
    assert.ok(await page.locator('#career-goal-error').isVisible());
   }
   assert.equal(writes.length, count);
   await field('career_goal').fill(goal); await field('target_role').fill('');
   await page.route(/\/api\/roadmap-inputs\/[^/]+$/, route => route.request().method() === 'PATCH' ? route.fulfill({ status: 503, json: { message: '저장하지 못했습니다.' } }) : route.continue(), { times: 1 });
   await button('저장 후 다음 →').click(); await page.getByRole('alert').filter({ hasText: '저장하지 못했습니다.' }).waitFor();
   assert.ok(page.url().endsWith('/input/basic')); assert.equal(await field('career_goal').inputValue(), goal);
   assert.equal(await status.textContent(), '변경사항 있음'); assert.ok(await button('저장').isEnabled());
   await button('저장 후 다음 →').click(); await page.waitForURL('**/input/documents');
   assert.equal((await get()).input.career_goal, goal); assert.equal((await get()).input.university_id, null);

   // Real revision conflict retains the draft until explicit reload.
   await go('/input/basic'); await ready(); await field('career_goal').fill(goal + ' 충돌 중 작성값');
   const plan = await get();
   const concurrent = await page.request.patch(`${origin}/api/roadmap-inputs/${plan.request_id}`, { headers: { Origin: origin }, data: { expected_input_revision: plan.input_revision, changes: { target_role: '다른 화면의 직무' } } });
   assert.ok(concurrent.ok());
   await button('저장').click(); await button('최신 내용 불러오기').waitFor();
   assert.equal(await field('career_goal').inputValue(), goal + ' 충돌 중 작성값'); assert.ok(await button('저장').isDisabled());
   await button('최신 내용 불러오기').click(); await ready();
   assert.equal(await field('target_role').inputValue(), '다른 화면의 직무');
   assert.deepEqual(errors, []); await layout();
   const entry = { viewport, checks: ['first visit expanded', 'department collapses without save', 'edit preserves draft', 'auto catalog and school reset', 'saved catalog restore', 'stale catalog ignored', 'catalog failure retry', 'save pending navigation lock', 'refresh restore', 'no school save and next navigation', 'all required goal errors and focus', '503 draft retention and retry', '409 draft retention', 'help image and focus', 'responsive alignment'], patches: writes.length };
   report.push(entry); console.log('PASS', JSON.stringify(entry));
  } catch (e) {
   await page.screenshot({ path: artifacts + `failure-${viewport.width}.png`, fullPage: true });
   console.error(await page.locator('body').innerText()); throw e;
  } finally { await context.close(); }
 }
 writeFileSync(artifacts + 'report.json', JSON.stringify(report, null, 2));
} finally { await browser.close(); }
