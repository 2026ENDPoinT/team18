// Real Next -> FastAPI -> SQLite/storage/parser. Start document_upload_ui_server.py
// and Next on :15115 (API :18095), with synthetic Supabase public test settings.
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.DOCUMENT_WEB_ORIGIN || 'http://localhost:15115';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER, headless: true });
const reports = [], failures = [];
const textFile = (name, text = '제가 프로젝트 문서를 작성했습니다.') => ({ name, mimeType: 'text/plain', buffer: Buffer.from(text) });
const savedRows = page => page.locator('tr[data-document-id]');
const names = async page => savedRows(page).locator('td:nth-child(2)').allTextContents();
const waitCount = (page, count) => page.waitForFunction(n => document.querySelectorAll('tr[data-document-id]').length === n && !document.querySelector('[data-upload-status="queued"],[data-upload-status="uploading"],[data-upload-status="uploaded"]'), count);
async function choose(page, files) {
 const choosing = page.waitForEvent('filechooser');
 await page.getByLabel('프로젝트 문서 선택').click();
 const chooser = await choosing;
 assert.equal(chooser.isMultiple(), true);
 await chooser.setFiles(files);
}
async function transfer(page, files) {
 return page.evaluateHandle(files => {
  const data = new DataTransfer();
  files.forEach(f => data.items.add(new File([Uint8Array.from(atob(f.base64), c => c.charCodeAt(0))], f.name, { type: f.mimeType })));
  return data;
 }, files.map(f => ({ name: f.name, mimeType: f.mimeType, base64: f.buffer.toString('base64') })));
}
async function drop(page, files) {
 const dataTransfer = await transfer(page, files);
 await page.locator('.documents-drop-zone').dispatchEvent('dragenter', { dataTransfer });
 await page.locator('.upload-box').dispatchEvent('drop', { dataTransfer });
 assert.equal(await page.locator('.documents-drop-zone.is-dragging').count(), 0);
 await dataTransfer.dispose();
}
async function numbered(page, expected) {
 assert.deepEqual(await names(page), expected);
 assert.deepEqual(await savedRows(page).locator('td:first-child').allTextContents(), expected.map((_, i) => String(i + 1)));
 assert.equal(await savedRows(page).first().locator('td:first-child').evaluate(el => getComputedStyle(el).textAlign), 'center');
}
async function scenario(name, run) {
 if (process.env.DOCUMENT_SCENARIO_FILTER && !name.includes(process.env.DOCUMENT_SCENARIO_FILTER)) return;
 const context = await browser.newContext();
 const errors = [], external = [];
 await context.route('**/*', async route => {
  const url = new URL(route.request().url());
  if (['localhost', '127.0.0.1'].includes(url.hostname)) return route.continue();
  if (url.hostname === 'job-skills-test.supabase.co') return route.fulfill({ json: {
   access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer',
   user: { id: '12345678-0000-4000-8000-000000000001', is_anonymous: true, aud: 'authenticated' },
  } });
  external.push(url.origin); await route.abort();
 });
 const page = await context.newPage();
 page.setDefaultTimeout(20000);
 page.on('pageerror', error => errors.push(error.message));
 try {
  await page.goto(origin);
  await page.getByRole('button', { name: '로그인 없이 시작하기', exact: true }).click();
  await page.waitForURL('**/input/basic');
  await page.goto(origin + '/input/documents');
  await page.getByText('등록된 문서가 없습니다.', { exact: true }).waitFor();
  await run(page);
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  reports.push({ name, status: 'pass' });
 } catch (error) {
  failures.push(error); reports.push({ name, status: 'fail', message: error.message });
  await page.screenshot({ path: `/tmp/document-uploads-failure-${failures.length}.png`, fullPage: true });
 } finally { await context.close(); }
}

try {
 await scenario('file chooser: 3 files, immediate rows, order, extraction, refresh and modal', async page => {
  const files = ['zeta.txt', 'alpha.txt', 'middle.txt'].map(name => textFile(name));
  await choose(page, files);
  await page.locator('[data-upload-status]').first().waitFor();
  assert.equal(await page.locator('[data-upload-status],[data-document-id]').count(), 3);
  await waitCount(page, 3); await numbered(page, files.map(f => f.name));
  await page.waitForFunction(() => [...document.querySelectorAll('tr[data-document-id]')].every(row => row.textContent.includes('읽기 완료')));
  await savedRows(page).first().getByRole('button', { name: '읽힌 내용', exact: true }).click();
  await page.getByRole('dialog').getByText('제가 프로젝트 문서를 작성했습니다.', { exact: true }).waitFor();
  await page.getByRole('button', { name: '닫기', exact: true }).click();
  await page.reload(); await waitCount(page, 3); await numbered(page, files.map(f => f.name));
  await mkdir('/tmp/team18-document-upload-artifacts', { recursive: true });
  await page.screenshot({ path: '/tmp/team18-document-upload-artifacts/desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(await page.locator('.documents-columns').count(), 1);
  await page.screenshot({ path: '/tmp/team18-document-upload-artifacts/mobile.png', fullPage: true, animations: 'disabled' });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 });
 await scenario('drop: 3 formats, nested hover without flicker, drag leave and navigation protection', async page => {
  const files = await Promise.all(['pdf', 'docx', 'txt'].map(async extension => ({ name: `project-ready.${extension}`, mimeType: 'application/octet-stream', buffer: await readFile(new URL(`../../../../docs/test-files/project-ready.${extension}`, import.meta.url)) })));
  const dt = await transfer(page, files);
  const zone = page.locator('.documents-drop-zone');
  const before = await zone.evaluate(el => getComputedStyle(el).borderColor);
  await zone.dispatchEvent('dragenter', { dataTransfer: dt });
  await page.locator('.upload-file-button').dispatchEvent('dragenter', { dataTransfer: dt });
  await page.locator('.upload-file-button').dispatchEvent('dragleave', { dataTransfer: dt });
  assert.equal(await page.locator('.documents-drop-zone.is-dragging').count(), 1);
  await page.waitForFunction(color => getComputedStyle(document.querySelector('.documents-drop-zone')).borderColor !== color, before);
  await zone.dispatchEvent('dragleave', { dataTransfer: dt });
  assert.equal(await page.locator('.documents-drop-zone.is-dragging').count(), 0);
  assert.equal(await page.evaluate(dt => !document.body.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true })), dt), true);
  await dt.dispose();
  await drop(page, files); await waitCount(page, 3); await numbered(page, files.map(f => f.name));
  await page.waitForFunction(() => [...document.querySelectorAll('tr[data-document-id]')].every(row => row.textContent.includes('읽기 완료')));
  await page.reload(); await waitCount(page, 3); await numbered(page, files.map(f => f.name));
 });
 await scenario('existing/case-insensitive duplicates + two duplicates and a new file + same input reselection', async page => {
  await choose(page, [textFile('Report.txt')]); await waitCount(page, 1);
  await choose(page, [textFile('Report.txt'), textFile('REPORT.TXT', 'different size'), textFile('new.txt')]);
  await waitCount(page, 2); await numbered(page, ['Report.txt', 'new.txt']);
  assert.equal(await page.locator('[data-upload-status="duplicate"]').count(), 2);
  for (const name of ['Report.txt', 'REPORT.TXT']) assert.ok((await page.locator('.documents-columns').innerText()).includes(`${name} 파일은 이미 등록되어`));
  await page.reload(); await waitCount(page, 2);
  await choose(page, [textFile('Report.txt')]);
  await page.locator('[data-upload-status="duplicate"]').waitFor();
  await choose(page, [textFile('Report.txt')]);
  assert.equal(await page.locator('[data-upload-status="duplicate"]').count(), 2);
 });
 await scenario('same batch and in-flight duplicates use the same queue for picker and drop', async page => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/documents', async route => {
   if (route.request().method() === 'POST') await gate;
   await route.continue();
  });
  await choose(page, [textFile('same.txt'), textFile('SAME.TXT'), textFile('tail.txt')]);
  await page.locator('[data-upload-status="uploading"]').waitFor();
  await drop(page, [textFile('Same.txt')]);
  assert.equal(await page.locator('[data-upload-status="duplicate"]').count(), 2);
  release(); await waitCount(page, 2); await numbered(page, ['same.txt', 'tail.txt']);
 });
 await scenario('delete renumbers and permits reupload at end; new single upload appends', async page => {
  await choose(page, ['first.txt', 'delete.txt', 'last.txt'].map(name => textFile(name))); await waitCount(page, 3);
  page.on('dialog', dialog => dialog.accept());
  await savedRows(page).nth(1).getByRole('button', { name: '삭제', exact: true }).click();
  await waitCount(page, 2); await numbered(page, ['first.txt', 'last.txt']);
  await choose(page, [textFile('delete.txt')]); await waitCount(page, 3);
  await choose(page, [textFile('single.txt')]); await waitCount(page, 4);
  await page.reload(); await waitCount(page, 4); await numbered(page, ['first.txt', 'last.txt', 'delete.txt', 'single.txt']);
 });
 await scenario('one upload failure and extraction failure are isolated; failed upload retries', async page => {
  await drop(page, [textFile('first.txt'), textFile('retry.txt', 'UPLOAD_FAIL_ONCE'), textFile('last.txt'), textFile('unreadable.txt', 'EXTRACTION_FAIL')]);
  await waitCount(page, 3); await numbered(page, ['first.txt', 'last.txt', 'unreadable.txt']);
  await page.getByText('업로드 실패', { exact: true }).waitFor();
  assert.equal(await page.locator('[data-upload-status="failed"] td:first-child').innerText(), '—');
  await page.getByRole('button', { name: '다시 업로드', exact: true }).click(); await waitCount(page, 4);
  await numbered(page, ['first.txt', 'last.txt', 'unreadable.txt', 'retry.txt']);
  await page.getByText('읽기 실패 · 분석 제외', { exact: true }).waitFor();
  await page.reload(); await waitCount(page, 4);
  await page.getByText('읽기 실패 · 분석 제외', { exact: true }).waitFor();
  assert.equal(await page.locator('[data-upload-status="failed"]').count(), 0);
 });
 await scenario('existing + pending count, size/format/empty/UTF-8 limits keep valid files', async page => {
  await choose(page, Array.from({ length: 9 }, (_, i) => textFile(`${i}.txt`))); await waitCount(page, 9);
  await drop(page, [textFile('bad.png'), textFile('empty.txt', ''), { name: 'large.txt', mimeType: 'text/plain', buffer: Buffer.alloc(10 * 1024 * 1024 + 1, 'a') }, { name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from([255]) }, textFile('overflow.txt')]);
  await waitCount(page, 9);
  assert.equal(await page.locator('[data-upload-status="failed"]').count(), 5);
  await choose(page, [textFile('final.txt'), textFile('one-too-many.txt')]); await waitCount(page, 10);
  assert.equal(await savedRows(page).count(), 10);
  assert.ok((await page.locator('.documents-columns').innerText()).includes('최대 10개'));
  assert.ok((await page.locator('.documents-columns').innerText()).includes('파일당 최대 10MB'));
 });
 await scenario('lost success response reconciles with server without duplicate registration', async page => {
  let once = true;
  await page.route('**/documents', async route => {
   if (once && route.request().method() === 'POST') {
    once = false; await route.fetch(); return route.abort('failed');
   }
   await route.continue();
  });
  await choose(page, [textFile('saved.txt')]); await waitCount(page, 1);
  assert.equal(await page.locator('[data-upload-status="failed"]').count(), 0);
  await page.reload(); await waitCount(page, 1); await numbered(page, ['saved.txt']);
 });
 console.log(JSON.stringify(reports, null, 2));
 if (failures.length) throw new AggregateError(failures, 'Document upload regression failures');
} finally { await browser.close(); }
