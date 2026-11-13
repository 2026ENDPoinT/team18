// Real Next cards; API snapshots are persisted fixtures. SDK/cache covered in Python.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RESULT_WEB_ORIGIN || 'http://localhost:15130';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({ access_token: 'test.token.value', refresh_token: 'test-refresh', expires_at: Math.floor(Date.now()/1000)+3600, expires_in: 3600, token_type: 'bearer', user: { id: 'test-user' } }));
 sessionStorage.setItem('roadmap_request_id', 'test-plan'); sessionStorage.setItem('roadmap_request_owner', 'test-user');
 const state = window.activityState = JSON.parse(sessionStorage.getItem('activity-reason-state') || 'null') || { reads: [], fallback: false, legacy: false };
 window.saveActivityState = () => sessionStorage.setItem('activity-reason-state', JSON.stringify(state));
 const comparison = { comparisons: [], project_analysis: { status: 'no_documents' }, job_analysis: { status: 'not_started', skills: [] } };
 const title = '기후 공공데이터 AI 활용대회';
 const evidence = { posting_field: 'title', posting_quote: title, matched_term: '데이터' };
 const activities = () => ({ status: 'success', sources: [{ source: 'contestkorea', status: 'success' }],
  activities: [{ id: 'climate', source: 'contestkorea', source_label: '콘테스트코리아', kind: 'competition',
   title, status: 'open', category: '데이터 분석', host: '검증용 기관', target: '대학생',
   period: '상시 접수', deadline_label: '상시 접수', url: 'https://example.org/climate',
   evidence: [evidence, evidence], reasons: ['콘테스트코리아: 기존 중복 문장', '콘테스트코리아: 기존 중복 문장'],
   ...(!state.legacy ? { personalization_reason: state.fallback
    ? '공고 제목에서 “기후 공공데이터 AI 활용대회”를 확인했습니다. 진로·경험과의 연결은 원문에서 확인해 주세요.'
    : '스포츠 분야와는 다르지만, 기후 공공데이터 분석으로 분석 방법을 연습할 수 있습니다. 확인한 Python 전처리 경험을 활용하고 시각화 결과를 정리해 제출하는 경험을 쌓을 수 있습니다.' } : {}),
  }] });
 const result = () => ({ run_id: 'saved-run', request_id: 'test-plan', status: 'partial', input_revision: 1,
  generation_complete: true, generation_tasks: { comparison: 'unavailable', courses: 'success', activities: 'success', roadmap: 'success' },
  recommended_courses: [{ course_id: 'db', course_name: '데이터베이스' }], roadmap: [], career_goal: '스포츠 데이터 분석', target_role: '데이터 분석가',
  skill_comparison: comparison, activity_recommendations: activities(), course_status: 'available',
  basis: { review_status: 'confirmed', outside_completed_courses: [], catalog: {} },
 });
 const nativeFetch = window.fetch;
 window.fetch = async (input, options = {}) => {
  const url = String(input);
  if (!url.includes('/api/')) return nativeFetch(input, options);
  state.reads.push(`${options.method || 'GET'} ${url}`); window.saveActivityState();
  const json = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  if (options.method && options.method !== 'GET') throw new Error('Unexpected generation: ' + url);
  if (url.endsWith('/roadmap') || url.includes('/roadmaps/')) return json(result());
  if (url.endsWith('/activities')) return json(activities());
  if (url.includes('/skill-comparison')) return json(comparison);
  if (url.includes('/courses?')) return json({ selected_courses: [] });
  if (url.endsWith('/roadmap-inputs/test-plan')) return json({ request_id: 'test-plan', input_revision: 1, input: { career_goal: '스포츠 데이터 분석', target_role: '데이터 분석가', catalog_id: 'catalog' } });
  return json({});
 };
});
const page = await context.newPage(), errors = [];
page.on('pageerror', error => errors.push(error.message));
const reason = () => page.locator('.activity-recommendations .recommendation-reason');
const generated = () => reason().filter({ hasText: '확인한 Python 전처리 경험' }).waitFor();
try {
 await page.goto(origin + '/result?tab=activities'); await generated();
 assert.equal(await reason().locator('h4').innerText(), '관심 분야와 연결되는 활동');
 assert.equal(await reason().locator('p').count(), 1);
 const card = page.locator('.activity-recommendations .skill-card');
 const metadata = await card.locator('dl').innerText();
 assert.match(metadata, /콘테스트코리아.*데이터 분석.*검증용 기관.*대학생.*상시 접수/s);
 assert.equal(await card.locator('a.button').getAttribute('href'), 'https://example.org/climate');
 for (let i = 0; i < 2; i++) {
  await page.getByRole('tab', { name: '결과 요약', exact: true }).click();
  await page.getByRole('tab', { name: '공모전·대외활동', exact: true }).click(); await generated();
  await page.reload(); await generated();
 }
 await page.evaluate(() => { window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange')); });
 await generated();
 for (const width of [1440, 390]) {
  await page.setViewportSize({ width, height: 900 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await card.screenshot({ path: `/tmp/team18-activity-reasons-${width}.png` });
 }
 for (const legacy of [false, true]) {
  await page.evaluate(legacy => { activityState.fallback = true; activityState.legacy = legacy; saveActivityState(); }, legacy);
  await page.reload(); await reason().filter({ hasText: '원문에서 확인해 주세요' }).waitFor();
  assert.equal(await reason().locator('p').count(), 1);
  assert.equal(await card.locator('dl').innerText(), metadata);
  assert.equal(await page.locator('.result-page [role="alert"]').count(), 0);
  assert.ok(!(await reason().innerText()).includes('기존 중복 문장'));
 }
 assert.ok((await page.evaluate(() => activityState.reads)).every(call => call.startsWith('GET ')));
 assert.deepEqual(errors, []);
 console.log('PASS: saved paragraph, tabs/reload/focus without generation, fallback/legacy cards, unchanged metadata/links, desktop/mobile');
} finally { await context.close(); await browser.close(); }
