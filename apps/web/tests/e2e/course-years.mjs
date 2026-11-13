// Real Next + disposable SQLite API and the repository's actual catalog snapshot.
// Run course_groups_ui_server.py with Next :15101 → API :18082.
import assert from 'node:assert/strict';
import { confirmCourseSelection, openCourseConfirmation } from './course-confirmation.mjs';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin=process.env.COURSE_WEB_ORIGIN || process.env.JOB_SKILLS_WEB_ORIGIN || 'http://localhost:15101';
const artifacts=process.env.COURSE_ARTIFACTS || '/tmp/team18-course-years';
mkdirSync(artifacts,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});
const fixture=await (await context.request.get(origin+'/api/course-groups-qa')).json();
await context.addInitScript(({rid})=>{
 localStorage.setItem('sb-job-skills-test-auth-token',JSON.stringify({access_token:'test.token.value',refresh_token:'test-refresh',expires_at:Math.floor(Date.now()/1000)+3600,expires_in:3600,token_type:'bearer',user:{id:'course-groups-qa-user',is_anonymous:true}}));
 sessionStorage.setItem('roadmap_request_id',rid);sessionStorage.setItem('roadmap_request_owner','course-groups-qa-user');
},{rid:fixture.request_id});
const page=await context.newPage(), errors=[], pages=[], reviews=[];
page.on('pageerror',error=>errors.push(error.message));
page.on('request',request=>{if(request.url().endsWith('/course-selection-review'))reviews.push(request.postDataJSON());});
const button=name=>page.getByRole('button',{name,exact:true});
const search=page.getByRole('textbox',{name:'과목 검색'});
const row=id=>page.locator(`[data-course-id="${id}"]`);
const base=origin+'/api/roadmap-inputs/'+fixture.request_id;
const plan=()=>context.request.get(base).then(r=>r.json());
const catalog=(await plan()).input.catalog_id;
const all=()=>context.request.get(base+'/courses?catalog_id='+catalog+'&page_size=100').then(r=>r.json());
async function poll(check,label){for(let i=0;i<200;i++){if(await check())return;await delay(75);}throw Error('Timeout: '+label);}
async function ready(){await poll(()=>button('이수 선택 확인').isEnabled(),'catalog ready');}
async function saved(){await page.locator('.course-save-status').filter({hasText:'이수 선택이 저장되었습니다.'}).waitFor();}
async function reset(){await button('필터 초기화').click();await poll(()=>page.locator('[data-course-id]').count().then(n=>n===initial.total),'all courses');}
async function screenshot(name){await page.addStyleTag({content:'nextjs-portal{display:none}'});await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:`${artifacts}/${name}.png`,animations:'disabled'});}
let initial;
try {
 const baseline=await all();
 const changes=baseline.courses.filter(c=>c.is_completed!==['데이터베이스 (Database)','자료구조 (Data Structure)'].includes(c.course_name)).map(c=>({course_id:c.course_id,is_completed:!c.is_completed}));
 if(changes.length)assert.equal((await context.request.patch(base+'/course-selections',{headers:{Origin:origin},data:{catalog_id:catalog,expected_selection_revision:baseline.selection_revision,changes}})).status(),200);

 // Force the real API to return 20 per page, regardless of the client's larger request.
 await page.route('**/courses?*',async route=>{
  const url=new URL(route.request().url());url.searchParams.set('page_size','20');
  const response=await route.fetch({url:url.toString()});pages.push(Number(url.searchParams.get('page')));
  await route.fulfill({response});
 });
 await page.goto(origin+'/input/courses');await ready();initial=await all();
 assert.equal(await page.locator('[data-course-id]').count(),initial.total);
 assert.deepEqual(pages,[1,2,3]);
 assert.ok(initial.total>20);
 for(const course of initial.courses.slice(20))assert.equal(await row(course.course_id).count(),1);
 const counts=await page.locator('.course-year-grid>.course-year').evaluateAll(elements=>elements.map(el=>({year:Number(el.dataset.year),count:el.querySelectorAll('[data-course-id]').length,heading:el.querySelector('header').innerText})));
 assert.equal(counts.reduce((n,item)=>n+item.count,0),initial.total);
 const boxes=await page.locator('.course-year-grid>.course-year').evaluateAll(elements=>elements.map(el=>({x:el.getBoundingClientRect().x,y:el.getBoundingClientRect().y,width:el.getBoundingClientRect().width})));
 assert.equal(new Set(boxes.map(b=>b.y)).size,1);assert.ok(Math.max(...boxes.map(b=>b.width))-Math.min(...boxes.map(b=>b.width))<1);
 assert.ok(boxes.every((b,i)=>!i||b.x>boxes[i-1].x));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth===innerWidth));
 assert.equal(await page.locator('main aside').count(),0);
 assert.equal(await page.getByRole('combobox',{name:'학년 필터'}).count(),0);
 assert.equal(await button('다음 페이지').count(),0);
 await screenshot('courses-desktop-1440');
 // Every term is sorted, including the courses beyond the former first page.
 for(const body of await page.locator('.course-year-table tbody').all()){
  const names=await body.locator('.course-name').allTextContents();
  assert.deepEqual(names,[...names].sort((a,b)=>a.localeCompare(b,'ko')));
 }
 const db=initial.courses.find(c=>c.course_name==='데이터베이스 (Database)');
 for(const query of ['데이터베이스','Database','database',db.course_code.split(' / ').at(-1)]){
  await search.fill(query);await poll(()=>page.locator('[data-course-id]').count().then(n=>n===1),'bilingual search');
  assert.equal(await row(db.course_id).count(),1);
  assert.equal(await page.locator('.course-year-grid>.course-year').count(),4);
  assert.equal(await page.locator('.course-confirm-summary strong').innerText(),`선택 ${initial.selection_summary.count}과목 · ${initial.selection_summary.known_credits}학점`);
 }
 assert.equal(await page.locator('.course-code').count(),0);
 assert.equal(await row(db.course_id).getByRole('switch').getAttribute('aria-label'),`${db.course_name} 이미 이수함`);
 await reset();
 // Hold the first PATCH while toggling all four years, including on→off→on.
 let release, started;const held=new Promise(r=>release=r), signal=new Promise(r=>started=r);
 await page.route('**/course-selections',async route=>{started();await held;await route.continue();},{times:1});
 const chosen=[1,2,3,4].map(year=>initial.courses.find(c=>c.recommended_year===year&&!c.is_completed));
 await row(chosen[0].course_id).getByRole('switch').click();await signal;
 for(const course of chosen.slice(1))await row(course.course_id).getByRole('switch').click();
 await row(chosen[0].course_id).getByRole('switch').click();await row(chosen[0].course_id).getByRole('switch').click();
 for(const course of chosen)assert.equal(await row(course.course_id).getByRole('switch').getAttribute('aria-checked'),'true');
 await search.fill('no-matching-course');
 assert.equal(await page.locator('[data-course-id]').count(),0);assert.equal(await page.locator('.course-year-grid>.course-year').count(),4);
 assert.ok((await page.locator('.course-confirm-summary strong').innerText()).startsWith(`선택 ${initial.selection_summary.count+4}과목`));
 release();await saved();
 const selected=await all();assert.equal(selected.selection_summary.count,initial.selection_summary.count+4);
 for(const course of chosen)assert.ok(selected.selected_courses.some(c=>c.course_id===course.course_id));
 // The preview includes hidden selections, leaves the review unsaved, and restores keyboard focus.
 const dialog=await openCourseConfirmation(page);
 assert.equal(new URL(page.url()).pathname,'/input/courses');assert.equal(reviews.length,0);
 assert.equal(await dialog.locator('[data-selected-course-id]').count(),selected.selection_summary.count);
 assert.deepEqual(await dialog.getByRole('heading',{level:3}).allTextContents(),['1학년','2학년','3학년','4학년']);
 assert.equal(await dialog.getByRole('heading',{level:2}).evaluate(el=>el===document.activeElement),true);
 await page.keyboard.press('Shift+Tab');assert.equal(await button('확인하고 역량 탐색').evaluate(el=>el===document.activeElement),true);
 await page.keyboard.press('Tab');assert.equal(await button('이수 과목 확인 닫기').evaluate(el=>el===document.activeElement),true);
 await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
 assert.equal(await button('이수 선택 확인').evaluate(el=>el===document.activeElement),true);
 assert.equal(await search.inputValue(),'no-matching-course');assert.equal((await all()).selection_summary.count,selected.selection_summary.count);
 await openCourseConfirmation(page);await button('선택 수정').click();await dialog.waitFor({state:'detached'});assert.equal(reviews.length,0);
 await page.reload();await ready();
 for(const course of chosen)assert.equal(await row(course.course_id).getByRole('switch').getAttribute('aria-checked'),'true');
 await page.getByRole('combobox',{name:'전공 구분 필터'}).selectOption(chosen[0].category);
 await page.getByRole('checkbox',{name:'선택한 과목만 보기'}).check();
 assert.equal(await page.getByRole('switch',{checked:false}).count(),0);
 assert.equal(await page.locator('.course-confirm-summary strong').innerText(),`선택 ${selected.selection_summary.count}과목 · ${selected.selection_summary.known_credits}학점`);
 await reset();
 // Group deselection clears both legacy language IDs, and selection keeps the representative ID.
 await row(db.course_id).getByRole('switch').click();await saved();
 let states=(await (await context.request.get(origin+'/api/course-groups-qa')).json()).states;
 assert.ok(states.filter(s=>db.member_course_ids.includes(s.course_id)).every(s=>!s.is_completed));
 await row(db.course_id).getByRole('switch').click();await saved();
 states=(await (await context.request.get(origin+'/api/course-groups-qa')).json()).states;
 assert.deepEqual(states.filter(s=>db.member_course_ids.includes(s.course_id)&&s.is_completed).map(s=>s.course_id),[db.course_id]);
 // Retry preserves all queued choices and requires successful persistence before review.
 await page.route('**/course-selections',route=>route.fulfill({status:503,json:{message:'검증용 일시 저장 실패'}}),{times:1});
 await row(chosen[0].course_id).getByRole('switch').click();await button('다시 저장').waitFor();
 assert.ok(await button('이수 선택 확인').isDisabled());await button('다시 저장').click();await saved();
 await row(chosen[0].course_id).getByRole('switch').click();await saved();
 // Breakpoints, usable drawer, and last-row checkbox above the fixed bar.
 for(const viewport of [{width:1024,height:900},{width:390,height:844},{width:1440,height:900}]){
  await page.setViewportSize(viewport);await page.evaluate(()=>scrollTo(0,0));
  assert.equal(await page.locator('.course-year-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),viewport.width===1440?4:viewport.width===1024?2:1);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth===innerWidth));
  if(viewport.width===390)await screenshot('courses-mobile-390');
  await page.getByRole('button',{name:/선택 목록·누락 신고/}).click();
  await page.getByRole('checkbox',{name:'목록에 없는 이수 과목이 있어요'}).check();
  assert.ok(await page.getByRole('region',{name:'선택 과목 및 누락 신고'}).isVisible());
  await page.getByRole('button',{name:/선택 목록·누락 신고/}).click();
  // Scroll each column's last course into view; hit testing catches footer overlap.
  for(const year of [1,2,3,4]){
   const last=page.locator(`.course-year[data-year="${year}"] [role=switch]`).last();
   await last.scrollIntoViewIfNeeded();
   await last.evaluate(el=>el.scrollIntoView({block:'center'}));
   assert.ok(await last.evaluate(el=>{const r=el.getBoundingClientRect(),bar=document.querySelector('.course-confirm-bar').getBoundingClientRect();return r.top>=0&&r.bottom<=bar.top&&el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),'last check unobscured '+viewport.width);
  }
  if(viewport.width===390)await screenshot('courses-mobile-last-row');
 }
 // Confirmation waits for both PATCH and its refreshed selection snapshot; duplicate clicks are ignored.
 let confirmRelease, confirmStarted;const confirmHeld=new Promise(r=>confirmRelease=r), confirmSignal=new Promise(r=>confirmStarted=r);
 await page.route('**/course-selections',async route=>{confirmStarted();await confirmHeld;await route.continue();},{times:1});
 await row(chosen[0].course_id).getByRole('switch').click();await confirmSignal;
 await button('이수 선택 확인').evaluate(el=>{el.click();el.click();});await delay(150);assert.equal(reviews.length,0);
 await page.getByRole('dialog',{name:'이수 과목 확인',exact:true}).waitFor();
 assert.ok(await button('확인하고 역량 탐색').isDisabled());
 confirmRelease();await saved();
 let submitRelease, submitStarted;const submitHeld=new Promise(r=>submitRelease=r), submitSignal=new Promise(r=>submitStarted=r);
 await page.route('**/course-selection-review',async route=>{submitStarted();await submitHeld;await route.continue();},{times:1});
 await button('확인하고 역량 탐색').evaluate(el=>{el.click();el.click();});await submitSignal;
 assert.ok(await button('선택 수정').isDisabled());await page.keyboard.press('Escape');assert.ok(await dialog.isVisible());assert.equal(reviews.length,1);
 submitRelease();await page.waitForURL('**/input/review');assert.equal(reviews.length,1);assert.equal(reviews[0].reported_missing_courses,true);
 assert.equal((await plan()).review_status,'partial');
 await page.goto(origin+'/input/courses');await ready();
 await page.getByRole('button',{name:/선택 목록·누락 신고/}).click();assert.ok(await page.getByRole('checkbox',{name:'목록에 없는 이수 과목이 있어요'}).isChecked());
 await page.getByRole('button',{name:/선택 목록·누락 신고/}).click();
 // Existing 409 protection remains intact after loading a full catalog.
 const fresh=await all(), external=fresh.courses.find(c=>!c.is_completed);
 assert.equal((await context.request.patch(base+'/course-selections',{headers:{Origin:origin},data:{catalog_id:catalog,expected_selection_revision:fresh.selection_revision,changes:[{course_id:external.course_id,is_completed:true}]}})).status(),200);
 await confirmCourseSelection(page);await page.getByRole('alert').waitFor();assert.ok(await button('확인하고 역량 탐색').isDisabled());
 await button('최신 상태 불러오기').click();await ready();assert.equal(await row(external.course_id).getByRole('switch').getAttribute('aria-checked'),'true');
 // Missing metadata fixture covers fallback locations without changing the catalog or production data.
 await page.unroute('**/courses?*');
 await page.route('**/courses?*',async route=>{
  const response=await route.fetch(),data=await response.json();
  data.courses[0].recommended_year=null;data.courses[0].recommended_term=null;
  data.courses[1].recommended_year=2;data.courses[1].recommended_term=null;
  await route.fulfill({response,json:data});
 });
 await page.reload();await ready();
 assert.equal(await page.locator('.course-unassigned [data-course-id]').count(),1);
 assert.ok(await page.locator('.course-year[data-year="2"]').innerText().then(t=>t.includes('학기 미지정')));
 assert.equal(await page.locator('[data-course-id]').count(),initial.total);
 await button('이수 과목 예시 보기').click();
 await poll(()=>page.getByRole('dialog').locator('img').evaluate(el=>el.complete&&el.naturalWidth>=1000),'updated help image');
 await page.keyboard.press('Escape');
 // A long confirmation is usable at all breakpoints, including the very last row.
 await page.unroute('**/courses?*');
 const beforeAll=await all();
 assert.equal((await context.request.patch(base+'/course-selections',{headers:{Origin:origin},data:{catalog_id:catalog,expected_selection_revision:beforeAll.selection_revision,changes:beforeAll.courses.filter(c=>!c.is_completed).map(c=>({course_id:c.course_id,is_completed:true}))}})).status(),200);
 await page.reload();await ready();await openCourseConfirmation(page);
 for(const viewport of [{width:1440,height:900},{width:1024,height:900},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  const scroller=dialog.locator('.course-review-dialog-body');await scroller.evaluate(el=>el.scrollTo(0,0));
  assert.equal(await dialog.locator('[data-selected-course-id]').count(),initial.total);
  assert.equal(await dialog.locator('.course-year-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),viewport.width===1440?4:viewport.width===1024?2:1);
  assert.equal(await dialog.locator('.course-year-grid').evaluate(el=>getComputedStyle(el).zoom),'0.9');
  assert.ok(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth),'no dialog horizontal overflow');
  assert.ok(await button('확인하고 역량 탐색').evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}),'final action visible');
  const dialogText=await dialog.innerText();
  for(const course of initial.courses)for(const code of course.course_code?.split(' / ') || [])assert.ok(!dialogText.includes(code),'no visible course code');
  await screenshot(`course-confirmation-${viewport.width}`);
  if(process.env.CAPTURE_HELP==='1'&&viewport.width===1440)await page.screenshot({path:fileURLToPath(new URL('../../public/help/courses.png',import.meta.url)),animations:'disabled'});
  const last=dialog.locator('[data-selected-course-id]').last();await last.scrollIntoViewIfNeeded();
  assert.ok(await last.evaluate(el=>{const r=el.getBoundingClientRect(),footer=document.querySelector('.course-review-dialog-footer').getBoundingClientRect();return r.bottom<=footer.top&&el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),'last selected row unobscured');
  if(viewport.width===390)await screenshot('course-confirmation-mobile-last-row');
 }
 await button('선택 수정').click();await page.setViewportSize({width:1440,height:900});
 // Historical roadmap evidence must still use the same grouped course after this UI change.
 await page.goto(origin+'/result?tab=courses');
 await page.locator('.skill-card h3').filter({hasText:'데이터베이스 (Database)'}).waitFor();
 assert.equal(await page.locator('#result-panel .skill-card').count(),1);
 await page.getByRole('tab',{name:'실행 로드맵',exact:true}).click();
 await page.getByText('관련 수강 후보: 데이터베이스 (Database)',{exact:true}).first().waitFor();
 assert.equal((await (await context.request.get(origin+'/api/course-groups-qa')).json()).ai_calls,0);
 assert.deepEqual(errors,[]);
 const report={viewports:['1440×900: 4 columns','1024×900: 2 columns','390×844: 1 column'],catalog,raw_source_rows:JSON.parse(readFileSync(new URL('../../../api/tests/fixtures/seoultech_cse_2026_catalog.json',import.meta.url))).courses.length,api_total:initial.total,year_counts:counts,forced_pages:[1,2,3],checks:['all courses beyond page 1','bilingual codes and canonical IDs','queued cross-year toggles and reversal','hidden selection credits','refresh restoration','save failure retry','confirmation waits and duplicate protection','missing report restoration','409 refresh','missing year/term fallback','last checkbox hit testing','help image','modal previews hidden selections','cancel and focus restoration','long modal 4/2/1 columns at 90%','final modal row and actions unobscured','no navigation or POST before final confirmation']};
 writeFileSync(artifacts+'/verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
} catch(error){await screenshot('failure');console.error(await page.locator('body').innerText());throw error;}
finally{await browser.close();}
