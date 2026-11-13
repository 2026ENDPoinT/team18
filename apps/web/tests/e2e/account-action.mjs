// Real Next UI and Supabase SDK; provider/API responses are synthetic.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.ROADMAP_WEB_ORIGIN || 'http://127.0.0.1:15109';
const authKey = 'sb-job-skills-test-auth-token';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });

async function scenario({ guest = false, width = 1440 }) {
 const user = { id:'account-test-user', email:guest ? undefined : 'student@example.test', is_anonymous:guest, aud:'authenticated' };
 const session = { access_token:'test.token.value', refresh_token:'test-refresh', expires_in:3600, expires_at:Math.floor(Date.now()/1000)+3600, token_type:'bearer', user };
 const context = await browser.newContext({ viewport:{ width, height:900 } });
 await context.addInitScript(({session,authKey,guest}) => {
  if (sessionStorage.getItem('account-test-initialized')) return;
  sessionStorage.setItem('account-test-initialized','true');
  if (!guest) {
   localStorage.setItem(authKey,JSON.stringify(session));
   sessionStorage.setItem('roadmap_request_id','account-plan');
   sessionStorage.setItem('roadmap_request_owner',session.user.id);
  }
 }, {session,authKey,guest});
 const plan = { request_id:'account-plan', input_revision:1, input:{career_goal:'저장된 진로 목표',target_role:'데이터 분석가'} };
 const comparison = { status:'success',job_analysis:{status:'success',snapshot_id:'job',skills:[]},comparisons:[] };
 const roadmap = { run_id:'saved-run',status:'partial',generation_complete:true,roadmap:[],recommended_courses:[],
  skill_comparison:comparison,activity_recommendations:{status:'success',activities:[],sources:[]} };
 let failLogout = false, releaseLogout, logoutStarted, holdLogout = false;
 const logouts = [], errors = [];
 await context.route('https://job-skills-test.supabase.co/**',async route => {
  const url = new URL(route.request().url());
  if (url.pathname === '/auth/v1/logout') {
   logouts.push(url.searchParams.get('scope'));
   if (holdLogout) await new Promise(resolve => { releaseLogout = resolve; logoutStarted(); });
   await route.fulfill(failLogout ? {status:500,json:{message:'Test logout failed'}} : {status:204,body:''});
  } else await route.fulfill({json:session});
 });
 await context.route('**/api/**',route => {
  const path = new URL(route.request().url()).pathname;
  const json = path.endsWith('/resume') ? {found:true,request:plan}
   : path.endsWith('/roadmap') ? roadmap : path.endsWith('/skill-comparison') ? comparison
   : path.endsWith('/documents') ? {documents:[]} : path.endsWith('/project-experience-analysis') ? {experiences:[]} : plan;
  return route.fulfill({json});
 });
 const page = await context.newPage();
 page.on('pageerror',error=>errors.push(error.message));
 const header = page.locator('header.global-bar');
 const logout = () => header.getByRole('button',{name:'로그아웃',exact:true});
 const login = () => header.getByRole('link',{name:'계정 · 로그인',exact:true});
 try {
  await page.goto(origin + (guest ? '/' : '/result'));
  if (guest) {
   await login().waitFor();
   await page.getByRole('button',{name:'로그인 없이 시작하기',exact:true}).click();
   await page.waitForURL('**/result?tab=roadmap');
  }
  await logout().waitFor();
  await page.locator('.result-basic').getByText('저장된 진로 목표',{exact:true}).waitFor();
  assert.equal(await login().count(),0);
  await page.reload(); await logout().waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if (guest) {
   page.once('dialog',dialog=>dialog.dismiss());
   await logout().click();
   assert.equal(logouts.length,0,'cancelling guest logout preserves the session');
   assert.equal(new URL(page.url()).pathname,'/result');
   page.once('dialog',dialog=>dialog.accept());
  } else {
   failLogout = true;
   await logout().click();
   await header.getByRole('alert').waitFor();
   assert.equal(new URL(page.url()).pathname,'/result','failed logout stays on the current page');
   assert.ok(await page.evaluate(key=>localStorage.getItem(key),authKey));
   assert.equal(await page.evaluate(()=>sessionStorage.getItem('roadmap_request_id')),'account-plan');
   failLogout = false;
  }
  holdLogout = true;
  const before = logouts.length;
  const requested = new Promise(resolve => { logoutStarted = resolve; });
  await logout().click();
  await header.getByRole('button',{name:'로그아웃 중…',exact:true}).waitFor();
  assert.equal(await header.getByRole('button',{name:'로그아웃 중…',exact:true}).isDisabled(),true);
  await requested;
  assert.equal(logouts.length,before+1);
  releaseLogout();
  await page.waitForURL(origin + '/');
  await login().waitFor();
  await page.getByRole('button',{name:'Google로 계속하기',exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(key=>[localStorage.getItem(key),sessionStorage.getItem('roadmap_request_id'),sessionStorage.getItem('roadmap_request_owner')],authKey),[null,null,null]);
  assert.ok(logouts.every(scope=>scope==='local'));
  await page.reload(); await login().waitFor();
  assert.equal(await logout().count(),0);
  assert.deepEqual(errors,[]);
  console.log(`PASS: ${guest?'guest sign-in/cancel':'signed-in restoration/failure retry'}, header logout, home redirect, cleared session, ${width}px`);
 } finally { releaseLogout?.(); await context.close(); }
}
try {
 await scenario({});
 await scenario({guest:true,width:390});
} finally { await browser.close(); }
