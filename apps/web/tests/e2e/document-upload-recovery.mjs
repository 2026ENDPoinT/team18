// Start Next on :15115 -> :18095. This script owns/kills/restarts its isolated
// PostgreSQL API fixture. See docs/document-upload-recovery.md for commands.
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm, mkdir, appendFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = await mkdtemp('/private/tmp/team18-recovery-browser-');
const apiRoot = fileURLToPath(new URL('../../../api/', import.meta.url));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const web = 'http://localhost:15115', api = 'http://127.0.0.1:18095';
const reports = [], errors = [];
let server, browser, user;
async function poll(fn, message, timeout = 20000) {
 const end = Date.now() + timeout;
 while (Date.now() < end) { try { if (await fn()) return; } catch {} await delay(100); }
 throw new Error(message);
}
async function start() {
 server = spawn(process.env.DOCUMENT_TEST_PYTHON || 'python3', ['tests/integration/document_recovery_ui_server.py'], {
  cwd: apiRoot, env: { ...process.env, DOCUMENT_RECOVERY_TEST_ROOT: root }, stdio: ['ignore', 'pipe', 'pipe'],
 });
 server.stderr.on('data', data => { void appendFile(root + '/api.log', data); if (String(data).includes('Traceback')) errors.push(String(data)); });
 server.stdout.on('data', data => { void appendFile(root + '/api.log', data); });
 await poll(async () => { const response = await fetch(api + '/__test__/config'); user = (await response.json()).user; return response.ok; }, 'API did not start');
}
async function kill() {
 if (!server || server.exitCode !== null) return;
 await new Promise(resolve => { server.once('exit', resolve); server.kill('SIGKILL'); });
}
async function resetGate(stage) {
 await Promise.all([rm(root + '/entered-' + stage, { force: true }), rm(root + '/release-' + stage, { force: true })]);
}
async function entered(stage) { await poll(async () => { await readFile(root + '/entered-' + stage); return true; }, stage + ' gate not reached'); }
const release = stage => writeFile(root + '/release-' + stage, '');
const file = (name, content = 'project text') => ({ name, mimeType: 'text/plain', buffer: Buffer.from(content) });
const choose = (page, files) => page.locator('input[type=file]').setInputFiles(files);
async function count(page, n) {
 await page.waitForFunction(n => document.querySelectorAll('[data-document-id]').length === n && !document.querySelector('[data-upload-status="uploading"],[data-upload-status="server_uploading"],[data-upload-status="uploaded"],[data-upload-status="checking"],[data-upload-status="queued"]'), n);
}
async function scenario(name, run) {
 if (process.env.DOCUMENT_SCENARIO_FILTER && !name.startsWith(process.env.DOCUMENT_SCENARIO_FILTER)) return;
 user = (await (await fetch(api + '/__test__/new-user', { method: 'POST' })).json()).user;
 const context = await browser.newContext();
 await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({ json: {
  access_token: user, refresh_token: 'synthetic-refresh', expires_in: 3600, token_type: 'bearer',
  user: { id: user, is_anonymous: true, aud: 'authenticated' },
 } }));
 const page = await context.newPage(); page.setDefaultTimeout(20000);
 const pageErrors = []; page.on('pageerror', e => pageErrors.push(e.message));
 try {
  await page.goto(web);
  await page.getByRole('button', { name: '로그인 없이 시작하기', exact: true }).click();
  await page.waitForURL('**/input/basic');
  // The same synthetic owner needs an explicit new plan for each scenario.
  const created = await context.request.post(api + '/api/roadmap-inputs', { headers: { Origin: web, Authorization: 'Bearer ' + user } });
  const rid = (await created.json()).request_id;
  await page.evaluate(({ rid, user }) => {
   sessionStorage.clear();
   sessionStorage.setItem('roadmap_request_id', rid);
   sessionStorage.setItem('roadmap_request_owner', user);
  }, { rid, user });
  await page.goto(web + '/input/documents');
  await page.getByText('등록된 문서가 없습니다.', { exact: true }).waitFor();
  await run(page, async () => (await fetch(api + '/__test__/audit/' + rid)).json(), rid);
  assert.deepEqual(pageErrors, []);
  reports.push({ name, status: 'pass' });
  console.log('PASS ' + name);
 } catch (error) {
  reports.push({ name, status: 'fail', message: error.message });
  await page.screenshot({ path: root + '/failure-' + reports.length + '.png', fullPage: true });
  throw error;
 } finally { await context.close(); }
}
try {
 await start();
 browser = await chromium.launch({ executablePath: process.env.P5_BROWSER, headless: true });
 await scenario('1 request starts, reload before body reaches API', async page => {
  let seen; const started = new Promise(resolve => { seen = resolve; });
  await page.route('**/documents', async route => {
   if (route.request().method() === 'POST') { seen(); return route.abort(); }
   await route.continue();
  });
  await choose(page, [file('not-sent.txt')]); await started; await page.reload();
  await page.locator('[data-upload-status="interrupted"]').waitFor();
  assert.equal(await page.locator('[data-document-id]').count(), 0);
  assert.equal(await page.getByRole('button', { name: '다시 업로드', exact: true }).count(), 0);
 });
 for (const [number, stage] of [[2, 'reservation'], [3, 'storage']]) {
  await scenario(`${number} reload during ${stage}`, async (page, audit) => {
   await resetGate(stage); await choose(page, [file(stage + '.txt', 'gate:' + stage)]); await entered(stage);
   await page.reload(); await page.locator('[data-upload-status="server_uploading"]').waitFor();
   assert.equal((await audit()).documents.length, 0);
   // Longer than the test lease: the upload remains live while disconnected.
   await delay(3500); assert.equal((await audit()).uploads[0].cleanup_attempts, 0);
   await release(stage); await count(page, 1);
   assert.equal((await audit()).objects.length, 1);
  });
 }
 await scenario('4 Storage saved, kill before DB registration', async (page, audit) => {
  await resetGate('db'); await choose(page, [file('before-db.txt')]); await entered('db');
  assert.equal((await audit()).objects.length, 1); assert.equal((await audit()).documents.length, 0);
  await kill(); await start(); await page.reload();
  await page.locator('[data-upload-status="interrupted"]').waitFor();
  await poll(async () => (await audit()).objects.length === 0, 'orphan not cleaned');
  await release('db'); await choose(page, [file('before-db.txt')]); await count(page, 1);
 });
 await scenario('5 DB committed, reload before response received', async (page, audit) => {
  let seen, finish;
  const committed = new Promise(resolve => { seen = resolve; });
  const gate = new Promise(resolve => { finish = resolve; });
  await page.route('**/documents', async route => {
   if (route.request().method() !== 'POST') return route.continue();
   await route.fetch(); seen(); await gate; await route.abort().catch(() => {});
  });
  await choose(page, [file('committed.txt')]); await committed;
  assert.equal((await audit()).documents.length, 1);
  await page.reload(); finish(); await count(page, 1);
  assert.equal((await audit()).objects.length, 1);
 });
 await scenario('6 reload during document extraction', async (page, audit) => {
  await resetGate('ocr'); await choose(page, [file('reading.txt', 'gate:ocr')]); await entered('ocr');
  await page.reload(); await count(page, 1); await page.getByText('읽기 중', { exact: true }).waitFor();
  assert.equal((await audit()).documents[0].extraction_status, 'pending');
  await release('ocr'); await page.getByText('읽기 완료 · 분석 포함 가능', { exact: true }).waitFor();
 });
 await scenario('6b reload during scanned PDF OCR, one durable OCR call', async (page, audit) => {
  await resetGate('ocr-service');
  const content = Buffer.from(await (await fetch(api + '/__test__/scan')).arrayBuffer());
  await choose(page, [{ name: 'scanned.pdf', mimeType: 'application/pdf', buffer: content }]);
  await entered('ocr-service'); await page.reload(); await count(page, 1);
  await page.getByText('읽기 중', { exact: true }).waitFor();
  assert.equal((await audit()).ocr_units.length, 1);
  await release('ocr-service'); await page.getByText('읽기 완료 · 분석 포함 가능', { exact: true }).waitFor();
  await page.reload(); await count(page, 1);
  assert.deepEqual((await audit()).ocr_units.map(unit => unit.status), ['completed']);
 });
 await scenario('7 multiple files, reload mid-queue', async (page, audit) => {
  await resetGate('storage');
  await choose(page, [file('first.txt'), file('middle.txt', 'gate:storage'), file('unsent-tail.txt')]); await entered('storage');
  await page.reload(); await page.locator('[data-upload-status="interrupted"]').waitFor();
  await page.locator('[data-upload-status="server_uploading"]').waitFor();
  assert.equal((await audit()).documents.length, 1);
  await release('storage'); await count(page, 2);
  assert.equal(await page.locator('[data-upload-status="interrupted"]').count(), 1);
  await choose(page, [file('unsent-tail.txt')]); await count(page, 3);
 });
 await scenario('8 kill and restart upload server, then restart extraction worker', async (page, audit) => {
  await resetGate('storage'); await choose(page, [file('killed.txt', 'gate:storage')]); await entered('storage');
  await kill(); await start(); await page.reload(); await page.locator('[data-upload-status="interrupted"]').waitFor();
  await release('storage'); await choose(page, [file('killed.txt')]); await count(page, 1);
  await resetGate('ocr'); await choose(page, [file('resume-reading.txt', 'gate:ocr')]); await entered('ocr');
  await kill(); await release('ocr'); await start();
  // Stop all browser polling: only lifespan startup may complete the DB job.
  await page.goto('about:blank');
  await poll(async () => (await audit()).documents.every(doc => doc.extraction_status === 'ready'), 'worker did not resume');
  await page.goto(web + '/input/documents'); await count(page, 2);
 });
 await scenario('9 same file reselection after interrupted request', async (page, audit) => {
  let once = true;
  await page.route('**/documents', route => {
   if (once && route.request().method() === 'POST') { once = false; return route.abort(); }
   return route.continue();
  });
  await choose(page, [file('retry.txt')]); await page.locator('[data-upload-status="failed"]').waitFor();
  await choose(page, [file('retry.txt')]); await count(page, 1);
  assert.equal((await audit()).documents.length, 1); assert.equal((await audit()).objects.length, 1);
 });
 await scenario('10 expired reservation releases tenth slot, live one holds it', async (page, audit) => {
  await choose(page, Array.from({ length: 9 }, (_, n) => file(n + '.txt'))); await count(page, 9);
  await resetGate('storage'); await choose(page, [file('last.txt', 'gate:storage')]); await entered('storage');
  await choose(page, [file('overflow.txt')]); await page.getByText('업로드 실패', { exact: true }).waitFor();
  await kill(); await start(); await page.reload(); await page.locator('[data-upload-status="interrupted"]').waitFor();
  await release('storage'); await choose(page, [file('last.txt')]); await count(page, 10);
  await choose(page, [file('eleventh.txt')]); await page.getByText('업로드 실패', { exact: true }).waitFor();
  assert.equal((await audit()).documents.length, 10); assert.equal((await audit()).objects.length, 10);
  await mkdir(root + '/screenshots'); await page.screenshot({ path: root + '/screenshots/final.png', fullPage: true });
 });
} finally {
 await browser?.close(); await kill();
 await writeFile(root + '/report.json', JSON.stringify({ reports, errors }, null, 2));
 console.log(JSON.stringify({ root, reports, errors }, null, 2));
}
