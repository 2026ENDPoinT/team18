// Real Next + disposable FastAPI: tests/integration/intake_ui_server.py.
// Only external auth/OCR and explicitly injected network failures are simulated.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.INTAKE_WEB_ORIGIN || 'http://localhost:15103';
const artifacts = process.env.INTAKE_ARTIFACTS || '/tmp/team18-intake-artifacts';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const user = { id: '12345678-0000-4000-8000-000000000002', is_anonymous: true, aud: 'authenticated' };
await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({ json: { access_token: 'test.token.value', refresh_token: 'test-refresh', expires_in: 3600, token_type: 'bearer', user } }));
const page = await context.newPage();
const errors = [], reviews = [];
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => { if (r.url().endsWith('/course-selection-review')) reviews.push(r.postDataJSON()); });
const button = text => page.getByRole('button', { name: text, exact: true });
async function poll(check, label) { for (let i=0;i<200;i++) { if (await check()) return; await delay(100); } throw Error('Timeout: '+label); }
async function saved() { await page.getByRole('status').filter({ hasText: '저장되었습니다.' }).waitFor(); }
async function ready() { await poll(() => page.getByRole('switch').first().isEnabled(), 'courses ready'); }
async function go(path) { await page.goto(origin+path); }
async function plan() { return page.evaluate(async () => (await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id'))).json()); }
async function courses() { const p=await plan(); return page.evaluate(async ({id,cid}) => (await fetch(`/api/roadmap-inputs/${id}/courses?catalog_id=${cid}&page_size=100`)).json(), {id:p.request_id,cid:p.input.catalog_id}); }
async function noMetadata() { const text=await page.locator('body').innerText(); for (const word of ['변경된 출처 안내 문자열','변경된 출처 이름','2099-12-31','원천 범위 상태:']) assert.ok(!text.includes(word), word); }
try {
 await go('/');
 await button('로그인 없이 시작하기').click();
 await page.waitForURL('**/input/basic');
 await page.locator('[name=career_goal]').fill('이수 과목과 프로젝트 경험을 연결하는 백엔드 개발자');
 await page.locator('[name=university_id]').selectOption('seoultech');
 await page.locator('[name=department_id]').selectOption('seoultech-cse');
 await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.', {exact:true}).waitFor();
 assert.equal(await page.locator('[name=catalog_id]').count(), 0, 'one catalog needs no second selection');
 await noMetadata();
 await button('저장').click(); await saved();
 assert.equal((await plan()).input.catalog_id, 'seoultech-cse-2026-major-v1');
 console.log('PASS: single catalog automatic selection and persisted real catalog');

 await page.locator('[name=department_id]').selectOption('qa-many');
 await poll(async()=>await page.locator('[name=catalog_id]').inputValue()==='qa-current','current year');
 await page.locator('[name=catalog_id]').selectOption('qa-previous');
 await button('저장').click(); await saved();
 await page.reload();
 await poll(async()=>await page.locator('[name=catalog_id]').count() && await page.locator('[name=catalog_id]').inputValue()==='qa-previous','resume saved older catalog');
 // Delay a real response, switch to another department before it arrives.
 let release; const gate=new Promise(resolve=>release=resolve); let responseStarted;
 const started=new Promise(resolve=>responseStarted=resolve);
 await page.route('**/departments/seoultech-cse/catalogs', async route=>{ const response=await route.fetch();responseStarted();await gate;await route.fulfill({response}).catch(()=>{}); });
 await page.locator('[name=department_id]').selectOption('seoultech-cse'); await started;
 await page.locator('[name=department_id]').selectOption('qa-none');
 await page.getByText('등록된 과목 목록이 없습니다. 계속 진행할 수 있습니다.',{exact:true}).waitFor();
 release();await delay(250);await page.unroute('**/departments/seoultech-cse/catalogs');
 await button('저장').click();await saved();assert.equal((await plan()).input.catalog_id,null);
 await go('/input/documents');await button('문서 없이 계속').click();
 await button('수강 제안 없이 계속').click();await page.waitForURL('**/input/review');
 console.log('PASS: multiple catalog priority, saved resume, delayed department response, no catalog continuation');

 await go('/input/basic');
 await page.locator('[name=university_id]').selectOption('qa-university');
 assert.equal(await page.locator('[name=department_id]').inputValue(),'');
 await page.locator('[name=department_id]').selectOption('qa-other');
 await page.getByText('등록된 과목 목록이 없습니다. 계속 진행할 수 있습니다.',{exact:true}).waitFor();
 await page.locator('[name=university_id]').selectOption('seoultech');
 await page.route('**/departments/seoultech-cse/catalogs', route=>route.fulfill({status:503,json:{message:'목록 조회 재시도 검증'}}),{times:1});
 await page.locator('[name=department_id]').selectOption('seoultech-cse');
 await button('목록 다시 불러오기').waitFor(); assert.equal(await button('저장').isDisabled(),true);
 await button('목록 다시 불러오기').click();
 await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.',{exact:true}).waitFor();
 await button('저장 후 다음: 프로젝트 문서').click();
 await page.locator('input[type=file]').waitFor();
 assert.equal(await page.locator('.upload-box').getByRole('button',{name:'문서 없이 계속',exact:true}).count(),1);
 assert.ok(!(await page.locator('body').innerText()).includes('Google Cloud Vision으로 전송'));
 await page.screenshot({path:`${artifacts}/documents-desktop.png`,fullPage:true});
 await button('문서 없이 계속').click();await ready();
 await noMetadata();assert.equal(await page.locator('tbody tr').count(),20);
 assert.equal(await button('이수 선택 확인').count(),1);
 assert.equal(await button('이수 선택 확인 완료').count(),0);
 assert.equal(await button('다음: 분석 내용 확인').count(),0);
 await button('이수 선택 확인').click();await page.waitForURL('**/input/review');
 assert.equal((await plan()).review_status,'confirmed');assert.equal((await courses()).selection_summary.count,0);
 console.log('PASS: school change, catalog fetch retry, upload-area skip, real course names and zero-selection confirmation');

 await go('/input/courses');await ready();
 await page.getByRole('checkbox',{name:'목록에 없는 이수 과목이 있어요'}).check();
 await page.getByRole('switch').nth(0).click();await ready();
 assert.equal((await courses()).selection_summary.count,1);
 // Hold the GET after the last PATCH, then confirm twice while that save is pending.
 let unblock;const held=new Promise(resolve=>unblock=resolve);let loading;const loadStarted=new Promise(resolve=>loading=resolve);
 await page.route('**/courses?*',async route=>{const response=await route.fetch();loading();await held;await route.fulfill({response});},{times:1});
 await page.getByRole('switch').nth(1).click();await loadStarted;
 const before=reviews.length;
 await button('이수 선택 확인').evaluate(e=>{e.click();e.click();});
 await delay(250);assert.equal(reviews.length,before,'review waits for final toggle refresh');
 unblock();await page.waitForURL('**/input/review');
 assert.equal(reviews.length,before+1,'duplicate confirmation blocked');
 assert.equal(reviews.at(-1).reported_missing_courses,true);
 assert.equal((await courses()).selection_summary.count,2);assert.equal((await plan()).review_status,'partial');
 console.log('PASS: multiple selections, missing report, confirmation during final save, duplicate clicks');

 await go('/input/courses');await ready();
 await page.getByRole('switch').nth(0).click();await ready();
 assert.equal(await page.getByRole('checkbox',{name:'목록에 없는 이수 과목이 있어요'}).isChecked(),true,'resumed missing report survives another toggle');
 await page.getByRole('switch').nth(0).click();await ready();
 await page.getByRole('checkbox',{name:'목록에 없는 이수 과목이 있어요'}).uncheck();
 await page.route('**/course-selections',route=>route.fulfill({status:503,json:{message:'일시적인 선택 저장 실패'}}),{times:1});
 await page.getByRole('switch').nth(2).click();
 await button('다시 저장').waitFor();assert.equal(await button('이수 선택 확인').isDisabled(),true);
 await button('다시 저장').click();await ready();assert.equal((await courses()).selection_summary.count,3);
 await page.route('**/course-selection-review',route=>route.fulfill({status:503,json:{message:'일시적인 확인 저장 실패'}}),{times:1});
 await button('이수 선택 확인').click();await page.getByRole('alert').waitFor();
 assert.equal(new URL(page.url()).pathname,'/input/courses');
 await button('이수 선택 확인').click();await page.waitForURL('**/input/review');
 assert.equal((await plan()).review_status,'confirmed');
 console.log('PASS: toggle save failure/retry, confirmation failure/retry without premature navigation');

 await go('/input/courses');await ready();
 const tab=await context.newPage();await tab.goto(origin+'/input/courses');
 await poll(()=>tab.getByRole('switch').first().isEnabled(),'second tab ready');
 await tab.getByRole('switch').nth(3).click();
 await poll(()=>tab.getByRole('switch').nth(3).getAttribute('aria-checked').then(v=>v==='true'),'second tab saved');
 await button('이수 선택 확인').click();await page.getByRole('alert').waitFor();
 assert.equal(new URL(page.url()).pathname,'/input/courses');assert.equal(await button('이수 선택 확인').isDisabled(),true);
 await button('최신 상태 불러오기').click();await ready();
 assert.equal((await courses()).selection_summary.count,4);
 await button('이수 선택 확인').click();await page.waitForURL('**/input/review');
 // Input revision conflict, even though selection revision is unchanged.
 await go('/input/courses');await ready();await tab.goto(origin+'/input/basic');
 await tab.locator('[name=target_role]').fill('다른 탭에서 수정한 희망 직무');
 await tab.getByRole('button',{name:'저장',exact:true}).click();await tab.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await button('이수 선택 확인').click();await page.getByRole('alert').waitFor();
 await button('최신 상태 불러오기').click();await ready();
 // Changing catalog in the other tab must reload the actual new department list.
 await tab.goto(origin+'/input/basic');
 await tab.locator('[name=department_id]').selectOption('qa-many');
 await poll(async()=>await tab.locator('[name=catalog_id]').count() && await tab.locator('[name=catalog_id]').inputValue()==='qa-current','other tab catalog');
 await tab.getByRole('button',{name:'저장',exact:true}).click();await tab.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await button('이수 선택 확인').click();await page.getByRole('alert').waitFor();
 await button('최신 상태 불러오기').click();
 await poll(async()=>await button('이수 선택 확인').isEnabled() && (await page.locator('body').innerText()).includes('검색 결과 0개'),'new catalog refresh');
 assert.equal(await page.getByRole('switch').count(),0);
 await tab.locator('[name=department_id]').selectOption('seoultech-cse');
 await tab.getByText('학과 과목 목록이 자동으로 연결되었습니다.',{exact:true}).waitFor();
 await tab.getByRole('button',{name:'저장',exact:true}).click();await tab.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await button('이수 선택 확인').click();await page.getByRole('alert').waitFor();
 await button('최신 상태 불러오기').click();await ready();
 // A concurrent input write between our PATCH and its refresh must not be silently confirmed.
 let releaseRefresh, refreshStarted;
 const refreshGate=new Promise(resolve=>releaseRefresh=resolve), refreshSignal=new Promise(resolve=>refreshStarted=resolve);
 await page.route('**/courses?*',async route=>{refreshStarted();await Promise.race([refreshGate,delay(20000,undefined,{ref:false})]);await route.fulfill({response:await route.fetch()});},{times:1});
 await page.getByRole('switch').nth(4).click();await refreshSignal;
 const reviewCount=reviews.length;await button('이수 선택 확인').click();
 await tab.reload();
 await tab.locator('[name=target_role]').fill('저장 응답 사이에 변경된 직무');
 await tab.getByRole('button',{name:'저장',exact:true}).click();await tab.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 releaseRefresh();await page.getByRole('alert').waitFor();
 assert.equal(reviews.length,reviewCount,'intervening input write blocks queued confirmation');
 await button('최신 상태 불러오기').click();await ready();
 await page.getByRole('switch').nth(4).click();await ready();
 await tab.close();
 console.log('PASS: actual API 409 conflicts for selection and input revisions across two tabs');

 const all=await courses();const first=all.courses[0];
 await page.getByRole('textbox',{name:'과목명·코드 검색'}).fill(first.course_code);
 await poll(async()=>await page.locator('tbody tr').count()===1 && await page.getByRole('switch').first().isEnabled(),'search');
 await button('검색·필터 초기화').click();await poll(async()=>await page.locator('tbody tr').count()===20 && await page.getByRole('switch').first().isEnabled(),'reset');
 await page.getByRole('combobox',{name:'학년 필터'}).selectOption('2');await ready();
 await page.getByRole('checkbox',{name:'선택한 과목만 보기'}).check();
 await poll(async()=>await page.getByRole('switch',{checked:false}).count()===0,'selected-only');
 await button('검색·필터 초기화').click();await poll(async()=>await page.locator('tbody tr').count()===20 && await page.getByRole('switch').first().isEnabled(),'reset again');
 await button('다음 페이지').click();await ready();
 assert.equal(await page.locator('.pagination').innerText().then(t=>t.includes('2 / 3')),true);
 assert.equal(await page.locator('.course-confirm-bar strong').innerText(),'선택 4개');
 await button('이전 페이지').click();await ready();
 await page.addStyleTag({content:'nextjs-portal { display: none; }'}); // Hide Next's development-only badge in screenshots.
 for(const width of [390,320]){
  await page.setViewportSize({width,height:844});await page.evaluate(()=>scrollTo(0,0));
  const bar=await page.locator('.course-confirm-bar').boundingBox();
  assert.ok(bar.y>=0&&bar.y+bar.height<=844.1,'mobile CTA visible without scrolling');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no page overflow');
  await page.screenshot({path:`${artifacts}/courses-${width}.png`,fullPage:false});
 }
 await page.setViewportSize({width:1440,height:1000});
 await page.screenshot({path:`${artifacts}/courses-desktop.png`,fullPage:false});
 console.log('PASS: search/filter/selection summary retained; 390px and 320px fixed confirmation/count');

 await go('/input/documents');await page.locator('input[type=file]').waitFor();
 await page.locator('input[type=file]').setInputFiles({name:'project.txt',mimeType:'text/plain',buffer:Buffer.from('직접 구현한 프로젝트 문서입니다. API 설계와 테스트를 담당했습니다.')});
 await poll(()=>button('읽힌 내용').first().isEnabled(),'TXT extraction');
 const trigger=button('읽힌 내용').first();await trigger.click();
 await page.getByRole('dialog').waitFor();
 assert.ok((await page.getByRole('dialog').innerText()).includes('API 설계와 테스트'));
 await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
 assert.equal(await trigger.evaluate(e=>e===document.activeElement),true,'Esc restores original trigger');
 await trigger.click();await button('닫기').click();assert.equal(await trigger.evaluate(e=>e===document.activeElement),true,'close restores trigger');
 for(const [file,mime] of [['scan.pdf','application/pdf'],['image.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document']]){
  const result=await context.request.get(origin+'/api/intake-qa/'+file);
  await page.locator('input[type=file]').setInputFiles({name:file,mimeType:mime,buffer:await result.body()});
  const row=page.getByRole('row').filter({hasText:file});
  await poll(()=>row.getByRole('button',{name:'읽힌 내용',exact:true}).isEnabled(),file+' OCR');
  await row.getByRole('button',{name:'읽힌 내용',exact:true}).click();await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').innerText()).includes('Python 3.14'));
  await page.keyboard.press('Escape');
 }
 assert.ok(!(await page.locator('body').innerText()).includes('Google Cloud Vision으로 전송'));
 await page.screenshot({path:`${artifacts}/documents-uploaded.png`,fullPage:true});
 console.log('PASS: real TXT upload/extraction, scan PDF and DOCX-image OCR pipeline (fake Google), modal Esc and focus return');
 assert.deepEqual(errors,[]);console.log('ALL INTAKE BROWSER CHECKS PASSED');
} catch(error) { await page.screenshot({path:`${artifacts}/failure.png`,fullPage:true}).catch(()=>{});console.error(await page.locator('body').innerText());throw error; }
finally { await context.close();await browser.close(); }
