// Next :15102 + apps/api/tests/integration/explore_ui_server.py.
// Real API/SQLite/parser; external authentication/AI are fixtures. No production data.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.EXPLORE_WEB_ORIGIN || 'http://localhost:15102';
const artifacts = process.env.EXPERIENCE_ARTIFACTS || '/tmp/team18-experience-answer-states';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const errors = [], external = [], writes = [];
await context.route('**/*', route => {
 const host = new URL(route.request().url()).hostname;
 if (['localhost', '127.0.0.1'].includes(host)) return route.continue();
 if (host === 'job-skills-test.supabase.co') return route.fulfill({ json: { access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer', user: { id: '12345678-0000-4000-8000-000000000002', is_anonymous: true, aud: 'authenticated' } } });
 external.push(host); return route.abort();
});
const page = await context.newPage();
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (r.method() === 'PATCH' && r.url().endsWith('/confirmation')) writes.push(r.postDataJSON()); });
const labels = { confirmed: '맞아요', corrected: '수정할게요', unknown: '잘 모르겠어요', no_experience: '이 기술 경험 없어요' };
const answerBadges = { confirmed: '본인 경험으로 확인', corrected: '사용자가 수정', unknown: '판단 보류', no_experience: '경험 없다고 답변' };
const button = name => page.getByRole('button', { name, exact: true });
const card = skill => page.locator('.skill-card').filter({ has: page.getByText('기술 스택: ' + skill, { exact: true }) });
const answer = (skill, status) => card(skill).getByRole('button', { name: labels[status], exact: true });
async function poll(check, label) { for (let i = 0; i < 200; i++) { if (await check()) return; await delay(100); } throw Error('Timeout: ' + label); }
const ready = () => poll(() => button('프로젝트 경험 분석 실행').isEnabled(), 'review ready');
async function api(path = '/project-experience-analysis', options) {
 return page.evaluate(async ({ path, options }) => {
  const r = await fetch('/api/roadmap-inputs/' + sessionStorage.getItem('roadmap_request_id') + path, options);
  if (!r.ok) throw Error(await r.text());
  return r.json();
 }, { path, options });
}
async function selected(skill, status) {
 const buttons = card(skill).locator('.experience-actions > button');
 assert.equal(await buttons.count(), 4);
 assert.equal(await card(skill).locator('.experience-actions > [aria-pressed=true]').count(), status ? 1 : 0, skill);
 for (const [value, label] of Object.entries(labels)) {
  const control = card(skill).getByRole('button', { name: label, exact: true });
  assert.equal(await control.getAttribute('aria-pressed'), String(value === status), `${skill}: ${label}`);
 }
 if (!status) return;
 await page.mouse.move(0, 0);
 const style = await answer(skill, status).evaluate(el => { const s = getComputedStyle(el); return [s.backgroundColor, s.color, s.borderColor]; });
 assert.deepEqual(style, ['rgb(83, 109, 231)', 'rgb(255, 255, 255)', 'rgb(83, 109, 231)'], 'persistent brand blue, white text and blue border');
 for (const other of Object.keys(labels).filter(value => value !== status)) {
  assert.equal(await answer(skill, other).evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(255, 255, 255)');
 }
}
async function saveAnswer(skill, status, trigger) {
 const response = page.waitForResponse(r => r.url().endsWith('/confirmation') && r.request().method() === 'PATCH');
 await (trigger ? trigger() : answer(skill, status).click());
 assert.equal((await response).status(), 200); await ready();
 await selected(skill, status);
 assert.equal(await card(skill).locator('form').count(), 0);
 assert.ok((await card(skill).locator('[aria-label="경험 상태"]').innerText()).includes(answerBadges[status]));
}
async function layout() {
 const results = await page.locator('.skill-card').evaluateAll(cards => cards.map(card => {
  const title = card.querySelector('.skill-title'), badges = card.querySelector('[aria-label="경험 상태"]');
  const stack = [...card.children].find(el => el.tagName === 'P'), actions = card.querySelector('.experience-actions');
  const t = title.getBoundingClientRect(), b = badges.getBoundingClientRect(), s = stack.getBoundingClientRect(), a = actions.getBoundingClientRect();
  return { allBelow: [...card.querySelectorAll('.badge')].every(el => el.parentElement === badges && el.getBoundingClientRect().top >= t.bottom),
   order: b.top >= t.bottom && s.top >= b.bottom && a.top >= s.bottom,
   left: Math.abs(t.left - b.left) < 1, wrap: getComputedStyle(badges).flexWrap,
   bounded: [...badges.children].every(el => el.getBoundingClientRect().right <= b.right + 1),
   sideBadges: title.querySelectorAll('.badge').length };
 }));
 for (const result of results) assert.deepEqual(result, { allBelow: true, order: true, left: true, wrap: 'wrap', bounded: true, sideBadges: 0 });
 assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow');
}
try {
 await page.goto(origin); await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic');
 await page.locator('[name=career_goal]').fill('데이터 분석 프로젝트를 준비합니다');
 await page.locator('[name=target_role]').fill('데이터 분석가');
 await page.locator('[name=university_id]').selectOption({ index: 1 });
 await page.locator('[name=department_id]').selectOption({ index: 1 });
 await button('저장 후 다음 →').click(); await page.waitForURL('**/input/documents');
 const originalActivity = 'React 화면과 키보드 탐색, 경로 안내 문구를 구현했습니다. 팀원 두 명은 길 조사와 경로 탐색 API를 각각 맡았습니다.';
 await page.getByLabel('프로젝트 문서 선택').setInputFiles({ name: 'experience-states.txt', mimeType: 'text/plain', buffer: Buffer.from(originalActivity + '\n팀원 민수는 Docker로 배포 환경을 구성했습니다.\n제가 SQL로 신청 데이터 조회 쿼리를 작성했습니다.\n제가 Python으로 통계를 정리했습니다.') });
 await poll(() => button('다음: 이수 과목').isEnabled(), 'document ready');
 await page.goto(origin + '/input/review'); await ready();
 await button('프로젝트 경험 분석 실행').click(); await ready();
 assert.equal(await page.locator('.skill-card').count(), 4);
 assert.equal(await page.getByRole('group', { name: '경험 상태', exact: true }).count(), 4);
 assert.ok((await card('React').innerText()).includes('문서 분석: 수행 주체 미확인'));
 const initial = await api();
 for (const skill of ['React', 'Docker', 'SQL', 'Python']) await selected(skill, null);
 await layout(); console.log('PASS 1: all analysis/answer badges below descriptions, left aligned and wrapping');

 // Switching from an editor discards only that card's draft and persists one answer.
 for (const status of ['confirmed', 'unknown', 'no_experience']) {
  await answer('React', 'corrected').click(); await selected('React', 'corrected');
  assert.ok((await card('React').locator('[aria-label="경험 상태"]').innerText()).includes('수정 중 · 미저장'));
  await layout();
  await card('React').locator('textarea').fill('저장하지 않을 초안');
  await answer('React', 'corrected').click();
  assert.equal(await card('React').locator('textarea').inputValue(), '저장하지 않을 초안', 'repeated edit click keeps the current draft');
  await saveAnswer('React', status);
  const text = await card('React').locator('[aria-label="경험 상태"]').innerText();
  assert.equal(text.includes('수행 주체 미확인'), status === 'unknown', 'only unresolved ownership retains the analysis badge');
  assert.equal(writes.at(-1).correction, undefined);
  await answer('React', 'corrected').click();
  assert.equal(await card('React').locator('textarea').inputValue(), originalActivity, 'discarded draft never comes back');
  await card('React').getByRole('button', { name: '수정 취소', exact: true }).click();
  await selected('React', status);
 }
 console.log('PASS 2–5: edit→confirm/defer/no experience closes editor; only the chosen answer stays blue; draft reset and resolved badges');

 // Real keyboard events: Tab order, Enter/Space, visible focus and focus return.
 await answer('React', 'confirmed').focus();
 await page.keyboard.press('Tab');
 assert.ok(await answer('React', 'corrected').evaluate(el => el === document.activeElement));
 assert.equal(await answer('React', 'corrected').evaluate(el => getComputedStyle(el).outlineWidth), '3px');
 await page.keyboard.press('Enter'); await card('React').locator('form').waitFor();
 await page.keyboard.press('Tab');
 assert.ok(await answer('React', 'unknown').evaluate(el => el === document.activeElement));
 await saveAnswer('React', 'unknown', () => page.keyboard.press('Space'));
 await answer('React', 'confirmed').focus();
 await saveAnswer('React', 'confirmed', () => page.keyboard.press('Enter'));
 await answer('Docker', 'corrected').click(); await card('Docker').locator('textarea').fill('Docker의 독립 초안');
 await saveAnswer('SQL', 'unknown');
 assert.equal(await card('Docker').locator('textarea').inputValue(), 'Docker의 독립 초안');
 await selected('Docker', 'corrected'); await selected('React', 'confirmed');
 await saveAnswer('Python', 'no_experience');
 await card('Docker').getByRole('button', { name: '수정 취소', exact: true }).click();
 await selected('Docker', null);
 assert.ok(await answer('Docker', 'corrected').evaluate(el => el === document.activeElement));
 console.log('PASS 6: independent card answers/drafts, keyboard Tab/Enter/Space and focus return');

 // Failed correction preserves its draft and never reports saved correction status.
 await answer('Docker', 'corrected').click();
 await card('Docker').getByLabel('기술명', { exact: true }).fill('Docker Compose');
 await card('Docker').locator('textarea').fill('배포 설정과 재시도 스크립트를 직접 작성했습니다.');
 await card('Docker').locator('select').selectOption('personal');
 let releaseCorrection, correctionEntered;
 const correctionGate = new Promise(resolve => releaseCorrection = resolve), correctionPending = new Promise(resolve => correctionEntered = resolve);
 await page.route('**/project-experiences/*/confirmation', async route => { correctionEntered(); await correctionGate; await route.fulfill({ status: 503, json: { message: '수정 저장 실패 검증' } }); }, { times: 1 });
 try {
  await card('Docker').getByRole('button', { name: '수정 내용 저장', exact: true }).click(); await correctionPending;
  for (const field of await card('Docker').locator('form input, form textarea, form select').all()) assert.ok(await field.isDisabled(), 'draft cannot change during submission');
 } finally { releaseCorrection(); }
 await page.getByRole('alert').filter({ hasText: '수정 저장 실패 검증' }).waitFor(); await ready();
 assert.equal(await card('Docker').getByLabel('기술명', { exact: true }).inputValue(), 'Docker Compose');
 assert.ok(!(await card('Docker').locator('[aria-label="경험 상태"]').innerText()).includes('사용자가 수정'));
 assert.equal((await api()).experiences.find(e => e.skill_name === 'Docker').user_answer, null);
 const correctedResponse = page.waitForResponse(r => r.url().endsWith('/confirmation'));
 await card('Docker').getByRole('button', { name: '수정 내용 저장', exact: true }).click();
 assert.equal((await correctedResponse).status(), 200); await ready();
 await selected('Docker Compose', 'corrected'); assert.equal(await card('Docker Compose').locator('form').count(), 0);
 assert.ok(await answer('Docker Compose', 'corrected').evaluate(el => el === document.activeElement));
 assert.ok((await card('Docker Compose').innerText()).includes('수정한 수행 범위: 본인 직접 수행'));
 assert.ok((await card('Docker Compose').innerText()).includes('사용자가 수정'));
 assert.deepEqual(Object.keys(writes.at(-1)).sort(), ['correction', 'expected_input_revision', 'status']);

 // A pending/failed alternative must keep the previously persisted correction selected.
 await answer('Docker Compose', 'corrected').click();
 await card('Docker Compose').locator('textarea').fill('버릴 재수정');
 let release, entered;
 const gate = new Promise(resolve => release = resolve), pending = new Promise(resolve => entered = resolve);
 await page.route('**/project-experiences/*/confirmation', async route => { entered(); await gate; await route.fulfill({ status: 503, json: { message: '답변 저장 실패 검증' } }); }, { times: 1 });
 try {
  await answer('Docker Compose', 'no_experience').click(); await pending;
  assert.equal(await card('Docker Compose').locator('form').count(), 0);
  assert.equal(await answer('Docker Compose', 'corrected').getAttribute('aria-pressed'), 'true');
  assert.equal(await answer('Docker Compose', 'no_experience').getAttribute('aria-pressed'), 'false');
  assert.ok(await answer('Docker Compose', 'no_experience').isDisabled());
 } finally { release(); }
 await page.getByRole('alert').filter({ hasText: '답변 저장 실패 검증' }).waitFor(); await ready();
 await selected('Docker Compose', 'corrected');
 await answer('Docker Compose', 'corrected').click();
 assert.equal(await card('Docker Compose').locator('textarea').inputValue(), '배포 설정과 재시도 스크립트를 직접 작성했습니다.');
 await card('Docker Compose').getByRole('button', { name: '수정 취소', exact: true }).click();
 console.log('PASS: correction retry, persisted correction retained after failed alternative, no premature success while saving');

 const expected = { React: 'confirmed', 'Docker Compose': 'corrected', SQL: 'unknown', Python: 'no_experience' };
 async function restored() {
  await ready();
  for (const [skill, status] of Object.entries(expected)) {
   await selected(skill, status);
   assert.ok((await card(skill).locator('[aria-label="경험 상태"]').innerText()).includes(answerBadges[status]));
  }
  assert.equal(await page.locator('.experience-correction').count(), 0); await layout();
 }
 await page.reload(); await restored();
 await page.locator('footer').getByRole('link', { name: /이전/ }).click(); await page.waitForURL('**/input/courses');
 await page.goBack(); await restored();
 await button('최신 내용 불러오기').click(); await restored();
 const persisted = await api();
 for (const item of persisted.experiences) {
  const original = initial.experiences.find(e => e.experience_id === item.experience_id);
  for (const key of ['activity', 'contribution_scope', 'evidence_text']) assert.equal(item[key], original[key], 'original analysis stays intact');
  const name = item.user_answer.status === 'corrected' ? item.user_answer.correction.skill_name : item.skill_name;
  assert.equal(item.user_confirmation, expected[name]); assert.equal(item.user_answer.status, expected[name]);
 }
 // This is the existing endpoint consumed by roadmap generation; answers remain unchanged.
 const comparison = await api('/skill-comparison');
 assert.deepEqual(comparison.project_analysis.experiences.map(e => e.user_answer), persisted.experiences.map(e => e.user_answer));
 console.log('PASS 7: real API/DB save and reload, previous-step navigation, refresh, original evidence and downstream answer payload');

 // A successful answer after a saved correction clears that old correction on the server.
 await answer('Docker Compose', 'corrected').click();
 const replaced = page.waitForResponse(r => r.url().endsWith('/confirmation'));
 await answer('Docker Compose', 'unknown').click(); assert.equal((await replaced).status(), 200); await ready();
 await selected('Docker', 'unknown'); assert.equal(await card('Docker').locator('form').count(), 0);
 assert.equal((await api()).experiences.find(e => e.skill_name === 'Docker').user_answer.correction, null);
 // Explicit unresolved corrections must retain their scope badge and corrected selection.
 for (const scope of ['unknown', 'team', 'personal']) {
  await answer('Docker', 'corrected').click(); await card('Docker').locator('select').selectOption(scope);
  await saveAnswer('Docker', 'corrected', () => card('Docker').getByRole('button', { name: '수정 내용 저장', exact: true }).click());
  assert.ok((await card('Docker').locator('[aria-label="경험 상태"]').innerText()).includes('수정한 수행 범위: ' + { unknown: '수행 주체 미확인', team: '팀 수행', personal: '본인 직접 수행' }[scope]));
  await layout();
 }
 for (const width of [1440, 390, 320]) {
  await page.setViewportSize({ width, height: 900 }); await layout();
  await page.addStyleTag({ content: 'nextjs-portal{display:none}' });
  await page.screenshot({ path: `${artifacts}/review-${width}.png`, fullPage: true });
 }
 await answer('Docker', 'corrected').click(); await layout();
 await page.screenshot({ path: `${artifacts}/review-editing-320.png`, fullPage: true });
 await card('Docker').getByRole('button', { name: '수정 취소', exact: true }).click();
 assert.deepEqual(errors, []); assert.deepEqual(external, []);
 console.log('PASS: corrected→other clears stale correction; personal/team/unknown scopes; responsive layout at 1440/390/320px');
 console.log('ALL EXPERIENCE ANSWER CHECKS PASSED');
} catch (error) {
 await page.screenshot({ path: `${artifacts}/failure.png`, fullPage: true }).catch(() => {});
 console.error(await page.locator('body').innerText()); throw error;
} finally { await context.close(); await browser.close(); }
