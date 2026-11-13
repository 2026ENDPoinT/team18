// Real Next + help_ui_server.py API/SQLite. External auth/AI/catalogs are fixtures.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { confirmCourseSelection } from './course-confirmation.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.HELP_WEB_ORIGIN || 'http://localhost:15102';
const artifacts = fileURLToPath(new URL('../../test-results/result-overview/', import.meta.url));
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const tabs = [['실행 로드맵', 'roadmap'], ['직무 역량 비교', 'skills'], ['수강 후보', 'courses'], ['공모전·대외활동', 'activities']];
const goal = '행사 신청 데이터를 분석하는 데이터 분석가가 되고 싶어요. 참여자의 관심 분야와 신청 흐름을 살펴보고 다음 행사를 개선할 수 있는 분석 역량을 기르고 싶어요.';
const report = [];
for (const viewport of [{width:1440,height:900}, {width:390,height:844}]) {
 const context = await browser.newContext({ viewport });
 await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'}}}));
 const page = await context.newPage(), errors = [], requests = [];
 page.on('pageerror', e => errors.push(e.message));
 page.on('request', r => { if (r.url().includes('/api/')) requests.push({ method:r.method(), path:new URL(r.url()).pathname }); });
 const button = name => page.getByRole('button', {name,exact:true});
 const tab = name => page.getByRole('tab', {name,exact:true});
 const go = path => page.goto(origin + path);
 // Course explanations are generated separately; navigation must not regenerate the roadmap.
 const writes = () => requests.filter(r => r.method !== 'GET' && !r.path.endsWith('/course-reasons'));
 const api = suffix => page.evaluate(async suffix => { const r=await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id')+suffix); if(!r.ok)throw Error(await r.text());return r.json(); },suffix);
 const courseCard = page.locator('.result-course-summary');
 const skillCard = page.locator('.result-skill-summary');
 const activityCard = page.locator('.result-activity-summary');
 const ready = async () => { await courseCard.getByRole('heading', {name:'데이터베이스',exact:true}).waitFor(); await activityCard.locator('.result-brief-list a').first().waitFor(); await skillCard.getByRole('list',{name:'분석된 기술 스택'}).getByRole('heading').waitFor(); };
 const clean = async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no page horizontal overflow');
 try {
  await go('/'); await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic');
  await page.locator('[name=career_goal]').fill(goal); await page.locator('[name=target_role]').fill('데이터 분석가');
  await page.locator('[name=university_id]').selectOption('10000000-0000-4000-8000-000000000001');
  await page.locator('[name=department_id]').selectOption('20000000-0000-4000-8000-000000000001');
  await page.getByRole('button',{name:/^저장 후 다음/}).click(); await page.waitForURL('**/input/documents');
  await go('/result'); await courseCard.getByText('아직 수강 추천이 없어요.', {exact:true}).waitFor();
  await activityCard.locator('.result-brief-list a').waitFor();
  assert.equal(await skillCard.getByText('아직 기술 스택 분석이 없어요.', {exact:true}).count(),1);
  const goalOnly = writes().length;
  await page.reload(); await courseCard.getByText('아직 수강 추천이 없어요.', {exact:true}).waitFor();
  assert.equal(writes().length,goalOnly, 'entry and refresh do not generate');
  await go('/input/courses');
  await page.getByRole('switch',{name:/^프로그래밍 기초 /}).click();
  await page.locator('.course-save-status').filter({hasText:'이수 선택이 저장되었습니다.'}).waitFor();
  await confirmCourseSelection(page); await page.waitForURL('**/input/review');
  await go('/result?tab=skills'); await button('직무 분석 실행').click(); await button('직무 분석 다시 실행').waitFor();
  await go('/result?tab=courses'); await button('로드맵 생성').click(); await page.locator('.course-candidates-list').waitFor();
  const plan = await api(''), saved = await api('/roadmap'), selections = await api('/courses?catalog_id='+plan.input.catalog_id+'&page_size=1'), comparison = await api('/skill-comparison'), activities = await api('/activities');
  assert.ok(selections.selected_courses.some(c => c.course_name === '프로그래밍 기초'));
  assert.ok(saved.recommended_courses.some(c => c.course_name === '데이터베이스'));
  assert.ok(!saved.recommended_courses.some(c => c.course_name === '프로그래밍 기초'));
  if(viewport.width===1440)writeFileSync(artifacts+'api-responses.json',JSON.stringify({plan,selections,roadmap:saved,comparison,activities},null,2));
  const before = writes().length;
  await go('/result'); await ready();
  assert.equal(await tab('실행 로드맵').getAttribute('aria-selected'),'true');
  assert.deepEqual(await page.getByRole('tab').allTextContents(),tabs.map(t=>t[0]));
  assert.deepEqual(await page.locator('.result-page').evaluate(el=>[...el.children].slice(0,3).map(n=>n.className)),['page-title-row','result-tabs','result-overview-panel']);
  assert.equal(await page.locator('.page-title-row').innerText(),'로드맵 결과\n?');
  assert.ok(!(await page.locator('.result-basic').innerText()).includes('학교·학과'));
  assert.ok(!(await page.locator('.result-basic').innerText()).includes('한빛대학교'));
  assert.equal(await courseCard.getByText('프로그래밍 기초',{exact:true}).count(),0);
  assert.ok(!(await courseCard.innerText()).includes(saved.recommended_courses[0].personalization_reason));
  assert.equal(await courseCard.locator('input[type=checkbox]').count(),0);
  assert.deepEqual(await skillCard.getByRole('list',{name:'분석된 기술 스택'}).getByRole('heading').allTextContents(),comparison.job_analysis.skills.map(skill=>skill.name));
  assert.equal(await page.locator('.side-nav').getByRole('link',{name:'이수 과목',exact:true}).count(),1);
  assert.equal(await page.locator('.next-task').count(),0);
  const boxes = await Promise.all(['.result-basic','.result-course-summary','.result-skill-summary','.result-activity-summary'].map(s=>page.locator(s).boundingBox()));
  if(viewport.width===1440){
   for(const [width,height] of [[1920,1080],[1640,911],[1440,900],[1366,768]]){
    await page.setViewportSize({width,height});
    const [basic,courses,role,activity]=await Promise.all(['.result-basic','.result-course-summary','.result-skill-summary','.result-activity-summary'].map(s=>page.locator(s).boundingBox()));
    assert.equal(basic.x,courses.x);assert.equal(basic.width,courses.width);
    assert.ok(courses.y>=basic.y+basic.height);
    for(const card of [role,activity]){
     assert.equal(card.y,basic.y);
     assert.ok(Math.abs(card.y+card.height-(courses.y+courses.height))<1);
    }
    await clean();
   }
   await page.setViewportSize(viewport);
  }
  else for(let i=1;i<boxes.length;i++)assert.ok(boxes[i].y>=boxes[i-1].y+boxes[i-1].height);
  await clean(); await page.addStyleTag({content:'nextjs-portal{display:none}'}); await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:artifacts+`result-${viewport.width}.png`,animations:'disabled'});
  await page.screenshot({path:artifacts+`result-${viewport.width}-full.png`,fullPage:true,animations:'disabled'});
  if(viewport.width===1440 && process.env.CAPTURE_HELP==='1') await page.locator('#main-content').screenshot({path:fileURLToPath(new URL('../../public/help/result-roadmap.png',import.meta.url)),animations:'disabled'});
  await page.evaluate(()=>window.scrollTo(0,0));
  const titleY=(await page.locator('.page-title-row').boundingBox()).y, tabY=(await page.locator('.result-tabs').boundingBox()).y;
  for (const [label,key] of tabs) {
   await tab(label).click(); await page.waitForURL('**/result?tab='+key);
   await page.evaluate(()=>window.scrollTo(0,0));
   if(key==='roadmap')await ready();
   if(key==='skills')await button('직무 분석 다시 실행').waitFor();
   if(key==='courses'){await page.locator('.course-candidates-list .recommendation-reason').filter({hasText:'행사 신청 데이터를 분석하려는 목표와 연결해 SQL 조회·집계 내용을 살펴볼 수 있어요.'}).first().waitFor();await page.locator('.course-learning summary').first().click();}
   if(key==='activities')await page.locator('.activity-recommendations .skill-card').first().waitFor();
   assert.equal((await page.locator('.page-title-row').boundingBox()).y,titleY);
   assert.equal((await page.locator('.result-tabs').boundingBox()).y,tabY);
   assert.equal(await tab(label).evaluate(el=>getComputedStyle(el).borderBottomColor),'rgb(68, 98, 222)');
   assert.equal(await tab(label).evaluate(el=>getComputedStyle(el).fontWeight),'700');
   if(viewport.width===1440&&process.env.CAPTURE_HELP==='1'&&key!=='roadmap')await page.locator('#main-content').screenshot({path:fileURLToPath(new URL(`../../public/help/result-${key}.png`,import.meta.url)),animations:'disabled'});
   await button(label+' 예시 보기').click();const dialog=page.getByRole('dialog');await dialog.waitFor();
   await dialog.locator('img').evaluate(el=>el.decode());assert.equal(await dialog.locator('img').getAttribute('src'),`/help/result-${key}.png`);
   await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
   assert.equal(await button(label+' 예시 보기').evaluate(el=>el===document.activeElement),true);
   await page.reload();await tab(label).waitFor();assert.equal(await tab(label).getAttribute('aria-selected'),'true');await clean();
  }
  await tab('실행 로드맵').click();await page.waitForURL('**/result?tab=roadmap');
  await tab('실행 로드맵').focus();
  for(const [label,key] of tabs.slice(1)){await page.keyboard.press('ArrowRight');await page.waitForURL('**/result?tab='+key);assert.equal(await tab(label).evaluate(el=>el===document.activeElement),true);assert.equal(await tab(label).getAttribute('aria-selected'),'true');}
  await page.keyboard.press('ArrowRight');await page.waitForURL('**/result?tab=roadmap');
  await page.keyboard.press('ArrowLeft');await page.waitForURL('**/result?tab=activities');
  await page.keyboard.press('Home');await page.waitForURL('**/result?tab=roadmap');
  await page.keyboard.press('End');await page.waitForURL('**/result?tab=activities');
  await page.goBack();await page.waitForURL('**/result?tab=roadmap');await ready();
  await context.route('https://www.contestkorea.com/**',route=>route.fulfill({contentType:'text/html',body:'<h1>활동 원문 연결 검증</h1>'}));
  const original=activityCard.locator('.result-brief-list a').first(), href=await original.getAttribute('href');
  const popupPromise=page.waitForEvent('popup');await original.click();const popup=await popupPromise;await popup.waitForLoadState();assert.equal(popup.url(),href);await popup.close();
  await go('/dashboard');await page.waitForURL('**/result?tab=roadmap');await ready();
  assert.equal(await page.getByRole('link',{name:'대시보드',exact:true}).count(),0);
  await tab('공모전·대외활동').click();await page.waitForURL('**/result?tab=activities');
  await button('결과 확인 완료 · 로드맵 요약 →').click();await page.waitForURL('**/result?tab=roadmap');
  assert.equal(await tab('실행 로드맵').evaluate(el=>el===document.activeElement),true);
  assert.equal(writes().length,before,'tabs, refresh, legacy redirect, help and source link never write/generate');
  await go('/result?tab=skills');
  const editor=page.getByRole('region',{name:'진로 정보 수정',exact:true});
  await editor.getByRole('button',{name:'수정',exact:true}).click();
  await editor.getByRole('textbox',{name:/희망 직무/}).fill('작성 중인 직무');
  const beforeFocus = requests.length;
  await page.evaluate(async () => {
   window.dispatchEvent(new Event('focus'));
   document.dispatchEvent(new Event('visibilitychange'));
   await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  assert.equal(requests.length,beforeFocus,'returning to the window does not reload result data');
  assert.equal(await editor.getByRole('textbox',{name:/희망 직무/}).inputValue(),'작성 중인 직무','returning to the window preserves an unsaved career draft');
  await editor.getByRole('button',{name:'취소',exact:true}).click();
  await go('/result?tab=roadmap&view=steps');await ready();
  assert.equal(await page.locator('.next-task,.roadmap-tasks,.roadmap-history').count(),0);
  assert.equal(await page.locator('a[href*="view=steps"]').count(),0);
  await tab('수강 후보').click();await page.locator('.course-candidates-list').waitFor();
  assert.equal(await button('현재 입력으로 다시 분석').count(),0);
  assert.equal(await button('저장 결과 새로고침').count(),0);
  assert.equal((await api('/roadmap')).run_id,saved.run_id);
  // Isolate read failures, empty results and pending reads without modifying saved data.
  await page.route('**/roadmap',route=>route.fulfill({status:503,json:{message:'저장 결과 조회 실패'}}));
  await go('/result');await courseCard.getByRole('alert').waitFor();await activityCard.locator('.result-brief-list a').waitFor();assert.ok((await page.locator('.result-basic').innerText()).includes(goal));
  await page.unroute('**/roadmap');await courseCard.getByRole('button',{name:'다시 조회'}).click();await ready();
  await page.route('**/roadmap',async route=>{const response=await route.fetch();await route.fulfill({response,json:{...await response.json(),recommended_courses:[]}});});
  await page.reload();await courseCard.getByText('현재 조건에 맞는 추천 과목이 없어요.',{exact:true}).waitFor();await page.unroute('**/roadmap');
  let release;const held=new Promise(r=>release=r);
  await page.route('**/roadmap',async route=>{await held;await route.continue();});await go('/result');await courseCard.getByText('수강 추천을 불러오는 중이에요…',{exact:true}).waitFor();release();await ready();await page.unroute('**/roadmap');
  await page.route('**/activities',route=>route.fulfill({status:503,json:{message:'활동 조회 실패'}}));await page.reload();await activityCard.getByRole('alert').waitFor();await page.unroute('**/activities');
  await page.route('**/activities',route=>route.fulfill({json:{status:'success',activities:[],sources:[]}}));await page.reload();await activityCard.getByText('현재 추천 조건에 맞는 활동이 없어요.',{exact:true}).waitFor();await page.unroute('**/activities');
  await page.route('**/activities',route=>route.fulfill({json:{...activities,activities:[{...activities.activities[0],kind:'extracurricular',status:'upcoming'}]}}));await page.reload();await activityCard.getByText('대외활동 · 접수 예정',{exact:true}).waitFor();await page.unroute('**/activities');
  await page.route('**/skill-comparison',route=>route.fulfill({status:503,json:{message:'직무 조회 실패'}}));await page.reload();await skillCard.getByRole('alert').waitFor();await activityCard.locator('.result-brief-list a').waitFor();await page.unroute('**/skill-comparison');
  await clean();assert.deepEqual(errors,[]);
  report.push({viewport,completedCourse:'프로그래밍 기초',recommendedCourse:'데이터베이스',reason:saved.recommended_courses[0].personalization_reason,checks:'layout, four tabs, active underline, arrows/Home/End, back/reload, help, legacy redirect, original link, GET-only visits, independent failure/empty/loading, goal-only activities, initial generation, removed execution UI, saved-result reuse',passed:true});
  console.log('PASS result overview '+viewport.width+'×'+viewport.height);
 } catch(error) {await page.screenshot({path:artifacts+`failure-${viewport.width}.png`,fullPage:true});console.error(await page.locator('body').innerText());throw error;}
 finally {await context.close();}
}
await browser.close();writeFileSync(artifacts+'report.json',JSON.stringify(report,null,2));
