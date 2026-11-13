// Real Next + roadmap_results_ui_server.py, real HTTP and SQLite. No AI API keys.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.ROADMAP_WEB_ORIGIN || 'http://localhost:15133';
const artifacts = process.env.ROADMAP_TEST_ARTIFACTS || '/tmp/team18-roadmap-results';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
try {
 const context = await browser.newContext({viewport:{width:1440,height:900}});
 const fixture = await (await context.request.get(origin + '/api/results-test-fixture')).json();
 await context.addCookies([{name:'roadmap_session', value:fixture.cookie, url:origin}]);
 await context.addInitScript(({id}) => {
  localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({access_token:'test.token.value',refresh_token:'test-refresh',expires_at:Math.floor(Date.now()/1000)+3600,expires_in:3600,token_type:'bearer',user:{id:'results-test-user'}}));
  sessionStorage.setItem('roadmap_request_id',id); sessionStorage.setItem('roadmap_request_owner','results-test-user');
 }, {id:fixture.request_id});
 const page = await context.newPage(), errors=[], calls=[];
 page.setDefaultTimeout(15000);
 page.on('pageerror', e=>errors.push(e.message));
 page.on('request', r=>{ if(r.url().includes('/api/')) calls.push({method:r.method(),path:new URL(r.url()).pathname}); });
 const summary = () => page.getByRole('tab',{name:'결과 요약',exact:true});
 const ready = async () => { await summary().waitFor(); await page.locator('.result-course-summary h3').waitFor(); };
 const get = async suffix => (await context.request.get(`${origin}/api/roadmap-inputs/${fixture.request_id}${suffix}`)).json();
 const post = async (path,body) => { const response=await context.request.post(origin+'/api'+path,{data:body,headers:{Origin:origin}});assert.ok(response.ok(),await response.text());return response.json(); };
 await page.goto(origin+'/result'); await ready(); // A genuine old saved plan remains readable.
 assert.equal(await page.locator('.execution-steps').count(),0);
 assert.equal(await page.getByRole('checkbox').count(),0);
 assert.equal((await get(`/roadmaps/${fixture.legacy_id}`)).progress.completed,1);
 await page.getByRole('button',{name:'재분석',exact:true}).click(); await ready();
 let saved=await get('/roadmap');
 assert.equal(saved.generation_complete,true); assert.equal(saved.status,'success'); assert.deepEqual(saved.roadmap,[]);
 assert.equal(saved.course_reasons_source,'catalog_evidence');
 const countWrites=()=>calls.filter(c=>c.method!=='GET').length;
 const writes=countWrites();
 for (const label of ['수강 후보','직무 역량 비교','공모전·대외활동','결과 요약']) {
  await page.getByRole('tab',{name:label,exact:true}).click();
  await page.waitForFunction(label=>document.querySelector('[role=tab][aria-selected=true]')?.textContent===label,label);
  if(label==='수강 후보') await page.getByText('목표와 일치하는 학습 내용:',{exact:false}).waitFor();
  if(label==='공모전·대외활동') await page.getByText('현재 추천 조건에 맞는 공고가 없습니다.',{exact:false}).waitFor();
 }
 await page.reload(); await ready(); assert.equal(countWrites(),writes);
 await page.screenshot({path:artifacts+'/success-desktop.png',fullPage:true});
 // Saved comparison and courses remain visible even when profile lookup fails.
 await page.route(`**/api/roadmap-inputs/${fixture.request_id}`,r=>r.fulfill({status:503,json:{message:'Synthetic profile failure'}}));
 await page.reload(); await ready();
 await page.getByRole('tab',{name:'직무 역량 비교',exact:true}).click();
 await page.locator('.job-skills .skill-title h3').getByText('SQL',{exact:true}).waitFor();
 await page.unroute(`**/api/roadmap-inputs/${fixture.request_id}`);
 await post('/results-test-state',{activity_failure:true,remove_job_snapshot:true});
 await page.goto(origin+'/result?tab=roadmap'); await ready(); // Stale saved results remain readable, without forcing polling.
 await page.getByRole('button',{name:'재분석',exact:true}).click(); await ready();
 saved=await get('/roadmap');
 assert.equal(saved.status,'partial'); assert.equal(saved.generation_complete,true);
 assert.equal(saved.component_status.comparison,'unavailable'); assert.equal(saved.component_status.activities,'failed');
 assert.ok(saved.recommended_courses.length);
 await page.getByText('아직 기술 스택 분석이 없어요.',{exact:true}).waitFor();
 await page.getByText('활동 추천을 불러오지 못했어요.',{exact:true}).waitFor();
 await page.getByRole('tab',{name:'직무 역량 비교',exact:true}).click();
 await page.getByText('저장된 직무 분석이 없어 미분석 상태입니다.',{exact:false}).waitFor();
 await page.getByRole('tab',{name:'공모전·대외활동',exact:true}).click();
 await page.getByText('추천 활동을 불러오지 못했습니다.',{exact:false}).waitFor();
 await summary().click(); await page.waitForURL('**/result?tab=roadmap'); await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:artifacts+'/partial-mobile.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const writesAfter=countWrites(); await page.reload(); await ready(); assert.equal(countWrites(),writesAfter);
 // A failed course-selection lookup does not hide saved course candidates.
 await page.route('**/courses?*',r=>r.fulfill({status:503,json:{message:'Synthetic selection failure'}}));
 await page.reload(); await ready(); await page.getByRole('tab',{name:'수강 후보',exact:true}).click();
 await page.locator('.course-candidates-list h3').waitFor(); await page.unroute('**/courses?*');
 // A failed saved-result lookup must still show profile/comparison/activity resources.
 await page.route(`**/roadmap-inputs/${fixture.request_id}/roadmap`,r=>r.fulfill({status:503,json:{message:'Synthetic roadmap read failure'}}));
 await page.goto(origin+'/result?tab=roadmap'); await summary().waitFor();
 await page.locator('.result-basic').getByText('데이터 분석가',{exact:true}).waitFor();
 await page.getByText('저장된 결과를 불러오지 못했어요.',{exact:false}).waitFor();
 await page.unroute(`**/roadmap-inputs/${fixture.request_id}/roadmap`);
 const latest=await (await context.request.get(origin+'/api/results-test-fixture')).json();
 assert.ok(Object.values(latest.calls).every(n=>n===0),JSON.stringify(latest.calls));
 assert.ok(calls.every(c=>!c.path.includes('/tasks/') && !c.path.includes('/course-reasons')));
 assert.deepEqual(errors,[]);
 assert.equal((await get(`/roadmaps/${fixture.legacy_id}`)).progress.completed,1);
 assert.ok((await get('/roadmaps')).runs.length>=3);
 console.log('PASS: real API generation, legacy history, missing analysis, activity failure, independent resources, reload/tabs, mobile; Gemini calls = 0');
 await context.close();
} finally { await browser.close(); }
