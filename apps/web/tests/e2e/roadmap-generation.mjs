// Real Next UI; synthetic authenticated session and API, with manually released tasks.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.ROADMAP_WEB_ORIGIN || 'http://127.0.0.1:15109';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });

function install() {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({access_token:'test.token.value', refresh_token:'test-refresh', expires_at:Math.floor(Date.now()/1000)+3600, expires_in:3600, token_type:'bearer', user:{id:'test-user'}}));
 sessionStorage.setItem('roadmap_request_id','test-plan'); sessionStorage.setItem('roadmap_request_owner','test-user');
 const state = window.batchMock = JSON.parse(sessionStorage.getItem('batch-mock') || 'null') || { posts: 0, reads: [], latest: null, runs: {} };
 window.saveBatch = () => sessionStorage.setItem('batch-mock', JSON.stringify(state));
 const plan = { request_id:'test-plan', input_revision:1, input:{career_goal:'데이터 분석 프로젝트', target_role:'데이터 분석가', catalog_id:'catalog'} };
 const comparison = { status:'success', input_revision:1, career_goal:plan.input.career_goal, target_role:plan.input.target_role,
  comparisons:[], project_analysis:{analyzed_documents:0,verified_experiences:0}, job_analysis:{status:'success', snapshot_id:'job-1', skills:[], keyword_details:[], collection_summary:{selected_jobs:0}, analysis_summary:{analyzed_jobs:0,failed_jobs:0,skipped_jobs:0}} };
 const activities = {status:'success', activities:[], sources:[{status:'success'}]};
 const full = run => ({ ...run, input_revision:1, request_id:'test-plan', is_stale:false, details_restricted:false,
  generation_complete:true, status:'partial', career_goal:plan.input.career_goal, skill_comparison:comparison,
  activity_recommendations:activities,
  recommended_courses:[{course_id:'course-1',course_name:'데이터베이스',personalization_reason:'기본 근거'}],
  course_reasons:[{course_id:'course-1',personalization_reason:'저장된 AI 추천 이유입니다.'}], course_status:'available',
  basis:{catalog:{},review_status:'confirmed',outside_completed_courses:[]},
  preparation_summary:{confirmed_skills:[],skills_to_verify:[],learning_candidates:[]},
  roadmap:[{step_id:'one',title:'분석 프로젝트 계획',purpose:'관심 분야 살펴보기',reason:'저장한 목표에 맞춘 실행 활동',tasks:[{task_id:'task-1',action:'데이터 분석 경험을 정리한다.',completion_criteria:'경험을 기록함',deliverable:'경험 메모',is_completed:false,progress_version:0}]}] });
 const native = window.fetch;
 window.fetch = async (input, options={}) => {
  const url=String(input); if(!url.includes('/api/')) return native(input, options);
  state.reads.push(`${options.method||'GET'} ${url}`); window.saveBatch();
  const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
  if(url.endsWith('/roadmap') && options.method==='POST') {
   const body=JSON.parse(options.body); state.posts++; state.lastBody=body;
   if(state.rejectNext) { state.rejectNext=false; window.saveBatch(); return json({error:'storage_unavailable',message:'저장소를 사용할 수 없습니다.'},503); }
   const run = body.retry_run_id && state.runs[body.retry_run_id] || {run_id:`run-${state.posts}`, generation_tasks:{comparison:'running',courses:'running',activities:'running',roadmap:'running'}};
   if(body.retry_run_id) { run.status='generating'; run.generation_complete=false; run.generation_tasks.activities='running'; run.generation_tasks.roadmap='running'; }
   state.runs[run.run_id]=run; state.latest=run.run_id; window.saveBatch(); return json(run,202);
  }
  if(url.endsWith('/roadmap')) {
   const run=state.runs[state.latest];
   return json(run ? {...(run.generation_complete ? full(run) : {status:'not_started'}),latest_generation:run} : {status:'not_started'});
  }
  if(url.includes('/roadmaps/')) {
   const run=state.runs[url.split('/roadmaps/')[1].split('/')[0]];
   return json(run?.generation_complete ? full(run) : {status:'generating', generation_complete:false, ...run});
  }
  if(url.includes('/skill-comparison')) return json(comparison);
  if(url.includes('/courses?')) return json({selected_courses:[]});
  if(url.endsWith('/roadmap-inputs/test-plan')) return json(plan);
  return json({error:'not_found'},404);
 };
}

try {
 for (const slow of ['comparison','courses','activities']) {
  const context = await browser.newContext({viewport:slow === 'activities' ? {width:1440,height:900} : {width:390,height:844}});
  await context.addInitScript(install);
  const page=await context.newPage(), errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  await page.goto(`${origin}/result?generate=1`);
  await page.getByRole('heading',{name:'맞춤형 진로 로드맵을 만들고 있어요'}).waitFor();
  assert.equal(await page.locator('.generation-tasks').getAttribute('aria-live'),'polite');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth));
  await page.waitForFunction(() => window.batchMock.posts === 1);
  await page.evaluate(slowTask => {
   const run=window.batchMock.runs[window.batchMock.latest];
   for (const name of ['comparison','courses','activities']) run.generation_tasks[name]=name===slowTask?'running':'success';
   window.saveBatch();
  }, slow);
  await page.waitForFunction(slowTask => {
   const rows=[...document.querySelectorAll('.generation-tasks li')];
   return rows.filter(row=>row.innerText.includes('완료')).length===2 && rows.some(row=>row.innerText.includes('진행 중'));
  }, slow);
  assert.equal(await page.getByRole('tab').count(),0);
  if (slow==='comparison') {
   await page.screenshot({path:'/tmp/team18-roadmap-loading-mobile.png'});
   await page.reload();
   await page.getByRole('heading',{name:'맞춤형 진로 로드맵을 만들고 있어요'}).waitFor();
   await page.waitForFunction(() => document.querySelectorAll('.generation-status.success').length===2);
   assert.equal(await page.evaluate(() => window.batchMock.posts),1);
  }
  await page.evaluate(() => {
   const run=window.batchMock.runs[window.batchMock.latest];
   Object.keys(run.generation_tasks).forEach(key=>run.generation_tasks[key]='success');
   run.generation_complete=true; window.saveBatch();
  });
  await page.getByRole('tab',{name:'준비 상태'}).waitFor();
  for (const name of ['준비 상태','직무 역량 비교','실행 로드맵','수강 후보','공모전·대외활동']) {
   await page.getByRole('tab',{name,exact:true}).click();
   await page.waitForFunction(label => [...document.querySelectorAll('[role=tab]')].find(tab => tab.textContent === label)?.getAttribute('aria-selected') === 'true', name);
   assert.equal(await page.getByRole('tab',{name,exact:true}).getAttribute('aria-selected'),'true');
   if (name==='수강 후보') await page.getByText('저장된 AI 추천 이유입니다.').waitFor();
  }
  assert.equal(await page.evaluate(() => window.batchMock.posts),1);
  assert.equal(await page.evaluate(() => window.batchMock.reads.filter(x=>/\/activities$|course-reasons|job-skill-analysis|course-recommendations/.test(x)).length),0);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth));
  if (slow==='comparison') {
   await page.getByRole('button',{name:'재분석',exact:true}).click();
   await page.getByRole('heading',{name:'맞춤형 진로 로드맵을 만들고 있어요'}).waitFor();
   await page.waitForFunction(() => window.batchMock.posts===2);
   assert.equal(await page.evaluate(() => window.batchMock.lastBody.refresh),true);
   await page.evaluate(() => { const run=window.batchMock.runs[window.batchMock.latest]; run.status='generating'; run.generation_tasks.activities='failed'; window.saveBatch(); });
   await page.getByRole('alert').getByText('로드맵 생성 중 일부 작업을 완료하지 못했어요.').waitFor();
   assert.equal(await page.getByRole('button',{name:'다시 시도'}).isDisabled(),true);
   await page.evaluate(() => { window.batchMock.runs[window.batchMock.latest].status='failed'; window.saveBatch(); });
   await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(button=>button.textContent==='다시 시도')?.disabled);
   await page.getByRole('button',{name:'다시 시도'}).click();
   await page.waitForFunction(() => window.batchMock.posts===3);
   assert.equal(await page.evaluate(() => window.batchMock.lastBody.retry_run_id),'run-2');
   await page.evaluate(() => { const run=window.batchMock.runs[window.batchMock.latest]; Object.keys(run.generation_tasks).forEach(key=>run.generation_tasks[key]='success');run.generation_complete=true;window.saveBatch(); });
   await page.getByRole('tab',{name:'준비 상태'}).waitFor();
   if (process.env.CAPTURE_BATCH_HELP === '1') {
    await page.setViewportSize({width:1440,height:900});
    await page.addStyleTag({content:'nextjs-portal{display:none!important}'});
    await page.screenshot({path:'apps/web/public/help/result-readiness.png'});
    await page.getByRole('tab',{name:'실행 로드맵'}).click();
    await page.screenshot({path:'apps/web/public/help/result-roadmap.png'});
   }
  } else if (slow==='courses') {
   await page.evaluate(() => { window.batchMock.rejectNext=true; window.saveBatch(); });
   await page.getByRole('button',{name:'재분석',exact:true}).click();
   await page.getByText('로드맵 생성 상태를 확인하지 못했어요.').waitFor();
   assert.equal(await page.getByRole('tab').count(),0);
   await page.getByRole('button',{name:'다시 시도'}).click();
   await page.waitForFunction(() => window.batchMock.posts===3);
   await page.evaluate(() => { const run=window.batchMock.runs[window.batchMock.latest];Object.keys(run.generation_tasks).forEach(key=>run.generation_tasks[key]='success');run.generation_complete=true;window.saveBatch(); });
   await page.getByRole('tab',{name:'준비 상태'}).waitFor();
  }
  assert.deepEqual(errors,[]);
  await context.close();
 }
 console.log('PASS: three completion orders, reload, failure/retry, reanalysis, five tabs, no tab-triggered recommendation requests, desktop/mobile layout');
} finally { await browser.close(); }
