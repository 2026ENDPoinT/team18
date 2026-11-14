// Real Next + API + SQLite. Start roadmap_results_ui_server.py with
// ROADMAP_SKILL_EXPERIENCE_FIXTURE=1. All AI entry points are forbidden there.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.ROADMAP_WEB_ORIGIN || 'http://localhost:15133';
const artifacts = process.env.ROADMAP_TEST_ARTIFACTS || '/tmp/team18-skill-experience';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
try {
 const context = await browser.newContext({ viewport: {width:1440,height:1000} });
 const fixture = await (await context.request.get(origin + '/api/results-test-fixture')).json();
 await context.addCookies([{name:'roadmap_session',value:fixture.cookie,url:origin}]);
 const base=`${origin}/api/roadmap-inputs/${fixture.request_id}`;
 for (const skill_name of ['Java','JavaScript','SQL']) {
  const comparison=await (await context.request.get(base+'/skill-comparison')).json();
  const cleared=await context.request.post(base+'/skill-comparison/answers',{headers:{Origin:origin},data:{
   expected_input_revision:comparison.input_revision,snapshot_id:comparison.job_analysis.snapshot_id,skill_name,status:'clear_experience'}});
  assert.equal(cleared.status(),200);
 }
 await context.addInitScript(id => {
  localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({access_token:'test.token.value',refresh_token:'test-refresh',expires_at:Math.floor(Date.now()/1000)+3600,expires_in:3600,token_type:'bearer',user:{id:'results-test-user'}}));
  sessionStorage.setItem('roadmap_request_id',id);sessionStorage.setItem('roadmap_request_owner','results-test-user');
 }, fixture.request_id);
 const page=await context.newPage(), errors=[], writes=[], observations={};
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',r=>{if(r.url().includes('/api/')&&r.method()!=='GET')writes.push(new URL(r.url()).pathname);});
 const checkbox=name=>page.getByRole('checkbox',{name:`${name} 이 기술 경험 있음`,exact:true});
 const candidates=()=>page.getByRole('region',{name:'보완할 역량 추천'});
 async function verify(names) {
  await page.waitForFunction(expected=>{
   const section=[...document.querySelectorAll('.skill-recommendations')].find(n=>n.checkVisibility());
   return section && JSON.stringify([...section.querySelectorAll('[data-recommended-skill]')].map(n=>n.dataset.recommendedSkill))===JSON.stringify(expected);
  },names);
  assert.deepEqual(await candidates().locator('[data-recommended-skill]').evaluateAll(ns=>ns.map(n=>n.dataset.recommendedSkill)),names);
  assert.ok((await candidates().innerText()).includes(`후보 ${names.length}개`));
 }
 async function toggle(name, checked) {
  assert.equal(await checkbox(name).isChecked(),!checked);
  const [response]=await Promise.all([
   page.waitForResponse(r=>r.url().endsWith('/skill-comparison/answers') && r.request().method()==='POST'),
   checkbox(name).click(),
  ]);
  assert.equal(response.status(),200);
  await page.waitForFunction(()=>![...document.querySelectorAll('.experience-check input')].some(n=>n.disabled));
  assert.equal(await checkbox(name).isChecked(),checked);
 }
 const all=['Java','JavaScript','SQL'];
 await page.goto(origin+'/result?tab=skills');await checkbox('Java').waitFor();
 await verify(all);observations.before=all;
 await toggle('Java',true);await verify(['JavaScript','SQL']);observations.after=['JavaScript','SQL'];
 assert.deepEqual(await page.locator('.job-skills .skill-title h3').allTextContents(),all);
 const current=await (await context.request.get(`${origin}/api/roadmap-inputs/${fixture.request_id}/roadmap`)).json();
 assert.ok(current.current_skill_comparison.comparisons.find(c=>c.skill_name==='Java').manual_experience);
 assert.equal(current.skill_comparison.comparisons.find(c=>c.skill_name==='Java').manual_experience,null);
 const legacy=await (await context.request.get(`${origin}/api/roadmap-inputs/${fixture.request_id}/roadmaps/${fixture.legacy_id}`)).json();
 assert.ok(legacy.current_skill_comparison.comparisons.find(c=>c.skill_name==='Java').manual_experience);
 // Summary and detail share exactly the same candidate list/count.
 await page.getByRole('tab',{name:'결과 요약',exact:true}).click();await verify(['JavaScript','SQL']);
 await page.waitForFunction(()=>document.querySelectorAll('.result-skill-preview ul[aria-label] li').length===3);
 assert.deepEqual(await page.getByRole('list',{name:'분석된 기술 스택'}).locator('h3').allTextContents(),all);
 await page.screenshot({path:artifacts+'/checked-summary.png',fullPage:true});
 await page.getByRole('tab',{name:'직무 역량 비교',exact:true}).click();await verify(['JavaScript','SQL']);
 assert.equal(await checkbox('Java').isChecked(),true);
 await page.reload();await checkbox('Java').waitFor();await verify(['JavaScript','SQL']);
 assert.equal(await checkbox('Java').isChecked(),true);observations.afterReload=['JavaScript','SQL'];
 // Reopening the same roadmap in another page also reads the durable answer.
 const reopened=await context.newPage();await reopened.goto(origin+'/result?tab=skills');
 await reopened.getByRole('checkbox',{name:'Java 이 기술 경험 있음',exact:true}).waitFor();
 assert.equal(await reopened.getByRole('checkbox',{name:'Java 이 기술 경험 있음',exact:true}).isChecked(),true);
 await reopened.close();
 // Failed uncheck and failed check both preserve checkbox AND recommendations.
 const answers=`**/api/roadmap-inputs/${fixture.request_id}/skill-comparison/answers`;
 const fail=route=>route.fulfill({status:503,json:{message:'테스트 저장 실패'}});
 await page.route(answers,fail);await checkbox('Java').click();
 await page.getByRole('alert').getByText('테스트 저장 실패',{exact:false}).waitFor();
 assert.equal(await checkbox('Java').isChecked(),true);await verify(['JavaScript','SQL']);
 await page.unroute(answers,fail);
 await toggle('Java',false);await verify(all);observations.afterClear=all;
 await page.route(answers,fail);await checkbox('Java').click();
 await page.getByRole('alert').getByText('테스트 저장 실패',{exact:false}).waitFor();
 assert.equal(await checkbox('Java').isChecked(),false);await verify(all);
 await page.unroute(answers,fail);
 for(const name of all) await toggle(name,true);
 await verify([]);await candidates().getByText('현재 보완할 역량 추천이 없습니다.',{exact:false}).waitFor();
 await page.reload();await checkbox('Java').waitFor();await verify([]);
 for(const name of all) assert.equal(await checkbox(name).isChecked(),true);
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:artifacts+'/all-checked-mobile.png',fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 for(const name of all) await toggle(name,false);
 await verify(all);
 const latest=await (await context.request.get(origin+'/api/results-test-fixture')).json();
 assert.ok(Object.values(latest.calls).every(n=>n===0),JSON.stringify(latest.calls));
 assert.ok(writes.every(path=>path.endsWith('/skill-comparison/answers')),JSON.stringify(writes));
 assert.deepEqual(errors,[]);
 writeFileSync(artifacts+'/results.json',JSON.stringify({observations,allChecked:[],saveFailure:'preserved on check and uncheck',geminiCalls:latest.calls},null,2));
 console.log('PASS: '+JSON.stringify(observations)+'; all checked empty; failed saves preserved; tabs/reopen/history consistent; Gemini calls = 0');
 await context.close();
} finally {await browser.close();}
