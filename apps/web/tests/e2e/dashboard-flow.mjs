// Next :15102 + explore_ui_server.py. Real routes, SQLite and parser; fixed external providers/auth.
import assert from 'node:assert/strict';
import { confirmCourseSelection } from './course-confirmation.mjs';
import { mkdirSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.DASHBOARD_WEB_ORIGIN || 'http://localhost:15102';
const artifacts = '/tmp/team18-dashboard-artifacts'; mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const user = { id: '12345678-0000-4000-8000-000000000002', is_anonymous: true, aud: 'authenticated' };
await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({ json: { access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer', user } }));
const page = await context.newPage(), errors = [], writes = [];
page.on('pageerror', error => errors.push(error.message));
context.on('request', request => { if (request.url().includes('/api/roadmap-inputs') && request.method() !== 'GET') writes.push(request.url()); });
const button = name => page.getByRole('button', { name, exact: true });
const card = name => page.locator('.dashboard-card').filter({ has: page.getByRole('heading', { name, exact: true }) });
const tab = name => page.getByRole('tab', { name, exact: true });
async function poll(check, label) { for (let i = 0; i < 250; i++) { if (await check()) return; await delay(100); } throw Error('Timeout: ' + label); }
async function go(path) { await page.goto(origin + path); }
async function dash() { await go('/dashboard'); await poll(() => page.locator('.dashboard-card').count().then(n => n === 8), 'eight dashboard cards'); }
async function get(suffix = '') { return page.evaluate(async suffix => { const r = await fetch('/api/roadmap-inputs/' + sessionStorage.getItem('roadmap_request_id') + suffix); if (!r.ok) throw Error(await r.text()); return r.json(); }, suffix); }
async function counts() { const data = await (await context.request.get(origin + '/api/review-counters')).json(); const { provider_fixture, ...ai } = data; return ai; }
async function screenshot(name) { await page.addStyleTag({ content: 'nextjs-portal{display:none}' }); await page.screenshot({ path: `${artifacts}/${name}.png`, fullPage: true }); }
async function textHas(locator, text) { assert.ok((await locator.innerText()).includes(text), `Missing ${text}`); }
async function reviewReady() { await poll(() => button('프로젝트 경험 분석 실행').isEnabled(), 'review ready'); }
try {
 await go('/'); await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic');
 const id = (await get()).request_id; assert.ok(id);
 await dash(); assert.equal(writes.filter(url => url.endsWith('/roadmap-inputs')).length, 1);
 await textHas(card('기본 정보'), '학교 미선택'); await textHas(card('경험·문서'), '등록 문서 0개');
 await textHas(card('역량 탐색'), '경험 분석 문서 0개'); await textHas(card('공모전·대외활동'), '목표를 저장하면');
 await screenshot('empty-desktop');
 await card('기본 정보').focus(); await page.keyboard.press('Enter'); await page.waitForURL('**/input/basic');
 await page.locator('[name=career_goal]').fill('데이터 분석 분야의 프로젝트를 준비합니다'); await page.locator('[name=target_role]').fill('데이터 분석가');
 await page.locator('[name=university_id]').selectOption({ index: 1 }); await page.locator('[name=department_id]').selectOption({ index: 1 }); await page.locator('[name=year_level]').selectOption('2');
 await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.', { exact: true }).waitFor();
 const school = await page.locator('[name=university_id] option:checked').innerText(), department = await page.locator('[name=department_id] option:checked').innerText();
 await button('저장').click(); await page.getByRole('status').filter({ hasText: '저장되었습니다.' }).waitFor();
 let ai = await counts(), written = writes.length;
 await page.getByRole('link', { name: '공모전·대외활동 바로 보기', exact: true }).click(); await page.waitForURL('**/result?tab=activities');
 await poll(() => page.locator('.activity-recommendations .skill-card').count().then(n => n > 0), 'goal-only activity');
 const activity = (await get('/activities')).activities[0]; await textHas(page.locator('.activity-recommendations'), activity.title);
 assert.equal(writes.length, written); assert.deepEqual(await counts(), ai);
 await dash(); await textHas(card('기본 정보'), school); await textHas(card('기본 정보'), department); await textHas(card('기본 정보'), '2학년');
 await textHas(card('공모전·대외활동'), activity.title); await textHas(card('공모전·대외활동'), activity.deadline_label);
 await screenshot('partial-desktop'); await card('기본 정보').click(); assert.equal(await page.locator('[name=target_role]').inputValue(), '데이터 분석가');
 await go('/'); await button('이어서 작성').click(); await page.waitForURL('**/input/documents'); assert.equal((await get()).request_id, id);
 console.log('PASS: one-click new guest, eight honest empty cards, keyboard card, saved basic values, goal-only activity shortcut, returning partial plan, read-only dashboard');

 await page.locator('input[type=file]').setInputFiles({ name: 'dashboard-experience.txt', mimeType: 'text/plain', buffer: Buffer.from('제가 React로 행사 신청 화면과 입력 검증을 구현했습니다.\n팀원 민수는 Docker로 배포 환경을 구성했습니다.\n제가 SQL로 신청 데이터 조회 쿼리를 작성했습니다.\n제가 Python으로 통계를 정리했습니다.') });
 await poll(() => button('다음: 이수 과목').isEnabled(), 'document parsed');
 await dash(); await textHas(card('경험·문서'), '등록 문서 1개 · 읽기 완료 1개'); await textHas(card('경험·문서'), 'dashboard-experience.txt'); await textHas(card('역량 탐색'), '경험 분석 문서 0개');
 await card('경험·문서').click(); await textHas(page.locator('body'), 'dashboard-experience.txt');
 await go('/input/courses'); await poll(() => page.getByRole('switch').first().isEnabled(), 'courses loaded');
 for (let i = 0; i < 2; i++) { await page.getByRole('switch').nth(i).click(); await poll(() => page.getByRole('switch').nth(i).isEnabled(), 'toggle saved'); }
 await confirmCourseSelection(page); await page.waitForURL('**/input/review'); await reviewReady();
 await button('프로젝트 경험 분석 실행').click(); await poll(() => page.locator('.skill-card').count().then(n => n === 4), 'four experiences'); await reviewReady();
 const first = page.locator('.skill-card').first(); await first.getByRole('button', { name: '수정할게요', exact: true }).click();
 await first.getByLabel('기술명', { exact: true }).fill('React Native'); await first.locator('textarea').fill('행사 신청 화면과 입력 검증을 직접 구현했어요'); await first.locator('select').selectOption('personal');
 await first.getByRole('button', { name: '수정 내용 저장', exact: true }).click(); await reviewReady();
 await page.reload(); await reviewReady();
 const plan = await get(); const courses = await get('/courses?catalog_id=' + plan.input.catalog_id + '&page_size=1');
 await dash(); await textHas(card('이수 과목'), `선택 ${courses.selection_summary.count}개 · ${courses.selection_summary.known_credits}학점`);
 for (const course of courses.selected_courses.slice(0, 3)) await textHas(card('이수 과목'), course.course_name);
 await textHas(card('역량 탐색'), '행사 신청 화면과 입력 검증을 직접 구현했어요'); await textHas(card('역량 탐색'), 'React Native'); await textHas(card('역량 탐색'), '사용자 수정 답변'); await textHas(card('역량 탐색'), '경험 분석 문서 1개');
 await card('역량 탐색').click(); await reviewReady(); await textHas(page.locator('.skill-card').first(), '행사 신청 화면과 입력 검증을 직접 구현했어요');
 await go('/dashboard'); await card('이수 과목').waitFor(); await card('이수 과목').click();
 await poll(() => page.getByRole('switch', { checked: true }).count().then(n => n === 2), 'selected courses detail');
 console.log('PASS: extraction and experience analysis counted separately, persisted correction, count/credits/course names match detail, all input card destinations');

 await go('/result?tab=skills'); await poll(() => button('직무 분석 실행').isEnabled(), 'job analysis ready'); await button('직무 분석 실행').click();
 await poll(() => button('직무 분석 다시 실행').isEnabled(), 'job saved');
 await tab('실행 로드맵').click(); await button('로드맵 생성').click(); await page.locator('.next-task').waitFor();
 let run = await get('/roadmap'); assert.ok(run.run_id); const task = run.roadmap[0].tasks[0];
 await textHas(page.locator('.next-task'), task.title); await textHas(page.locator('.next-task'), task.deliverable); await textHas(page.locator('.next-task'), run.roadmap[0].reason);
 await page.getByRole('region', { name: '확인할 질문' }).waitFor();
 await screenshot('next-task-desktop');
 await page.setViewportSize({width:390,height:844}); await screenshot('next-task-390'); assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)); await page.setViewportSize({width:1440,height:1000});
 assert.ok((await page.locator('.next-task').boundingBox()).y < (await page.locator('.roadmap-controls').boundingBox()).y);
 await button('이 작업 완료로 표시').click(); await poll(() => page.locator('.next-task').innerText().then(t => t.includes('작업 완료 1 / 3개')), 'task completion saved');
 await dash(); ai = await counts(); written = writes.length;
 const comparison = await get('/skill-comparison'); await textHas(card('직무 역량 비교'), comparison.job_analysis.canonical_role); await textHas(card('직무 역량 비교'), 'SQL');
 run = await get('/roadmap'); await textHas(card('실행 로드맵'), '작업 완료 1 / 3개'); await textHas(card('실행 로드맵'), run.roadmap[1].tasks[0].title);
 assert.ok(run.recommended_courses.length); const course = run.recommended_courses[0]; await textHas(card('수강 후보'), course.course_name); await textHas(card('수강 후보'), course.personalization_reason || course.reason);
 await screenshot('full-desktop');
 for (const [name, key] of [['직무 역량 비교','skills'], ['실행 로드맵','roadmap'], ['수강 후보','courses'], ['공모전·대외활동','activities']]) {
  await card(name).focus(); await page.keyboard.press('Enter'); await page.waitForURL('**/result?tab=' + key); assert.equal(await tab(name).getAttribute('aria-selected'), 'true');
  await page.reload(); assert.equal(await tab(name).getAttribute('aria-selected'), 'true');
  if (key === 'courses') { await page.locator('#result-panel .skill-card').first().waitFor(); await textHas(page.locator('#result-panel'), course.course_name); await textHas(page.locator('#result-panel'), course.course_evidence); await textHas(page.locator('#result-panel'), '공식 교육과정에서 확인한 학습 내용'); }
  if (key === 'activities') { await page.locator('.activity-recommendations .skill-card').first().waitFor(); await textHas(page.locator('.activity-recommendations'), activity.title); await textHas(page.locator('.activity-recommendations'), activity.deadline_label); }
  await page.goBack(); await page.waitForURL('**/dashboard'); await card(name).waitFor();
 }
 await go('/result?tab=skills'); await tab('직무 역량 비교').focus(); await page.keyboard.press('ArrowRight'); await page.waitForURL('**/result?tab=roadmap');
 await page.keyboard.press('ArrowRight'); await page.waitForURL('**/result?tab=courses'); await page.goBack(); await page.waitForURL('**/result?tab=roadmap'); assert.equal(await tab('실행 로드맵').getAttribute('aria-selected'), 'true');
 await page.goBack(); await page.waitForURL('**/result?tab=skills'); assert.equal(await tab('직무 역량 비교').getAttribute('aria-selected'), 'true');
 assert.deepEqual(await counts(), ai); assert.equal(writes.length, written);
 console.log('PASS: full saved cards match all result details, exact tab URL/direct entry/reload/back/keyboard, first pending task and stored reason/deliverable, grouped questions, no implicit AI or mutations');

 await page.route('**/documents', route => route.fulfill({ status: 503, json: { message: '문서 조회 일시 실패' } }));
 await page.route('**/skill-comparison', route => route.fulfill({ status: 503, json: { message: '직무 조회 일시 실패' } }));
 await dash(); await textHas(card('경험·문서'), '불러오지 못했습니다'); assert.ok(!(await card('경험·문서').innerText()).includes('0개'));
 await textHas(card('직무 역량 비교'), '불러오지 못했습니다'); await textHas(card('실행 로드맵'), '작업 완료 1 / 3개'); await textHas(card('역량 탐색'), 'React Native');
 await page.unroute('**/documents'); await page.unroute('**/skill-comparison'); await button('최신 내용 불러오기').click(); await card('경험·문서').waitFor(); await textHas(card('경험·문서'), '읽기 완료 1개');
 for (const width of [390,320]) { await page.setViewportSize({ width, height: 844 }); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)); await screenshot('full-' + width); }
 await page.setViewportSize({ width:1440, height:1000 });
 await go('/'); await button('이어서 작성').click(); await page.waitForURL('**/result?tab=roadmap'); await page.locator('.next-task').waitFor(); assert.equal((await get()).request_id, id);
 await button('이 작업 완료로 표시').click(); await poll(() => page.locator('.next-task').innerText().then(t => t.includes('작업 완료 2 / 3개')), 'second saved');
 await button('이 작업 완료로 표시').click(); await page.getByText('모든 작업을 완료했어요. 저장한 실행 기록을 아래에서 확인하세요.', { exact:true }).waitFor();
 await page.reload(); await textHas(page.locator('.next-task'), '모든 작업을 완료했어요'); await dash(); await textHas(card('실행 로드맵'), '모든 작업을 완료했어요'); await textHas(card('실행 로드맵'), '작업 완료 3 / 3개');
 const newer = await context.newPage(); await newer.goto(origin + '/'); await newer.getByRole('button',{name:'처음부터 작성하기',exact:true}).click(); await newer.waitForURL('**/input/basic');
 await newer.locator('[name=career_goal]').fill('다른 계획의 디자인 관심 분야'); await newer.getByRole('button',{name:'저장',exact:true}).click(); await newer.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await newer.goto(origin + '/dashboard'); await newer.locator('.dashboard-card').first().waitFor(); assert.ok((await newer.locator('.dashboard-card').first().innerText()).includes('다른 계획의 디자인 관심 분야'));
 await page.reload(); await card('기본 정보').waitFor(); await textHas(card('기본 정보'),'데이터 분석 분야의 프로젝트를 준비합니다'); await textHas(card('실행 로드맵'),'작업 완료 3 / 3개'); assert.equal((await get()).request_id,id);
 await newer.close();
 const signed = await browser.newContext();
 await signed.route('https://job-skills-test.supabase.co/**',route=>route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{...user,id:'12345678-0000-4000-8000-000000000003',is_anonymous:false,email:'browser-check@example.test'}}}));
 const signedPage=await signed.newPage(); await signedPage.goto(origin+'/'); await signedPage.getByRole('button',{name:'로그인 없이 시작하기',exact:true}).click(); await signedPage.waitForURL('**/input/basic');
 await signedPage.locator('[name=career_goal]').fill('다른 계정의 환경 관심 분야'); await signedPage.getByRole('button',{name:'저장',exact:true}).click(); await signedPage.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await signedPage.goto(origin+'/'); await signedPage.getByText('로그인됨 · browser-check@example.test',{exact:true}).waitFor(); await signedPage.getByRole('button',{name:'이어서 작성',exact:true}).click(); await signedPage.waitForURL('**/input/documents');
 await signedPage.goto(origin+'/dashboard'); await signedPage.locator('.dashboard-card').first().waitFor(); assert.ok((await signedPage.locator('.dashboard-card').first().innerText()).includes('다른 계정의 환경 관심 분야')); assert.ok(!(await signedPage.locator('body').innerText()).includes('dashboard-experience.txt'));
 await signed.close();
 console.log('PASS: current tab plan retained when a newer plan exists, authenticated-session resume, isolated owner data');
 assert.deepEqual(errors, []); console.log('PASS: independent 503 failures never show zero, retry recovery, 320/390 layouts, returning saved roadmap, all-completed persistence');
 console.log('ALL DASHBOARD BROWSER CHECKS PASSED');
} catch (error) { await screenshot('failure').catch(() => {}); console.error(await page.locator('body').innerText()); throw error; }
finally { await context.close(); await browser.close(); }
