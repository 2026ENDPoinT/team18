// Real Next + course_groups_ui_server.py: real catalog and isolated SQLite saves.
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.COURSE_WEB_ORIGIN || 'http://localhost:15101';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({ json: { access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer', user: { id: 'course-groups-qa-user', is_anonymous: true, aud: 'authenticated' } } }));
const fixtureResponse = await context.request.get(origin + '/api/course-groups-qa');
assert.equal(fixtureResponse.status(), 200);
const fixture = await fixtureResponse.json();
await context.addInitScript(({ requestId }) => {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({ access_token: 'test.token.value', refresh_token: 'test-refresh', expires_at: Math.floor(Date.now() / 1000) + 3600, expires_in: 3600, token_type: 'bearer', user: { id: 'course-groups-qa-user', is_anonymous: true } }));
 sessionStorage.setItem('roadmap_request_id', requestId);
 sessionStorage.setItem('roadmap_request_owner', 'course-groups-qa-user');
}, { requestId: fixture.request_id });

const page = await context.newPage();
const errors = [], patches = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.method() === 'PATCH' && request.url().endsWith('/course-selections')) patches.push(request.postDataJSON().changes); });
const base = origin + '/api/roadmap-inputs/' + fixture.request_id;
const planResponse = await context.request.get(base);
assert.equal(planResponse.status(), 200);
const catalogId = (await planResponse.json()).input.catalog_id;
const catalogUrl = `${base}/courses?catalog_id=${encodeURIComponent(catalogId)}&page_size=100`;
const button = name => page.getByRole('button', { name, exact: true });
const row = course => page.locator(`[data-course-id="${course.course_id}"]`);
const search = page.getByRole('textbox', { name: '과목 검색' });
const only = page.getByRole('checkbox', { name: '선택한 과목만 보기' });
const ids = courses => courses.map(course => course.course_id).sort();
const list = async () => {
 const response = await context.request.get(catalogUrl);
 assert.equal(response.status(), 200);
 return response.json();
};
const sorted = set => [...set].sort();
async function waitForSelection(expected, label) {
 for (let attempt = 0; attempt < 200; attempt++) {
  const current = await list();
  if (JSON.stringify(ids(current.selected_courses)) === JSON.stringify(sorted(expected))) {
   await page.locator('.course-save-status').filter({ hasText: '이수 선택이 저장되었습니다.' }).waitFor();
   return;
  }
  await delay(50);
 }
 assert.deepEqual(ids((await list()).selected_courses), sorted(expected), label);
}
async function toggleCourse(course, target, expected) {
 await row(course).getByRole('switch').click();
 if (target) expected.add(course.course_id); else expected.delete(course.course_id);
 await waitForSelection(expected, course.course_name);
}
async function toggleGroup(label, candidates, target, expected) {
 const start = patches.length;
 await button(`${label} ${target ? '전체 선택' : '전체 해제'}`).click();
 for (const course of candidates) {
  if (target) expected.add(course.course_id); else expected.delete(course.course_id);
 }
 await waitForSelection(expected, label);
 const allowed = new Set(ids(candidates));
 const changes = patches.slice(start).flat();
 assert.ok(changes.length > 0, `${label}: a save was sent`);
 assert.ok(changes.every(change => allowed.has(change.course_id) && change.is_completed === target), `${label}: only displayed courses were sent`);
}

try {
 const catalog = await list();
 const courses = catalog.courses;
 assert.ok(catalog.total > 20, 'the real grouped catalog is used');
 const find = name => {
  const matches = courses.filter(course => course.course_name === name || course.course_name.startsWith(name + ' ('));
  assert.equal(matches.length, 1, name);
  return matches[0];
 };
 const db = find('데이터베이스'), network = find('데이터통신'), analysis = find('데이터분석');
 const mining = find('데이터마이닝'), bigData = find('빅데이터처리');
 const firstYear = courses.find(course => course.recommended_year === 1);
 const otherTerm = find('자료구조'), hiddenSecond = find('알고리즘'), hiddenFourth = find('블록체인');
 const secondTerm = courses.filter(course => course.recommended_year === 2 && String(course.recommended_term).startsWith('2'));
 const dataMatches = [db, network, analysis, mining, bigData];
 assert.deepEqual([db, network, analysis, mining, bigData].map(c => [c.recommended_year, String(c.recommended_term)[0]]), [[2, '2'], [2, '2'], [3, '1'], [4, '2'], [4, '2']]);

 for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
  await page.setViewportSize(viewport);
  // The fixture starts with legacy selections; clear them through the real API.
  const before = await list();
  if (before.selected_courses.length) {
   const response = await context.request.patch(base + '/course-selections', { headers: { Origin: origin }, data: { catalog_id: catalogId, expected_selection_revision: before.selection_revision, changes: before.selected_courses.map(course => ({ course_id: course.course_id, is_completed: false })) } });
   assert.equal(response.status(), 200, await response.text());
  }
  await page.goto(origin + '/input/courses');
  await page.locator('[data-course-id]').first().waitFor();
  assert.equal(await page.locator('[data-course-id]').count(), courses.length);
  const expected = new Set();

  // Without search, all courses in the semester change; other semesters/years do not.
  await toggleCourse(firstYear, true, expected);
  await toggleCourse(otherTerm, true, expected);
  await toggleGroup('2학년 2학기', secondTerm, true, expected);
  assert.equal(await button('2학년 2학기 전체 해제').getAttribute('data-selection'), 'all');
  await toggleGroup('2학년 2학기', secondTerm, false, expected);
  await toggleCourse(hiddenSecond, true, expected);
  await toggleCourse(hiddenFourth, true, expected);

  await search.fill('데');
  assert.deepEqual((await page.locator('[data-course-id]').evaluateAll(rows => rows.map(row => row.dataset.courseId))).sort(), ids(dataMatches));
  assert.equal(await button('2학년 1학기 전체 선택').isDisabled(), true);
  assert.equal(await button('1학년 전체 선택').isDisabled(), true);
  assert.equal(await button('1학년 1학기 전체 선택').isDisabled(), true);
  await toggleGroup('2학년 2학기', [db, network], true, expected);
  await toggleCourse(db, false, expected);
  assert.equal(await button('2학년 2학기 전체 선택').getAttribute('data-selection'), 'some');
  assert.equal(await button('2학년 전체 선택').getAttribute('data-selection'), 'some');
  await toggleGroup('2학년 2학기', [db, network], true, expected);
  await toggleGroup('2학년 2학기', [db, network], false, expected);

  // Clearing search restores all rows without changing the saved hidden selections.
  await search.fill('');
  const displayedSelected = await page.locator('[data-course-id]').evaluateAll(rows => rows.filter(row => row.querySelector('[role=switch]').getAttribute('aria-checked') === 'true').map(row => row.dataset.courseId).sort());
  assert.deepEqual(displayedSelected, sorted(expected));
  await search.fill('데');
  await toggleGroup('2학년 2학기', [db, network], true, expected);
  await toggleGroup('3학년 1학기', [analysis], true, expected);
  await toggleGroup('4학년 2학기', [mining, bigData], true, expected);

  // A year toggle covers matching rows across multiple terms, preserving all others.
  await search.fill('프로그래밍');
  const yearMatches = courses.filter(course => course.recommended_year === 2 && `${course.course_name} ${course.course_code || ''}`.toLocaleLowerCase().includes('프로그래밍'));
  assert.ok(yearMatches.length > 1 && new Set(yearMatches.map(course => course.recommended_term)).size > 1);
  await toggleCourse(yearMatches[0], true, expected);
  assert.equal(await button('2학년 전체 선택').getAttribute('data-selection'), 'some');
  await toggleGroup('2학년', yearMatches, true, expected);
  assert.equal(await button('2학년 전체 해제').getAttribute('data-selection'), 'all');
  await toggleGroup('2학년', yearMatches, false, expected);

  // The selected-only filter hides unselected matches as well as search nonmatches.
  await search.fill('데');
  await toggleCourse(network, false, expected);
  await toggleCourse(bigData, false, expected);
  await only.check();
  assert.deepEqual((await page.locator('[data-course-id]').evaluateAll(rows => rows.map(row => row.dataset.courseId))).sort(), ids([db, analysis, mining]));
  const start = patches.length;
  let release, started;
  const held = new Promise(resolve => { release = resolve; });
  const signal = new Promise(resolve => { started = resolve; });
  await page.route('**/course-selections', async route => { started(); await held; await route.continue(); }, { times: 1 });
  try {
   await button('2학년 2학기 전체 해제').click();
   await signal;
   expected.delete(db.course_id);
   assert.equal(await button('2학년 2학기 전체 선택').isDisabled(), true);
   assert.equal(await button('2학년 전체 선택').isDisabled(), true);
   await button('4학년 전체 해제').click();
   expected.delete(mining.course_id);
   assert.equal(await button('4학년 2학기 전체 선택').isDisabled(), true);
  } finally { release(); }
  await waitForSelection(expected, 'selected-only queued deselection');
  const changes = patches.slice(start).flat();
  assert.deepEqual(changes.map(change => change.course_id).sort(), ids([db, mining]));
  assert.ok(changes.every(change => !change.is_completed));
  assert.ok(expected.has(hiddenSecond.course_id) && expected.has(hiddenFourth.course_id));
  assert.ok(!expected.has(network.course_id) && !expected.has(bigData.course_id));
  assert.ok(expected.has(analysis.course_id));

  // Reload from the server and compare every visible selected row.
  await page.reload();
  await page.locator('[data-course-id]').first().waitFor();
  assert.equal(await search.inputValue(), '');
  assert.equal(await only.isChecked(), false);
  assert.deepEqual(ids((await list()).selected_courses), sorted(expected));
  assert.deepEqual(await page.locator('[data-course-id]').evaluateAll(rows => rows.filter(row => row.querySelector('[role=switch]').getAttribute('aria-checked') === 'true').map(row => row.dataset.courseId).sort()), sorted(expected));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 }
 assert.deepEqual(errors, []);
 console.log('PASS: desktop/mobile filtered semester and year bulk selection, partial/all states, hidden courses, selected-only filter, real saves and reload');
} finally {
 await context.close();
 await browser.close();
}
