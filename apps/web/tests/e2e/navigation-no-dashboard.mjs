// Real Next + help_ui_server.py and disposable SQLite; external auth is stubbed.
import assert from 'node:assert/strict';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.HELP_WEB_ORIGIN || 'http://localhost:15102';
const browser = await chromium.launch({ executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless:true });
for (const viewport of [{width:1280,height:720}, {width:390,height:844}]) {
 const context = await browser.newContext({viewport});
 await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'}}}));
 const page = await context.newPage(), errors = [], writes = [];
 page.on('pageerror', error => errors.push(error.message));
 page.on('request', request => { if (request.url().includes('/api/roadmap-inputs') && request.method() !== 'GET') writes.push(request); });
 const button = name => page.getByRole('button',{name,exact:true});
 const goal = '저장된 계획의 화면 이동을 확인합니다.';
 try {
  await page.goto(origin);
  await button('로그인 없이 시작하기').click();
  await page.waitForURL('**/input/basic');
  await page.locator('[name=career_goal]').fill(goal);
  await button('저장').click();
  await page.locator('.basic-save-status').filter({hasText:'저장됨'}).waitFor();
  const planId = await page.evaluate(() => sessionStorage.getItem('roadmap_request_id'));
  const beforeNavigation = writes.length;

  const nav = page.getByRole('navigation',{name:'주 메뉴',exact:true});
  assert.equal(await nav.getByRole('link').count(),5);
  assert.equal(await nav.getByRole('link',{name:'대시보드',exact:true}).count(),0);
  await page.goto(origin);
  await button('이어서 작성').waitFor();
  const saved = page.getByRole('link',{name:'저장 결과 보기',exact:true});
  assert.equal(await saved.getAttribute('href'),'/result?tab=roadmap');
  await saved.click();
  await page.waitForURL('**/result?tab=roadmap');
  await page.locator('.result-basic').getByText(goal,{exact:true}).waitFor();
  await page.getByRole('tab',{name:'공모전·대외활동',exact:true}).click();
  await button('결과 확인 완료 · 로드맵 요약 →').click();
  await page.waitForURL('**/result?tab=roadmap');
  assert.equal(await page.getByRole('tab',{name:'실행 로드맵',exact:true}).evaluate(el=>el===document.activeElement),true);

  await page.goto(origin+'/dashboard');
  await page.waitForURL('**/result?tab=roadmap');
  await page.locator('.result-basic').getByText(goal,{exact:true}).waitFor();
  await page.reload();
  await page.locator('.result-basic').getByText(goal,{exact:true}).waitFor();
  assert.equal(await page.evaluate(() => sessionStorage.getItem('roadmap_request_id')),planId);

  // If saved progress cannot be read, stay on the start page and allow retry.
  await page.goto(origin);
  await button('이어서 작성').waitFor();
  await page.route('**/api/roadmap-inputs/*/documents',route=>route.fulfill({status:503,json:{message:'조회 실패'}}),{times:1});
  await button('이어서 작성').click();
  await page.getByText('저장된 진행 상태를 확인하지 못했습니다. 다시 시도해 주세요.',{exact:true}).waitFor();
  assert.equal(new URL(page.url()).pathname,'/');
  assert.equal(await page.evaluate(() => sessionStorage.getItem('roadmap_request_id')),planId);
  await button('이어서 작성').click();
  await page.waitForURL('**/input/documents');
  assert.equal(await page.evaluate(() => sessionStorage.getItem('roadmap_request_id')),planId);
  assert.equal(writes.length,beforeNavigation,'navigation and retry do not create or change a plan');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors,[]);
  console.log(`PASS ${viewport.width}×${viewport.height}: no dashboard menu, saved result, legacy redirect, resume/retry and preserved plan`);
 } finally { await context.close(); }
}
await browser.close();
