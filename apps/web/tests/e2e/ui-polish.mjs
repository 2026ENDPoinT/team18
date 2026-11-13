// Run against help_ui_server.py and Next with its fixture auth configuration.
// External providers are stubbed; input and selection persistence use real SQLite.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.HELP_WEB_ORIGIN || 'http://localhost:15102';
const browser = await chromium.launch({ executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless:true });
const context = await browser.newContext({ viewport:{width:1280,height:720} });
await context.route('https://job-skills-test.supabase.co/**', route => route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'}}}));
const page = await context.newPage(), errors = [], requests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.url().includes('/api/')) requests.push({method:request.method(),path:new URL(request.url()).pathname}); });
const button = name => page.getByRole('button',{name,exact:true});
const saved = () => page.locator('.course-save-status').filter({hasText:'이수 선택이 저장되었습니다.'}).waitFor();
const get = suffix => page.evaluate(async suffix => {
 const response = await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id')+suffix);
 if (!response.ok) throw Error(await response.text());
 return response.json();
},suffix);
try {
 await page.goto(origin);
 await button('로그인 없이 시작하기').waitFor();
 assert.ok(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),'desktop home fits one screen');
 await button('로그인 없이 시작하기').click(); await page.waitForURL('**/input/basic');
 const goal = page.locator('[name=career_goal]'); await goal.waitFor();
 assert.ok((await goal.getAttribute('placeholder')).startsWith('예)'));
 assert.ok((await page.locator('[name=target_role]').getAttribute('placeholder')).startsWith('예)'));
 await button('저장').click(); await page.locator('#career-goal-error').waitFor();
 assert.equal(await goal.evaluate(el=>el===document.activeElement),true);
 await goal.fill('   '); await button('저장').click();
 assert.equal(await goal.getAttribute('aria-invalid'),'true');
 assert.equal(await page.locator('[name=year_level],[name=gpa],[name=completed_credits]').count(),0);
 await goal.fill('데이터 분석을 해보고 싶어요');
 assert.equal(await page.locator('#career-goal-error').count(),0);
 await page.locator('[name=university_id]').selectOption({index:1});
 await page.locator('[name=department_id] option').nth(1).waitFor({state:'attached'});
 await page.locator('[name=department_id]').selectOption({index:1});
 await button('저장 후 다음: 프로젝트 문서').click(); await page.waitForURL('**/input/documents');
 await button('문서 없이 계속').click(); await page.waitForURL('**/input/courses');
 await page.locator('[data-course-id]').first().waitFor();
 const plan = await get(''), query = '/courses?catalog_id='+plan.input.catalog_id+'&page_size=100';
 const initial = await get(query), yearCourses = initial.courses.filter(course=>course.recommended_year===2);
 assert.ok(yearCourses.length>1,'fixture includes multiple courses in a year');
 assert.equal(await button('필터 초기화').count(),0);
 assert.equal(await page.getByRole('combobox',{name:'전공 구분 필터'}).count(),0);
 const row = page.locator(`[data-course-id="${yearCourses[0].course_id}"]`);
 await row.locator('.course-name').click(); await saved();
 assert.equal(await row.getByRole('switch').getAttribute('aria-checked'),'true','whole row toggles exactly once');
 await row.getByRole('switch').click(); await saved();
 const search = page.getByRole('textbox',{name:'과목 검색'});
 await search.fill(yearCourses[0].course_name);
 // Reversals while a save is in flight must preserve the most recent group choice.
 let release, started;
 const held = new Promise(resolve=>release=resolve), signal = new Promise(resolve=>started=resolve);
 await page.route('**/course-selections',async route=>{started();await held;await route.continue();},{times:1});
 await button('2학년 전체 선택').click(); await signal;
 await button('2학년 전체 해제').click(); await button('2학년 전체 선택').click();
 release(); await saved();
 let selected = await get(query);
 assert.equal(selected.selection_summary.count,yearCourses.length,'bulk selection includes search-hidden courses');
 await search.fill(''); await page.reload(); await page.locator('[data-course-id]').first().waitFor();
 assert.equal(await page.locator('[data-year="2"]').getByRole('switch',{checked:true}).count(),yearCourses.length);
 await button('2학년 1학기 전체 해제').click(); await saved();
 assert.equal((await get(query)).selected_courses.filter(course=>course.recommended_year===2&&String(course.recommended_term)==='1').length,0);
 await button('2학년 전체 선택').click(); await saved();
 await button('이수 선택 확인').click(); const dialog=page.getByRole('dialog'); await dialog.waitFor();
 assert.equal(await dialog.locator('[data-selected-course-id]').count(),yearCourses.length);
 assert.ok(!/학점|전공필수|전공선택/.test(await dialog.innerText()));
 await page.keyboard.press('Escape'); await dialog.waitFor({state:'detached'});
 assert.equal(await button('이수 선택 확인').evaluate(el=>el===document.activeElement),true);
 await button('이수 선택 확인').click(); await button('확인하고 역량 탐색').click(); await page.waitForURL('**/input/review');
 await page.goto(origin+'/result'); await button('제한 안내 로드맵 생성').click(); await page.locator('.next-task').waitFor();
 await page.getByRole('tab',{name:'준비 상태',exact:true}).click();
 const readsBefore = requests.filter(request=>request.method==='GET'&&request.path.endsWith('/roadmap')).length;
 await button('다음: 실행 로드맵 →').click(); await page.waitForURL('**/result?tab=roadmap');
 assert.equal(requests.filter(request=>request.method==='GET'&&request.path.endsWith('/roadmap')).length,readsBefore,'tab navigation reuses the saved result');
 for (const [label,key] of [['직무 역량 비교','skills'],['수강 후보','courses'],['공모전·대외활동','activities']]) {
  await button(`다음: ${label} →`).click(); await page.waitForURL('**/result?tab='+key);
  assert.equal(await page.getByRole('tab',{name:label,exact:true}).getAttribute('aria-selected'),'true');
  if (key==='courses') { await page.locator('.course-learning summary').first().click(); assert.equal(await page.locator('.course-learning').first().getAttribute('open'),''); }
 }
 assert.equal(requests.filter(request=>request.method==='GET'&&request.path.endsWith('/roadmaps')).length,0,'no history fetch');
 assert.equal(requests.filter(request=>request.method==='POST'&&request.path.endsWith('/roadmap')).length,1,'tab navigation does not regenerate');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no desktop horizontal overflow');
 assert.deepEqual(errors,[]);
 console.log('PASS: desktop required-field feedback, row/bulk selection persistence and reversals, confirmation focus, result navigation/request reuse');
} finally { await context.close(); await browser.close(); }
