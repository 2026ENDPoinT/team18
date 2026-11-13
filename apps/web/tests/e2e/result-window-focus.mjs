// Real Next UI with synthetic API responses; no external services or saved data are changed.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RESULT_WEB_ORIGIN || 'http://localhost:15110';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 700 } });
const input = { catalog_id: 'test-catalog', career_goal: '데이터 분석을 배우고 싶어요.', target_role: '데이터 분석가' };
const plan = { request_id: 'focus-plan', input_revision: 1, activity_basis: 'goal-only', input };
const courses = ['데이터베이스', '선형대수학 (Linear Algebra)', '프로그래밍 기초', '자료구조', '데이터마이닝'].map((course_name, i) => ({
 course_id: `course-${i}`, course_name, credits: 3, recommended_year: 2, recommended_term: '1학기',
 personalization_reason: '데이터 분석 목표에 연결되는 학습 내용입니다.',
 keyword_evidence: [{ keyword: 'SQL', keyword_role: 'learning', evidence_text: '데이터를 조회하고 정리하는 방법을 학습합니다.' }],
}));
const roadmap = { run_id: 'focus-run', status: 'success', input_revision: 1, roadmap: [], recommended_courses: courses,
 course_status: 'success', basis: { catalog: null, review_status: 'confirmed', outside_completed_courses: [] } };
const analysisSkills = ['SQL','Python','긴 이름과 줄바꿈이 필요한 데이터 처리 및 분석 기술','JavaScript','TypeScript','React','Node.js','Docker','Kubernetes','Git','Linux','PostgreSQL','MongoDB','Redis','AWS','Azure','Power BI','Tableau','Excel','Apache Spark'].map(name=>({
 name,category:'other',mentioned_job_count:1,mention_frequency:1,required_job_count:1,preferred_job_count:0,
 mentioned_only_job_count:0,unknown_job_count:0,direct_job_count:1,related_job_count:0,seniority_distribution:{unknown:1},evidence:[],
}));
const comparison = { ...input, input_revision: 1, comparisons: [],
 job_analysis: { status: 'success', snapshot_id: 'snapshot', canonical_role: input.target_role, skills:analysisSkills.slice(0,1) } };
const activities = { ...plan, status: 'success', sources: [],
 evaluated_at: new Date().toISOString(), valid_until: new Date(Date.now() + 300000).toISOString(),
 activities: [1, 2, 3].map(id => ({ id, title: `데이터 분석 공모전 ${id}`, source: 'contestkorea', source_label: '콘테스트코리아',
  kind: 'competition', status: 'open', target: '대학생', reasons: ['데이터 분석 목표와 관련된 활동입니다.'],
  url: `https://example.com/contest/${id}`, deadline_label: '접수 중', period: '테스트 접수 기간' })),
};
const requests = [], errors = [];
let pendingGeneration = false;
await context.addInitScript(() => {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({ access_token: 'test.token.value', refresh_token: 'test-refresh', expires_at: Math.floor(Date.now() / 1000) + 3600, expires_in: 3600, token_type: 'bearer', user: { id: 'focus-user', is_anonymous: true } }));
 sessionStorage.setItem('roadmap_request_id', 'focus-plan');
 sessionStorage.setItem('roadmap_request_owner', 'focus-user');
});
await context.route('**/api/**', route => {
 const request = route.request(), path = new URL(request.url()).pathname;
 requests.push({ method: request.method(), path });
 const json = path.endsWith('/roadmap') ? pendingGeneration ? { status: 'generating', generation_pending: true } : roadmap
  : path.endsWith('/courses') ? { selected_courses: [] }
  : path.endsWith('/skill-comparison') ? comparison
  : path.endsWith('/activities') ? activities
  : path.endsWith('/job-skill-analysis') ? { ...comparison.job_analysis, input_revision: 1 }
  : path.endsWith('/course-reasons') ? { run_id: 'focus-run', provider: 'gemini', reasons: courses.map(c => ({ course_id: c.course_id, personalization_reason: c.personalization_reason })) }
  : plan;
 return route.fulfill({ json });
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
const tab = label => page.getByRole('tab', { name: label, exact: true });
const ready = async key => {
 if (key === 'roadmap') {
  await page.locator('.result-course-summary h3').first().waitFor();
  await page.getByRole('list',{name:'분석된 기술 스택'}).getByRole('heading').first().waitFor();
  await page.locator('.activity-summary[aria-busy=false] .result-brief-list a').first().waitFor();
 } else if (key === 'skills') await page.locator('.job-skills[aria-busy=false] .skill-summary').waitFor();
 else if (key === 'courses') await page.locator('.recommendation-reason').filter({ hasText: courses[0].personalization_reason }).first().waitFor();
 else await page.locator('.activity-recommendations[aria-busy=false] .skill-card').first().waitFor();
};
const returnToWindow = async () => {
 await page.evaluate(() => {
  window.dispatchEvent(new Event('blur'));
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
  document.dispatchEvent(new Event('visibilitychange'));
 });
 // A minute in another app must not trigger an activity timer reload on return.
 await page.clock.fastForward(65000);
 await page.evaluate(() => {
  delete document.visibilityState;
  document.dispatchEvent(new Event('visibilitychange'));
  window.dispatchEvent(new Event('focus'));
 });
 await page.clock.runFor(100);
};
try {
 await page.goto(origin + '/result');
 await ready('roadmap');
 const viewports = [{width:1920,height:1080},{width:1640,height:911},{width:1440,height:900},{width:1366,height:768},{width:390,height:844}];
 const cardHeights = new Map();
 const settle = () => page.evaluate(async()=>{await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
 for(const viewport of viewports){
  await page.setViewportSize(viewport);await settle();
  cardHeights.set(viewport.width,(await page.locator('.result-skill-summary').boundingBox()).height);
 }
 comparison.job_analysis.skills = analysisSkills;
 requests.length = 0;
 await page.reload();await ready('roadmap');
 for(const viewport of [...viewports,...viewports.slice(0,1)]){
  await page.setViewportSize(viewport);await settle();
  const displayed=await page.getByRole('list',{name:'분석된 기술 스택'}).getByRole('heading').allTextContents();
  assert.deepEqual(displayed,analysisSkills.slice(0,displayed.length).map(skill=>skill.name));
  assert.ok(displayed.length>0);
  if(viewport.width>700){
   assert.ok(displayed.length<analysisSkills.length,'many skills do not force the card taller');
   assert.ok(Math.abs((await page.locator('.result-skill-summary').boundingBox()).height-cardHeights.get(viewport.width))<1);
   assert.ok(await page.locator('.result-skill-preview').evaluate(el=>{
    const rows=el.querySelector('ul').children,measure=el.querySelector('.result-skill-measure');
    return rows[rows.length-1].getBoundingClientRect().bottom<=el.getBoundingClientRect().bottom+1 &&
     measure.children[rows.length].getBoundingClientRect().bottom-measure.getBoundingClientRect().top>el.clientHeight;
   }),'show as many complete rows as fit');
  } else assert.equal(displayed.length,analysisSkills.length,'mobile cards grow naturally with all skills');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.equal(await page.locator('.result-skill-summary .summary-link').getAttribute('href'),'/result?tab=skills');
 }
 assert.ok(requests.every(request=>request.method==='GET'),'preview never triggers analysis');
 await page.setViewportSize({width:1440,height:700});await settle();
 console.log('PASS: saved skills fit the card on four desktop sizes, resize back from mobile, all skills remain available');
 await page.clock.install();
 for (const [label, key] of [['실행 로드맵', 'roadmap'], ['직무 역량 비교', 'skills'], ['수강 후보', 'courses'], ['공모전·대외활동', 'activities']]) {
  if (key !== 'roadmap') { await tab(label).click(); await ready(key); }
  if (key === 'skills') {
   const editor = page.getByRole('region', { name: '진로 정보 수정', exact: true });
   await editor.getByRole('button', { name: '수정', exact: true }).click();
   await editor.getByRole('textbox', { name: /희망 직무/ }).fill('작성 중인 직무');
  }
  if (key === 'courses') await page.locator('.course-learning summary').first().click();
  await page.evaluate(() => window.scrollTo(0, 300));
  await page.clock.runFor(100);
  const beforeRequests = requests.length;
  const before = await page.locator('#result-panel').innerHTML();
  const scroll = await page.evaluate(() => scrollY);
  await page.evaluate(() => {
   window.resultChanges = [];
   window.resultObserver = new MutationObserver(changes => resultChanges.push(...changes.map(c => c.type)));
   resultObserver.observe(document.querySelector('#result-panel'), { subtree: true, attributes: true, childList: true, characterData: true });
  });
  for (let i = 0; i < 2; i++) await returnToWindow();
  assert.equal(requests.length, beforeRequests, `${label}: window return makes no API requests`);
  assert.equal(await page.locator('#result-panel').innerHTML(), before, `${label}: rendered content stays unchanged`);
  assert.equal(await page.evaluate(() => scrollY), scroll, `${label}: scroll position stays unchanged`);
  assert.deepEqual(await page.evaluate(() => { resultObserver.disconnect(); return resultChanges; }), [], `${label}: no loading flicker`);
  if (key === 'skills') assert.equal(await page.getByRole('textbox', { name: /희망 직무/ }).inputValue(), '작성 중인 직무');
  if (key === 'courses') assert.equal(await page.locator('.course-learning').first().getAttribute('open'), '');
  console.log(`PASS: ${label} preserves content, scroll and state after window return`);
 }
 assert.equal(requests.filter(r => r.path.endsWith('/activities')).length, 1, 'summary and activity tab share the first response');
 await tab('실행 로드맵').click(); await ready('roadmap');
 const activitySnapshot = await page.locator('.activity-summary').innerHTML();
 const beforeIdle = requests.length;
 // Stay on the summary longer than the old timer and five-minute cache lifetime.
 await page.clock.fastForward(10 * 60000);
 await page.clock.runFor(100);
 assert.equal(requests.length, beforeIdle, 'visible summary never polls or refreshes on cache expiry');
 assert.equal(await page.locator('.activity-summary').innerHTML(), activitySnapshot);
 await tab('공모전·대외활동').click(); await ready('activities');
 assert.equal(requests.filter(r => r.path.endsWith('/activities')).length, 1, 'returning after cache expiry keeps the displayed snapshot');
 const beforeRefresh = requests.filter(r => r.path.endsWith('/activities')).length;
 await Promise.all([
  page.waitForResponse(response => response.url().endsWith('/activities')),
  page.getByRole('button', { name: '활동 추천 다시 확인', exact: true }).click(),
 ]);
 await ready('activities');
 assert.equal(requests.filter(r => r.path.endsWith('/activities')).length, beforeRefresh + 1, 'explicit activity refresh still works');
 await tab('실행 로드맵').click(); await ready('roadmap');
 assert.equal(requests.filter(r => r.path.endsWith('/activities')).length, beforeRefresh + 1, 'summary reuses the manually refreshed result');
 await tab('직무 역량 비교').click(); await ready('skills');
 await Promise.all([
  page.waitForResponse(response => response.url().endsWith('/job-skill-analysis') && response.request().method() === 'POST'),
  page.getByRole('button', { name: '직무 분석 다시 실행', exact: true }).click(),
 ]);
 await ready('skills');
 assert.equal(requests.filter(r => r.path.endsWith('/job-skill-analysis') && r.method === 'POST').length, 1, 'explicit analysis still works');
 // Automatic checks remain necessary only while an already requested generation is pending.
 pendingGeneration = true;
 await page.goto(origin + '/result?tab=courses');
 await page.getByText('진행 중인 생성 요청이 있습니다. 저장 결과를 확인하고 있습니다.', { exact: true }).waitFor();
 pendingGeneration = false;
 await page.clock.runFor(5100);
 await ready('courses');
 assert.deepEqual(errors, []);
 console.log('PASS: no activity polling for ten minutes or across tabs/cache expiry; shared manual refresh; explicit analysis and pending-generation completion still work');
} finally { await context.close(); await browser.close(); }
