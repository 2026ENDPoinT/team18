// Real Next UI with persisted API snapshots. Gemini transport/cache is tested in Python.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RESULT_WEB_ORIGIN || 'http://localhost:15110';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({ access_token: 'test.token.value', refresh_token: 'test-refresh', expires_at: Math.floor(Date.now()/1000)+3600, expires_in: 3600, token_type: 'bearer', user: { id: 'test-user' } }));
 sessionStorage.setItem('roadmap_request_id', 'test-plan'); sessionStorage.setItem('roadmap_request_owner', 'test-user');
 const state = window.reasonState = JSON.parse(sessionStorage.getItem('reason-state') || 'null') || { reads: [], fallback: false, completed: false, legacy: false };
 window.saveReasons = () => sessionStorage.setItem('reason-state', JSON.stringify(state));
 const course = { course_id: 'db', course_name: '데이터베이스', credits: 3, recommended_year: 2, recommended_term: '2학기',
  personalization_reason: '목표와 일치하는 학습 내용: SQL 조회와 집계를 학습합니다.',
  keyword_evidence: [{ keyword: 'SQL', keyword_role: 'learning', evidence_text: 'SQL 조회와 집계를 학습합니다.' }] };
 const comparison = { comparisons: [], project_analysis: { status: 'no_documents' }, job_analysis: { status: 'not_started', skills: [] } };
 const activities = { status: 'success', activities: [], sources: [{ status: 'success' }] };
 const result = () => ({ run_id: 'saved-run', request_id: 'test-plan', status: 'partial', input_revision: 1,
  generation_complete: true, generation_tasks: { comparison: 'unavailable', courses: 'success', activities: 'success', roadmap: 'success' },
  recommended_courses: [course], roadmap: [], career_goal: '데이터 분석', target_role: '데이터 분석가',
  skill_comparison: comparison, activity_recommendations: activities, course_status: 'available',
  ...(!state.legacy ? { course_reasons: [{ course_id: 'db', personalization_reason: state.fallback ? course.personalization_reason : '데이터 분석 목표에 필요한 SQL 조회·집계를 학습하는 과목입니다. 확인된 Python 전처리 경험을 데이터 저장·조회와 연결하는 방향으로 확장할 수 있습니다.' }], course_reasons_source: state.fallback ? 'catalog_evidence_fallback' : 'gemini' } : {}),
  basis: { review_status: 'confirmed', outside_completed_courses: [], catalog: {} },
 });
 const nativeFetch = window.fetch;
 window.fetch = async (input, options = {}) => {
  const url = String(input);
  if (!url.includes('/api/')) return nativeFetch(input, options);
  state.reads.push(`${options.method || 'GET'} ${url}`); window.saveReasons();
  const json = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  if (options.method && options.method !== 'GET') throw new Error('Unexpected mutation/provider trigger: ' + url);
  if (url.endsWith('/roadmap') || url.includes('/roadmaps/')) return json(result());
  if (url.endsWith('/activities')) return json(activities);
  if (url.includes('/skill-comparison')) return json(comparison);
  if (url.includes('/courses?')) return json({ selected_courses: state.completed ? [{ ...course, is_completed: true }] : [] });
  if (url.endsWith('/roadmap-inputs/test-plan')) return json({ request_id: 'test-plan', input_revision: 1, input: { career_goal: '데이터 분석', target_role: '데이터 분석가', catalog_id: 'catalog' } });
  return json({});
 };
});
const page = await context.newPage(), errors = [];
page.on('pageerror', error => errors.push(error.message));
const reason = () => page.locator('.course-candidates-list .recommendation-reason');
const generated = () => reason().filter({ hasText: '확인된 Python 전처리 경험' }).waitFor();
try {
 await page.goto(origin + '/result?tab=courses'); await generated();
 assert.equal(await page.locator('.course-candidates-list h3').innerText(), '데이터베이스');
 assert.match(await page.locator('.course-candidate-meta').innerText(), /3학점.*2학년.*2학기/);
 assert.ok((await reason().innerText()).startsWith('목표와의 연결'));
 assert.ok(!(await reason().innerText()).includes('목표와 일치하는 학습 내용:'));
 assert.equal(await page.locator('.recommendation-reason[aria-busy="true"]').count(), 0);
 await page.locator('.course-learning summary').click();
 await page.locator('.course-learning p').getByText('SQL 조회와 집계를 학습합니다.', { exact: true }).waitFor();
 await page.evaluate(() => { window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange')); });
 for (let i = 0; i < 2; i++) {
  await page.getByRole('tab', { name: '결과 요약', exact: true }).click();
  await page.getByRole('tab', { name: '수강 후보', exact: true }).click(); await generated();
  await page.reload(); await generated();
 }
 for (const width of [1440, 390]) {
  await page.setViewportSize({ width, height: 900 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: `/tmp/team18-personalized-reasons-${width}.png`, fullPage: true });
 }
 for (const legacy of [false, true]) {
  await page.evaluate(legacy => { reasonState.fallback = true; reasonState.legacy = legacy; saveReasons(); }, legacy);
  await page.reload(); await reason().filter({ hasText: '목표와 일치하는 학습 내용:' }).waitFor();
  assert.equal(await page.locator('.result-page [role="alert"]').count(), 0);
  assert.equal(await page.locator('.course-candidates-list h3').count(), 1);
 }
 await page.evaluate(() => { reasonState.completed = true; saveReasons(); });
 await page.reload(); await page.getByText('현재 근거와 미선택 과목에서 추천할 후보를 찾지 못했습니다.', { exact: true }).waitFor();
 assert.equal(await page.locator('.course-candidates-list h3').count(), 0);
 const calls = await page.evaluate(() => reasonState.reads);
 assert.ok(calls.every(call => call.startsWith('GET ') && !call.includes('/course-reasons')));
 assert.deepEqual(errors, []);
 console.log('PASS: saved Gemini text, unchanged card/details, no calls on tabs/reload/focus/expand, immediate cache, fallback/legacy without error banner, completed filter, desktop/mobile');
} finally { await context.close(); await browser.close(); }
