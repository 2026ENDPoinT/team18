// Run with help_ui_server.py and Next configured for its fixture API/auth.
// All writes use disposable SQLite; external auth/AI/catalog services are fixtures.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { confirmCourseSelection } from './course-confirmation.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.HELP_WEB_ORIGIN || 'http://localhost:15102';
const artifacts = process.env.SCROLL_ARTIFACTS || fileURLToPath(new URL('../../test-results/viewport-scroll/', import.meta.url));
mkdirSync(artifacts, { recursive:true });
const browser = await chromium.launch({ executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless:true });
const context = await browser.newContext({ viewport:{width:1366,height:768} });
await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'}}}));
const page = await context.newPage(), report = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
const button = name => page.getByRole('button', {name,exact:true});
const sizes = [[1920,1080],[1640,911],[1440,900],[1366,768],[1280,600],[768,700],[390,844],[320,640]];
const go = async (path, ready) => {
 await page.goto(origin + path);
 await page.locator(ready).first().waitFor();
 await page.waitForLoadState('networkidle');
};
async function measure(name, {short=false, long=false, reason=''} = {}) {
 await page.waitForLoadState('networkidle');
 // The Next development indicator is not part of the deployed page.
 await page.addStyleTag({content:'nextjs-portal{display:none}'});
 for (const [width,height] of sizes) {
  await page.setViewportSize({width,height});
  await page.evaluate(async () => { await document.fonts.ready; scrollTo(0,0); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); });
  const metrics = await page.evaluate(() => {
   const root = document.documentElement;
   const box = el => {const r=el.getBoundingClientRect();return {selector:el.className,top:r.top,bottom:r.bottom,height:r.height};};
   const scrollers = [...document.querySelectorAll('main,main *,aside')].filter(el => {
    const css = getComputedStyle(el);
    return !el.matches('textarea') && el.clientHeight && el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(css.overflowY);
   }).map(el => el.className);
   return {scroll:Math.max(0,root.scrollHeight-innerHeight),horizontal:root.scrollWidth-innerWidth,
    overflow:getComputedStyle(document.body).overflowY,scrollers,
    actions:[...document.querySelectorAll('.footer,.result-pagination,.course-confirm-bar')].map(box)};
  });
  report.push({name,width,height,reason,...metrics});
  assert.ok(metrics.horizontal <= 1, `${name} ${width}: horizontal overflow`);
  assert.ok(!['hidden','clip'].includes(metrics.overflow), `${name}: page scrolling is not locked`);
  assert.deepEqual(metrics.scrollers, [], `${name} ${width}: nested vertical scroll areas`);
  if (!process.env.SCROLL_OBSERVE && short && width >= 1366) {
   assert.ok(metrics.scroll <= 1, `${name} ${width}×${height}: unnecessary ${metrics.scroll}px scroll`);
   for (const action of metrics.actions) assert.ok(action.bottom <= height + 1, `${name}: actions fit the viewport`);
  }
  if (long) assert.ok(metrics.scroll > 0, `${name} ${width}: long content must extend the page`);
  if ([1366,390].includes(width)) await page.screenshot({path:`${artifacts}/${name}-${width}.png`,fullPage:true,animations:'disabled'});
  const controls = page.locator('.footer a,.footer button,.result-pagination a,.result-pagination button,.course-confirm-bar button');
  for (const control of await controls.all()) {
   await control.scrollIntoViewIfNeeded();
   assert.ok(await control.evaluate(el => {
    const r=el.getBoundingClientRect(), hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
    return r.top >= -1 && r.bottom <= innerHeight+1 && (hit===el || el.contains(hit));
   }), `${name} ${width}: footer control is clipped or covered`);
  }
  if (metrics.scroll > 0) {
   await page.evaluate(() => scrollTo(0,0));
   await page.mouse.move(width-20,height/2);
   await page.mouse.wheel(0,300);
   await page.waitForFunction(() => scrollY>0);
   await page.evaluate(() => scrollTo(0,document.documentElement.scrollHeight));
   assert.ok(await page.evaluate(() => scrollY+innerHeight>=document.documentElement.scrollHeight-1),`${name}: page bottom reachable`);
  }
 }
 console.log(name,report.slice(-sizes.length).map(r=>`${r.width}×${r.height}:${r.scroll}px`).join(' '));
}
try {
 await go('/', '.home-actions button:not(:disabled)'); await measure('home',{short:true});
 await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic');
 await page.locator('[name=career_goal]').waitFor(); await measure('basic-expanded',{short:true});
 await page.locator('[name=career_goal]').fill('데이터 분석을 해보고 싶어요');
 await page.locator('[name=target_role]').fill('데이터 분석가');
 await page.locator('[name=university_id]').selectOption('10000000-0000-4000-8000-000000000001');
 await page.locator('[name=department_id]').selectOption('20000000-0000-4000-8000-000000000001');
 await button('저장 후 다음 →').click(); await page.waitForURL('**/input/documents');
 await page.locator('.documents-columns').waitFor(); await measure('documents-empty',{short:true});
 await go('/input/basic','[name=career_goal]'); await measure('basic-saved',{short:true});
 await go('/input/courses','.course-year-grid'); await measure('courses',{short:true,reason:'Year/term headings and catalog rows'});
 await page.getByRole('textbox',{name:'과목 검색'}).fill('없는 과목');
 await page.locator('.course-year-empty').first().waitFor(); await measure('courses-filtered',{short:true});
 // Many course rows use the same page scroll; no fixed-height catalog viewport.
 await page.route('**/api/roadmap-inputs/*/courses?*',async route=>{
  const response=await route.fetch(), data=await response.json();
  const courses=Array.from({length:40},(_,i)=>({...data.courses[0],course_id:`layout-${i}`,course_name:`학습 과목 ${i+1}`,recommended_year:1}));
  await route.fulfill({response,json:{...data,total:courses.length,courses}});
 });
 await go('/input/courses','.course-year-grid'); assert.equal(await page.locator('[data-course-id]').count(),40); await measure('courses-long',{long:true,reason:'40 catalog rows in a year'});
 await page.unroute('**/api/roadmap-inputs/*/courses?*');
 await go('/input/courses','.course-year-grid');
 await page.getByRole('switch',{name:/^프로그래밍 기초 /}).click();
 await page.locator('.course-save-status').filter({hasText:'이수 선택이 저장되었습니다.'}).waitFor();
 await confirmCourseSelection(page); await page.waitForURL('**/input/review');
 await page.locator('.wire-box[aria-busy=false]').waitFor(); await measure('review-empty',{short:true});
 await go('/result','.activity-summary[aria-busy=false]'); await measure('result-overview',{short:true});
 await go('/result?tab=skills','.job-skills[aria-busy=false] .skill-summary'); await measure('skills-empty',{short:true,reason:'Career fields, analysis summary, guidance and source attribution'});
 await go('/result?tab=courses','.roadmap-controls button:not(:disabled)'); await measure('candidates-empty',{short:true});
 await go('/result?tab=activities','.activity-recommendations[aria-busy=false] .skill-card'); await measure('activities',{reason:'Activity rationale, eligibility, dates and source details'});
 // Empty activities should also fit; only the catalog read is substituted.
 await page.route('**/activities', route=>route.fulfill({json:{status:'success',activities:[],sources:[]}}));
 await go('/result?tab=activities','.activity-recommendations[aria-busy=false]'); await measure('activities-empty',{short:true});
 await page.unroute('**/activities');
 // Exercise real file upload, parsing, and the existing experience analysis flow.
 await go('/input/documents','.documents-columns');
 await page.getByLabel('프로젝트 문서 선택').setInputFiles({name:'프로젝트.txt',mimeType:'text/plain',buffer:Buffer.from('제가 React로 신청 화면과 입력 검증을 구현했습니다.\n팀에서 Docker 배포 환경을 구성했습니다.\n제가 SQL로 신청 데이터를 조회했습니다.\n제가 Python으로 통계를 정리했습니다.')});
 await button('읽힌 내용').waitFor(); await measure('documents-uploaded',{short:true});
 // A full ten-document list must grow naturally instead of scrolling inside the card.
 await page.route('**/api/roadmap-inputs/*/documents',async route=>{
  const response=await route.fetch(),data=await response.json(),doc=data.documents[0];
  await route.fulfill({response,json:{...data,documents:Array.from({length:10},(_,i)=>({...doc,document_id:`layout-${i}`,original_filename:`긴 프로젝트 활동과 담당 역할을 기록한 문서 ${i+1}.txt`}))}});
 });
 await go('/input/documents','.documents-columns'); assert.equal(await page.locator('.documents-columns tbody tr').count(),10); await measure('documents-long',{long:true,reason:'10 document rows with read/retry/delete actions'});
 await page.unroute('**/api/roadmap-inputs/*/documents');
 await go('/input/review','.wire-box[aria-busy=false]'); await button('프로젝트 경험 분석 실행').click();
 await page.locator('.wire-box[aria-busy=false] .skill-card').first().waitFor(); await measure('review-analyzed',{long:true,reason:'Four experiences, evidence and confirmation actions'});
 await go('/result?tab=skills','.job-skills[aria-busy=false]'); await button('직무 분석 실행').click();
 await button('직무 분석 다시 실행').waitFor(); await page.locator('.job-skills[aria-busy=false] .skill-card').first().waitFor();
 await measure('skills-analyzed',{long:true,reason:'Job requirements, project evidence and answer controls'});
 await go('/result?tab=courses','.roadmap-controls button:not(:disabled)'); await button('로드맵 생성').click();
 await page.locator('.course-candidates-list .skill-card').first().waitFor();
 await measure('candidates-generated',{reason:'Recommended courses, personalized reasons and evidence'});
 await page.locator('.course-learning summary').first().click();
 await measure('candidates-expanded',{reason:'Expanded learning content and supporting recommendations'});
 await go('/result','.activity-summary[aria-busy=false]'); await measure('result-generated',{short:true});
 // Sidebar collapse and re-expansion must not introduce another scroll owner.
 await page.setViewportSize({width:1366,height:768}); await button('메뉴 접기').click();
 await measure('result-sidebar-collapsed',{short:true});
 assert.deepEqual(errors,[]);
 console.log(`PASS ${report.length} viewport/state checks, reachable actions and normal document scrolling`);
} finally {
 writeFileSync(`${artifacts}/report.json`,JSON.stringify(report,null,2));
 await context.close(); await browser.close();
}
