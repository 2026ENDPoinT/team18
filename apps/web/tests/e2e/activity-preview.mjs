// Real layout with synthetic saved results; no provider or database is contacted.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.ROADMAP_WEB_ORIGIN || 'http://127.0.0.1:15109';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });

function install() {
 localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({access_token:'test.token.value',refresh_token:'test-refresh',expires_at:Math.floor(Date.now()/1000)+3600,expires_in:3600,token_type:'bearer',user:{id:'test-user'}}));
 sessionStorage.setItem('roadmap_request_id','test-plan'); sessionStorage.setItem('roadmap_request_owner','test-user');
 const plan = {request_id:'test-plan',input_revision:1,input:{career_goal:'데이터 분석',target_role:'데이터 분석가',catalog_id:'catalog'}};
 const comparison = {status:'success',input_revision:1,career_goal:'데이터 분석',target_role:'데이터 분석가',comparisons:[],
  job_analysis:{status:'success',snapshot_id:'job-1',skills:[],keyword_details:[],collection_summary:{selected_jobs:0},analysis_summary:{analyzed_jobs:0,failed_jobs:0,skipped_jobs:0}}};
 const activities = Array.from({length:Number(sessionStorage.getItem('activity-count') || 12)},(_,index)=>({
  source:'contestkorea',id:`activity-${index}`,title:index % 2 ? `지역 사회 문제를 해결하는 데이터 분석 프로젝트 공모전 ${index+1}` : `데이터 분석 공모전 ${index+1}`,
  url:`https://example.test/activity/${index}`,kind:index%2?'extracurricular':'competition',status:index%3?'open':'upcoming',reasons:[],source_links:[],target:'대학생',period:'상시 접수',deadline_label:'상시 접수'}));
 const courses = Array.from({length:7},(_,i)=>({course_id:`course-${i}`,course_name:`데이터 분석 과목 ${i+1}`,personalization_reason:'저장된 이유'}));
 const result = {request_id:'test-plan',run_id:'run-1',status:'partial',generation_complete:true,is_stale:false,details_restricted:false,
  input_revision:1,skill_comparison:comparison,activity_recommendations:{status:'success',activities,sources:[{status:'success'}]},
  recommended_courses:courses,course_reasons:courses.map(course=>({course_id:course.course_id,personalization_reason:'저장된 이유'})),
  course_status:'available',basis:{catalog:{},review_status:'confirmed',outside_completed_courses:[]},
  roadmap:[{step_id:'step-1',title:'계획',tasks:[{task_id:'task-1',action:'정리'}]}]};
 const native = window.fetch;
 window.fetch = async (input,options={}) => {
  const url=String(input); if(!url.includes('/api/')) return native(input,options);
  const json=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
  if(url.endsWith('/roadmap')) return json(result);
  if(url.includes('/skill-comparison')) return json(comparison);
  if(url.includes('/courses?')) return json({selected_courses:[]});
  if(url.endsWith('/roadmap-inputs/test-plan')) return json(plan);
  return new Response('{}',{status:404});
 };
}

try {
 const context = await browser.newContext({viewport:{width:1440,height:900}});
 await context.addInitScript(install);
 const page = await context.newPage(), errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(`${origin}/result?tab=roadmap`);
 const preview = page.locator('.result-activity-preview');
 const visible = preview.locator(':scope > ul:not(.result-activity-measure) > li');
 const measurement = preview.locator('.result-activity-measure > li');
 const verify = async (width,height) => {
  await page.setViewportSize({width,height});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => {
   const preview=document.querySelector('.result-activity-preview');
   if(!preview) return false;
   const list=preview.querySelector('.result-activity-measure'), style=getComputedStyle(preview);
   const limit=style.contain.includes('size')?preview.clientHeight:parseFloat(style.maxHeight);
   const top=list.getBoundingClientRect().top;
   const expected=[...list.children].filter(row=>row.getBoundingClientRect().bottom-top<=limit+0.1).length;
   return preview.querySelector('ul:not(.result-activity-measure)').children.length===expected;
  });
  const layout = await preview.evaluate(element => {
   const list=element.querySelector('ul:not(.result-activity-measure)'), measure=element.querySelector('.result-activity-measure');
   const style=getComputedStyle(element), rect=element.getBoundingClientRect(), card=element.closest('.result-activity-summary');
   const footer=card.querySelector('.summary-link').getBoundingClientRect();
   return {count:list.children.length, measured:measure.children.length, height:element.clientHeight,
    scrollHeight:element.scrollHeight, overflowY:style.overflowY, top:rect.top, bottom:rect.bottom, footerTop:footer.top,
    rows:[...list.children].map(row=>({top:row.getBoundingClientRect().top,bottom:row.getBoundingClientRect().bottom})),
    width:document.documentElement.scrollWidth,viewport:innerWidth, pageHeight:document.documentElement.scrollHeight,
    cardHeight:card.getBoundingClientRect().height, hiddenLinks:measure.querySelectorAll('a').length};
  });
  assert.equal(layout.measured,12);
  assert.ok(layout.count>0,`no activity fits at ${width}×${height}`);
  assert.ok(layout.rows.every(row=>row.top>=layout.top-0.1&&row.bottom<=layout.bottom+0.1),`partial row at ${width}×${height}`);
  assert.ok(layout.bottom<=layout.footerTop+0.1,`footer overlap at ${width}×${height}`);
  assert.ok(layout.scrollHeight<=layout.height+1,`preview overflow at ${width}×${height}`);
  assert.notEqual(layout.overflowY,'scroll');
  assert.equal(layout.width,layout.viewport);
  assert.equal(layout.hiddenLinks,0);
  return layout;
 };
 await preview.waitFor();
 const desktop = await verify(1440,900);
 assert.ok(desktop.count>3,`available desktop space should show more than three activities; got ${desktop.count}`);
 if (process.env.CAPTURE_ACTIVITY_PREVIEW === '1') await page.screenshot({path:'/tmp/team18-activity-preview-desktop.png'});
 const expanded = await page.addStyleTag({content:'.result-course-summary{min-height:1000px!important}'});
 await page.waitForFunction(count => document.querySelector('.result-activity-preview ul:not(.result-activity-measure)').children.length > count, desktop.count);
 await verify(1440,900);
 await expanded.evaluate(element=>element.remove());
 await page.waitForFunction(count => document.querySelector('.result-activity-preview ul:not(.result-activity-measure)').children.length === count, desktop.count);
 await verify(1024,768);
 await verify(720,800);
 await verify(390,844);
 if (process.env.CAPTURE_ACTIVITY_PREVIEW === '1') {
  await page.locator('.result-activity-summary').scrollIntoViewIfNeeded();
  await page.screenshot({path:'/tmp/team18-activity-preview-mobile.png'});
 }
 await verify(350,640);
 await verify(1440,900);
 assert.equal(await measurement.count(),12);
 assert.ok(await visible.count()>3);
 await page.getByRole('link',{name:'활동 상세 보기 →'}).click();
 await page.waitForURL('**/result?tab=activities');
 assert.equal(await page.locator('.activity-recommendations .skill-card').count(),12);
 await page.goto(`${origin}/result?tab=roadmap`);
 const many = await verify(1440,900);
 await page.evaluate(()=>sessionStorage.setItem('activity-count','1'));
 await page.reload(); await preview.waitFor();
 const one = await preview.evaluate(el=>({pageHeight:document.documentElement.scrollHeight,cardHeight:el.closest('.result-activity-summary').getBoundingClientRect().height}));
 assert.ok(Math.abs(many.pageHeight-one.pageHeight)<=1,'extra activities must not grow the desktop page');
 assert.ok(Math.abs(many.cardHeight-one.cardHeight)<=1,'extra activities must not grow the desktop card');
 assert.deepEqual(errors,[]);
 await context.close();
 console.log('PASS: complete rows fit available space, resize recomputes, no preview overflow, desktop page stays fixed, mobile bound, all activities remain in detail');
} finally { await browser.close(); }
