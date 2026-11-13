// Real Next/API/SQLite with help_ui_server.py. Only external services and failure injection are fixtures.
// CAPTURE_HELP=1 writes the ten actual application screenshots into public/help.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { helpExamples } from '../../src/components/help/examples.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.HELP_WEB_ORIGIN || 'http://localhost:15102';
const capture = process.env.CAPTURE_HELP === '1';
const assets = fileURLToPath(new URL('../../public/help/', import.meta.url));
const artifacts = '/tmp/team18-help-artifacts'; mkdirSync(assets, { recursive:true }); mkdirSync(artifacts, { recursive:true });
const browser = await chromium.launch({ executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless:true });
const goal = '행사 신청 데이터를 분석하는 데이터 분석가가 되고 싶어요';
const text = '민서의 동아리 행사 신청 프로젝트\n제가 React로 행사 신청 화면과 입력 검증을 구현했습니다.\n팀원 민수는 Docker로 배포 환경을 구성했습니다.\n제가 SQL로 신청 데이터 조회 쿼리를 작성했습니다.\n제가 Python으로 통계를 정리했습니다.';
const forbidden = ['추출 버전','입력 버전','현재 비교 입력 버전','직무 스냅샷','실행 ID:', '생성 입력', 'Basic DEMO', 'limitsu', '생성 당시 입력 기준', '표시할 기준 없음', '원천 범위 상태', '68개 행', '사용자가 제공한 2026학년도', '외부 Gemini 서비스에서 처리됩니다', '일부 문서 또는 근거 검증이 완료되지 않았습니다', '일부 분석을 완료하지 못했습니다', 'INTERNAL_REVIEW_NOTE'];
async function poll(check,label){for(let i=0;i<250;i++){if(await check())return;await delay(100);}throw Error('Timeout: '+label);}
for (const viewport of [{width:1440,height:900},{width:390,height:844}]) {
 const context = await browser.newContext({viewport});
 await context.route('https://job-skills-test.supabase.co/**',route=>route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'}}}));
 const page=await context.newPage(), errors=[], writes=[];
 page.on('pageerror',e=>errors.push(e.message));
 context.on('request',r=>{if(r.url().includes('/api/roadmap-inputs')&&r.method()!=='GET')writes.push(r);});
 const button=name=>page.getByRole('button',{name,exact:true});
 const tab=name=>page.getByRole('tab',{name,exact:true});
 const card=name=>page.locator('.dashboard-card').filter({has:page.getByRole('heading',{name,exact:true})});
 const experience=skill=>page.locator('.skill-card').filter({has:page.getByText('기술 스택: '+skill,{exact:true})});
 const go=path=>page.goto(origin+path);
 const get=(suffix='')=>page.evaluate(async suffix=>{const r=await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id')+suffix);if(!r.ok)throw Error(await r.text());return r.json();},suffix);
 const readyReview=()=>poll(()=>button('프로젝트 경험 분석 실행').isEnabled(),'review ready');
 const saveBasic=async()=>{await button('저장').click();await page.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();};
 const clean=async()=>{const body=await page.locator('#main-content').textContent();for(const phrase of forbidden)assert.ok(!body.includes(phrase),phrase);};
 async function image(id) {
  if(!capture||viewport.width!==1440)return;
  await clean(); await page.addStyleTag({content:'nextjs-portal{display:none}'});
  await page.evaluate(()=>document.fonts.ready); await page.locator('#main-content').screenshot({path:assets+id+'.png',animations:'disabled'});
 }
 async function help(id, method='escape') {
  if(capture)return; // Capture first; the validation pass then loads the committed assets.
  const name=helpExamples[id].title+' 예시 보기', trigger=button(name), before=writes.length, url=page.url();
  await trigger.click();const dialog=page.getByRole('dialog',{name:helpExamples[id].title+' 예시',exact:true});await dialog.waitFor();
  const img=dialog.getByRole('img',{name:helpExamples[id].alt,exact:true});
  await poll(()=>img.evaluate(el=>el.complete&&el.naturalWidth>0),'help image loaded '+id);
  assert.ok((await img.getAttribute('src')).startsWith('/help/'+id+'.png'));
  assert.equal(await dialog.getByRole('button',{name:'도움말 닫기'}).evaluate(el=>el===document.activeElement),true);
  await page.keyboard.press('Shift+Tab');assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true,'focus stays in dialog');
  await dialog.getByRole('button',{name:'이미지 확대',exact:true}).click();
  assert.ok(await dialog.locator('.help-image-view').evaluate(el=>el.scrollWidth>el.clientWidth),'zoom permits horizontal reading');
  await dialog.locator('.help-image-view').focus();await page.keyboard.press('ArrowRight');
  await dialog.getByRole('button',{name:'이미지 맞춤',exact:true}).click();
  if(id==='basic')await page.screenshot({path:`${artifacts}/help-${viewport.width}.png`});
  if(method==='escape')await page.keyboard.press('Escape');else await dialog.getByRole('button',{name:'도움말 닫기'}).click();
  await dialog.waitFor({state:'detached'});assert.equal(await trigger.evaluate(el=>el===document.activeElement),true,'focus returns');
  assert.equal(page.url(),url);assert.equal(writes.length,before,'help does not mutate input or analyze');
 }
 try {
  await go('/');await button('로그인 없이 시작하기').click();await page.waitForURL('**/input/basic');
  await page.locator('[name=career_goal]').fill(goal);await page.locator('[name=target_role]').fill('데이터 분석가');
  await help('basic');assert.equal(await page.locator('[name=career_goal]').inputValue(),goal);
  await page.locator('[name=university_id]').selectOption({index:1});await page.locator('[name=department_id]').selectOption({index:1});await page.locator('[name=year_level]').selectOption('2');
  await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.',{exact:true}).waitFor();
  await page.route(/\/api\/roadmap-inputs\/[\da-f-]+$/,route=>route.request().method()==='PATCH'?route.fulfill({status:503,json:{message:'저장하지 못했습니다. 다시 시도해 주세요.'}}):route.continue(),{times:1});
  await button('저장').click();await page.getByRole('status').filter({hasText:'저장하지 못했습니다.'}).waitFor();assert.equal(await page.locator('[name=career_goal]').inputValue(),goal);await clean();await saveBasic();await image('basic');
  const initialId=(await get()).request_id;
  await page.getByRole('link',{name:'공모전·대외활동 바로 보기',exact:true}).click();await page.waitForURL('**/result?tab=activities');
  await page.locator('.activity-recommendations .skill-card').first().waitFor();assert.equal((await get('/documents')).documents.length,0);await help('result-activities');await clean();
  await go('/input/documents');await page.locator('input[type=file]').setInputFiles({name:'민서_행사신청_프로젝트.txt',mimeType:'text/plain',buffer:Buffer.from(text)});
  await poll(()=>button('다음: 이수 과목').isEnabled(),'document ready');await help('documents','close');await image('documents');await clean();
  await button('읽힌 내용').click();await page.getByRole('dialog',{name:'읽힌 내용',exact:true}).waitFor();await clean();await page.keyboard.press('Escape');assert.equal(await button('읽힌 내용').evaluate(el=>el===document.activeElement),true);
  await button('다음: 이수 과목').click();await page.waitForURL('**/input/courses');await poll(()=>page.getByRole('switch').first().isEnabled(),'courses loaded');
  for(const name of ['프로그래밍 기초','자료구조']){await page.getByRole('switch',{name:new RegExp('^'+name+' ')}).click();await poll(()=>page.getByRole('switch').first().isEnabled(),'course saved');}
  const beforeCourses=await get('/courses?catalog_id='+(await get()).input.catalog_id+'&page_size=1');await help('courses');assert.equal((await get('/courses?catalog_id='+(await get()).input.catalog_id+'&page_size=1')).selection_summary.count,2);assert.equal(beforeCourses.selection_summary.known_credits,6);await image('courses');
  await page.route('**/course-selection-review',route=>route.fulfill({status:503,json:{message:'이수 선택을 저장하지 못했습니다. 다시 시도해 주세요.'}}),{times:1});
  await button('이수 선택 확인').click();await page.getByRole('alert').filter({hasText:'이수 선택을 저장하지 못했습니다.'}).waitFor();assert.ok(page.url().endsWith('/input/courses'));await help('courses');await clean();
  await button('이수 선택 확인').click();await page.waitForURL('**/input/review');await readyReview();
  await button('프로젝트 경험 분석 실행').click();await poll(()=>page.locator('.skill-card').count().then(n=>n===4),'partial analysis cards');await readyReview();await clean();
  await experience('React').getByRole('button',{name:'맞아요',exact:true}).click();await readyReview();
  await experience('SQL').getByRole('button',{name:'잘 모르겠어요',exact:true}).click();await readyReview();
  await experience('Python').getByRole('button',{name:'이 기술 경험 없어요',exact:true}).click();await readyReview();
  await experience('React').getByRole('button',{name:'수정할게요',exact:true}).click();await experience('React').locator('textarea').fill('행사 신청 화면과 입력 검증을 구현했어요');
  await help('review');assert.equal(await experience('React').locator('textarea').inputValue(),'행사 신청 화면과 입력 검증을 구현했어요');
  await experience('React').getByRole('button',{name:'수정 내용 저장',exact:true}).click();await readyReview();await page.reload();await readyReview();assert.equal(await experience('React').getByRole('heading',{level:3}).innerText(),'행사 신청 화면과 입력 검증을 구현했어요');await image('review');
  await page.locator('footer.footer').getByRole('link',{name:'다음: 로드맵 결과',exact:true}).click();await page.waitForURL('**/result');await help('result-overview');
  await tab('직무 역량 비교').click();await poll(()=>button('직무 분석 실행').isEnabled(),'job ready');await button('직무 분석 실행').click();await poll(()=>button('직무 분석 다시 실행').isEnabled(),'job saved');
  await help('result-skills');await tab('실행 로드맵').click();await button('로드맵 생성').click();await page.locator('.next-task').waitFor();assert.ok((await get('/roadmap')).run_id);
  for(const [name,key] of [['준비 상태','overview'],['직무 역량 비교','skills'],['실행 로드맵','roadmap'],['수강 후보','courses'],['공모전·대외활동','activities']]){
   await tab(name).click();await page.waitForURL('**/result?tab='+key);
   if(key==='skills')await poll(()=>button('직무 분석 다시 실행').isEnabled(),'saved skills');
   if(key==='activities')await page.locator('.activity-recommendations .skill-card').first().waitFor();
   if(key==='courses')await page.locator('#result-panel .skill-card').first().waitFor();
   await help('result-'+key);await clean();await image('result-'+key);
   await page.reload();assert.equal(await tab(name).getAttribute('aria-selected'),'true');
  }
  await go('/dashboard');await poll(()=>page.locator('.dashboard-card').count().then(n=>n===8),'dashboard cards');await help('dashboard');await image('dashboard');
  assert.ok((await card('역량 탐색').innerText()).includes('행사 신청 화면과 입력 검증을 구현했어요'));assert.ok((await card('이수 과목').innerText()).includes('선택 2개 · 6학점'));
  await card('직무 역량 비교').click();await page.waitForURL('**/result?tab=skills');const editor=page.getByRole('region',{name:'진로 정보 수정',exact:true});
  await poll(()=>editor.getByRole('button',{name:'수정',exact:true}).isEnabled(),'career editor');await editor.getByRole('button',{name:'수정',exact:true}).click();await editor.getByRole('textbox',{name:/희망 직무/}).fill('데이터 엔지니어');
  const paidBefore=writes.filter(r=>/\/(roadmap|job-skill-analysis|project-experience-analysis)$/.test(r.url())).length;
  await help('result-skills');assert.equal(await editor.getByRole('textbox',{name:/희망 직무/}).inputValue(),'데이터 엔지니어');
  await editor.getByRole('button',{name:'저장',exact:true}).click();await editor.getByRole('status').filter({hasText:'진로 정보를 저장했습니다.'}).waitFor();
  assert.equal(writes.filter(r=>/\/(roadmap|job-skill-analysis|project-experience-analysis)$/.test(r.url())).length,paidBefore);
  await go('/input/basic');assert.equal(await page.locator('[name=target_role]').inputValue(),'데이터 엔지니어');await go('/dashboard');await card('기본 정보').waitFor();assert.ok((await card('기본 정보').innerText()).includes('데이터 엔지니어'));
  for(const [name,key] of [['직무 역량 비교','skills'],['실행 로드맵','roadmap'],['수강 후보','courses'],['공모전·대외활동','activities']]){
   await card(name).focus();await page.keyboard.press('Enter');await page.waitForURL('**/result?tab='+key);assert.equal(await tab(name).getAttribute('aria-selected'),'true');await help('result-'+key);await clean();await page.reload();assert.equal(await tab(name).getAttribute('aria-selected'),'true');await page.goBack();await page.waitForURL('**/dashboard');await card(name).waitFor();
  }
  console.log(`PASS ${viewport.width}×${viewport.height}: guest → department → upload → one-button courses → four experience responses/edit → results → career edit → dashboard tabs; reload, draft/selection/tab retention, saved retry`);

  // Vary the values of metadata fields, not text-match filters. Real user evidence remains visible.
  const marker='INTERNAL_REVIEW_NOTE';
  await page.route('**/api/roadmap-inputs/**',async route=>{
   if(route.request().method()!=='GET')return route.continue();
   try {
   const response=await route.fetch();if(!response.ok())return route.fulfill({response});
   const data=await response.json();
   if(data.roadmap){data.model_name=marker;data.limitations=[marker];data.basis.job_snapshot_id=marker;if(data.basis.catalog){data.basis.catalog.scope_description=marker;data.basis.catalog.source_name=marker;}for(const step of data.roadmap)step.limitations=marker;}
   if(data.job_analysis){data.job_analysis.sample_notice=marker;data.job_analysis.previous_analysis_version=true;data.job_analysis.status='partial';}
   if(data.activities)data.sample_notice=marker;
   return await route.fulfill({response,json:data});
   } catch(error) { if(!/already handled|Target closed|ERR_ABORTED|closed/.test(error.message))throw error; }
  });
  for(const key of ['overview','skills','roadmap','courses','activities']){await go('/result?tab='+key);await page.waitForLoadState('networkidle');if(key==='skills')await poll(()=>button('직무 분석 실행').isEnabled(),'new goal empty skills');else if(key==='activities')await button('활동 추천 다시 확인').waitFor();else await page.locator('.roadmap-controls').waitFor();await help('result-'+key);await clean();}
  await page.unroute('**/api/roadmap-inputs/**');
  // Failure history still gives an actionable retry without diagnostic IDs.
  await go('/result?tab=roadmap');await button('현재 입력으로 다시 분석').waitFor();
  await page.route('**/roadmap',route=>route.request().method()==='POST'?route.fulfill({status:502,json:{error:'gemini_invalid_response',message:'실패',run_id:'internal-run-id',detail_code:'experience_status_mismatch'}}):route.continue());
  await button('현재 입력으로 다시 분석').click();await page.getByRole('alert').filter({hasText:'다시 생성해 주세요.'}).waitFor();await clean();assert.ok(!(await page.locator('body').innerText()).includes('internal-run-id'));await help('result-roadmap');await page.unroute('**/roadmap');
  if(!capture){await page.route('**/help/basic.png',route=>route.fulfill({status:404,body:''}),{times:1});await go('/input/basic');await button('기본 정보 예시 보기').click();await page.getByRole('dialog').getByRole('alert').waitFor();await button('이미지 다시 불러오기').click();await poll(()=>page.getByRole('dialog').locator('img').evaluate(el=>el.complete&&el.naturalWidth>0),'image retry');await page.keyboard.press('Escape');}
  // New plan: skip a document and confirm zero courses, then read activities without analysis.
  await go('/');await button('처음부터 작성하기').click();await page.waitForURL('**/input/basic');await page.locator('[name=career_goal]').fill(goal);await page.locator('[name=university_id]').selectOption({index:1});await page.locator('[name=department_id]').selectOption({index:1});await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.',{exact:true}).waitFor();await button('저장 후 다음: 프로젝트 문서').click();await page.waitForURL('**/input/documents');await button('문서 없이 계속').click();await page.waitForURL('**/input/courses');await poll(()=>button('이수 선택 확인').isEnabled(),'zero courses ready');await help('courses');await button('이수 선택 확인').click();await page.waitForURL('**/input/review');await page.getByText('현재 분석 가능한 문서가 없습니다. 경험이 없다는 의미는 아닙니다. 문서 상태를 확인해 주세요.',{exact:true}).waitFor();await clean();await help('review');
  assert.equal((await get('/documents')).documents.length,0);assert.notEqual((await get()).request_id,initialId);assert.equal((await get()).review_status,'confirmed');
  await go('/result?tab=courses');await page.getByText('아직 표시할 로드맵 결과가 없습니다. 분석 근거를 확인한 후 로드맵을 생성해 주세요.',{exact:true}).waitFor();await clean();await help('result-courses');await go('/result?tab=activities');await page.locator('.activity-recommendations .skill-card').first().waitFor();await help('result-activities');await clean();
  await page.route('**/api/roadmap-inputs/*/documents',route=>route.fulfill({status:503,json:{error:'feature_unavailable',message:'PostgreSQL 문서 기능은 아직 연결되지 않았습니다.'}}),{times:1});
  await go('/input/documents');await page.getByText('프로젝트 문서를 사용할 수 없습니다.',{exact:true}).waitFor();assert.ok(!(await page.locator('body').innerText()).includes('PostgreSQL'));await help('documents');await clean();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log(`PASS ${viewport.width}×${viewport.height}: changed metadata stays hidden in partial/old/empty/error states, image recovery, document skip, zero courses, goal-only activities`);
 } catch(error) { await page.screenshot({path:`${artifacts}/failure-${viewport.width}.png`,fullPage:true}).catch(()=>{});console.error(await page.locator('body').innerText());throw error; }
 finally { await context.close(); }
}
await browser.close();
console.log(capture?'ALL TEN ACTUAL APP EXAMPLES CAPTURED':'ALL HELP AND FULL USER FLOW CHECKS PASSED');
