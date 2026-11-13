// Next :15102 + tests/integration/explore_ui_server.py. Real API/DB; fake external providers.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const { chromium }=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const origin=process.env.EXPLORE_WEB_ORIGIN||'http://localhost:15102';
const artifacts=process.env.EXPLORE_ARTIFACTS||'/tmp/team18-explore-artifacts';mkdirSync(artifacts,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.P5_BROWSER||'/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const user={id:'12345678-0000-4000-8000-000000000002',is_anonymous:true,aud:'authenticated'};
await context.route('https://job-skills-test.supabase.co/**',route=>route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user}}));
const page=await context.newPage();const errors=[],patches=[],paid=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.method()==='PATCH'&&/\/roadmap-inputs\/[\da-f-]+$/.test(r.url()))patches.push(r.postDataJSON());if(r.method()==='POST'&&/\/(job-skill-analysis|project-experience-analysis|roadmap)$/.test(r.url()))paid.push(r.url());});
const button=name=>page.getByRole('button',{name,exact:true});
const editor=()=>page.getByRole('region',{name:'진로 정보 수정',exact:true});
const card=skill=>page.locator('.skill-card').filter({has:page.getByText('기술 스택: '+skill,{exact:true})});
async function poll(check,label){for(let i=0;i<200;i++){if(await check())return;await delay(100);}throw Error('Timeout: '+label);}
async function go(path){await page.goto(origin+path);}
async function readyReview(){await poll(()=>button('프로젝트 경험 분석 실행').isEnabled(),'review ready');}
async function saved(){await page.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();}
async function plan(){return page.evaluate(async()=>(await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id'))).json());}
async function fixture(body){await page.evaluate(async body=>{const r=await fetch('/api/explore-fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());},body);}
async function counters(){return(await context.request.get(origin+'/api/review-counters')).json();}
async function cleanCopy(){const text=await page.locator('body').innerText();for(const snippet of ['외부 Gemini 서비스에서 처리됩니다','저장된 본문으로 다시 분석하며 OCR','일부 문서 또는 근거 검증이 완료되지 않았습니다','일부 분석을 완료하지 못했습니다','진행 순서: 입력','생성 당시 입력 기준','추천에 사용한 입력 기준','표시할 기준 없음','직무 근거가 있는 로드맵 생성은','저장된 목표와 희망 직무를 바탕으로 해외 원격근무','실행하면 저장한 목표·희망 직무를 Gemini'])assert.ok(!text.includes(snippet),snippet);}
async function editorReady(){await poll(()=>editor().getByRole('button',{name:'수정',exact:true}).isEnabled(),'career editor ready');}
async function edit(){await editorReady();await editor().getByRole('button',{name:'수정',exact:true}).click();}
async function careerSaved(){await editor().getByRole('status').filter({hasText:'진로 정보를 저장했습니다.'}).waitFor();await editorReady();}
async function compareTab(){await page.getByRole('tab',{name:'직무 역량 비교',exact:true}).click();await editorReady();}
try{
 await go('/');await button('로그인 없이 시작하기').click();await page.waitForURL('**/input/basic');
 await page.locator('[name=career_goal]').fill('데이터 분석 분야의 프로젝트를 준비합니다');await page.locator('[name=target_role]').fill('데이터 분석가');
 await page.locator('[name=university_id]').selectOption({index:1});await page.locator('[name=department_id]').selectOption({index:1});
 await page.getByText('학과 과목 목록이 자동으로 연결되었습니다.',{exact:true}).waitFor();
 await button('저장 후 다음: 프로젝트 문서').click();
 await page.locator('input[type=file]').setInputFiles({name:'experience.txt',mimeType:'text/plain',buffer:Buffer.from('제가 React로 행사 신청 화면과 입력 검증을 구현했습니다.\n팀원 민수는 Docker로 배포 환경을 구성했습니다.\n제가 SQL로 신청 데이터 조회 쿼리를 작성했습니다.\n제가 Python으로 통계를 정리했습니다.')});
 await poll(()=>button('다음: 이수 과목').isEnabled(),'document ready');await button('다음: 이수 과목').click();
 await button('이수 선택 확인').click();await page.waitForURL('**/input/review');await readyReview();await cleanCopy();
 await fixture({failure:true});await button('프로젝트 경험 분석 실행').click();
 await page.getByRole('alert').filter({hasText:'프로젝트 경험 분석을 완료하지 못했습니다.'}).waitFor();await readyReview();
 await fixture({failure:false,partial:true});await button('프로젝트 경험 분석 실행').click();
 await poll(()=>page.locator('.skill-card').count().then(n=>n===4),'partial cards');await readyReview();
 assert.equal(await page.locator('section[aria-busy]').getByRole('alert').count(),0);assert.equal(await page.locator('.project-evidence').count(),0);
 assert.equal(await card('React').getByRole('heading',{level:3}).innerText(),'제가 React로 행사 신청 화면과 입력 검증을 구현했습니다.');
 assert.ok((await card('Docker').innerText()).includes('팀 수행'));await cleanCopy();
 assert.equal(await card('React').getByRole('button').count(),4);
 console.log('PASS: whole analysis failure/retry, partial-success cards without removed notices, task titles, team/personal distinction, four answer buttons');

 await card('React').getByRole('button',{name:'맞아요',exact:true}).click();await readyReview();assert.ok((await card('React').innerText()).includes('본인 경험으로 확인'));
 await card('SQL').getByRole('button',{name:'잘 모르겠어요',exact:true}).click();await readyReview();assert.ok((await card('SQL').innerText()).includes('판단 보류'));
 await card('Python').getByRole('button',{name:'이 기술 경험 없어요',exact:true}).click();await readyReview();assert.ok((await card('Python').innerText()).includes('경험 없다고 답변'));
 await card('Docker').getByRole('button',{name:'수정할게요',exact:true}).click();
 await card('Docker').getByLabel('기술명',{exact:true}).fill('Docker Compose');await card('Docker').locator('textarea').fill('배포 설정과 재시도 스크립트를 직접 작성했어요');
 await card('Docker').locator('select').selectOption('personal');
 await card('Docker').getByRole('button',{name:'수정 내용 저장',exact:true}).click();await readyReview();
 assert.equal(await card('Docker Compose').getByRole('heading',{level:3}).innerText(),'배포 설정과 재시도 스크립트를 직접 작성했어요');
 await page.reload();await readyReview();assert.equal(await card('Docker Compose').count(),1);assert.ok((await card('Docker Compose').innerText()).includes('본인 직접 수행'));
 await card('Docker Compose').getByRole('button',{name:'수정할게요',exact:true}).click();assert.equal(await card('Docker Compose').getByLabel('기술명',{exact:true}).inputValue(),'Docker Compose');await card('Docker Compose').getByRole('button',{name:'수정 취소',exact:true}).click();
 await page.route('**/project-experiences/*/confirmation',route=>route.fulfill({status:503,json:{message:'경험 답변 저장 재시도 검증'}}),{times:1});
 await card('React').getByRole('button',{name:'잘 모르겠어요',exact:true}).click();await page.getByRole('alert').filter({hasText:'경험 답변 저장 재시도 검증'}).waitFor();
 assert.ok((await card('React').innerText()).includes('본인 경험으로 확인'));
 await card('React').getByRole('button',{name:'잘 모르겠어요',exact:true}).click();await readyReview();assert.ok((await card('React').innerText()).includes('판단 보류'));
 await fixture({failure:true});await button('프로젝트 경험 재분석').click();await page.getByRole('alert').filter({hasText:'기존 분석 결과와 사용자 답변을 유지했습니다.'}).waitFor();
 assert.equal(await card('Docker Compose').count(),1);await fixture({failure:false});
 await page.reload();await readyReview();await page.addStyleTag({content:'nextjs-portal{display:none}'});await page.evaluate(()=>scrollTo(0,0));
 await page.screenshot({path:`${artifacts}/experience-cards.png`,fullPage:true});
 console.log('PASS: all four answer types, corrected task/skill/scope after reload, answer save retry, failed refresh preserves edits');

 const next=page.locator('footer.footer').getByRole('link',{name:'다음: 로드맵 결과',exact:true});assert.equal(await next.count(),1);assert.ok((await next.getAttribute('class')).includes('primary'));
 await next.click();await page.waitForURL('**/result');
 for(const name of ['준비 상태','직무 역량 비교','실행 로드맵','수강 후보','공모전·대외활동']){await page.getByRole('tab',{name,exact:true}).click();await cleanCopy();assert.equal(await page.locator('.result-summary>div').count(),1);}
 await compareTab();assert.ok((await editor().innerText()).includes('데이터 분석가'));
 await button('직무 분석 실행').click();await poll(()=>button('직무 분석 다시 실행').isEnabled(),'job analysis complete');
 await page.getByRole('tab',{name:'실행 로드맵',exact:true}).click();await button('로드맵 생성').click();
 await poll(async()=>(await page.locator('#result-panel').innerText()).includes('작업 완료'),'generated roadmap');
 for(const name of ['준비 상태','직무 역량 비교','실행 로드맵','수강 후보','공모전·대외활동']){await page.getByRole('tab',{name,exact:true}).click();await cleanCopy();assert.equal(await page.locator('.result-summary>div').count(),1);}
 assert.ok((await counters()).roadmap_fixture>0);
 console.log('PASS: one primary footer navigation, removed copy and no empty summary column before/after real roadmap persistence across all tabs');

 await compareTab();let before=await counters();let beforePaid=paid.length;
 await edit();await editor().getByRole('textbox',{name:/목표·관심 분야/}).fill('취소할 목표');let beforePatch=patches.length;
 await editor().getByRole('button',{name:'취소',exact:true}).click();assert.equal(patches.length,beforePatch);assert.ok((await editor().innerText()).includes('데이터 분석 분야의 프로젝트를 준비합니다'));
 await edit();await editor().getByRole('textbox',{name:/목표·관심 분야/}).fill('   ');await editor().getByRole('button',{name:'저장',exact:true}).click();
 await editor().getByRole('alert').waitFor();assert.equal(patches.length,beforePatch);
 await editor().getByRole('textbox',{name:/목표·관심 분야/}).fill('데이터 엔지니어로 성장하고 싶어요');
 await editor().getByRole('button',{name:'저장',exact:true}).click();await careerSaved();
 assert.deepEqual(patches.at(-1).changes,{career_goal:'데이터 엔지니어로 성장하고 싶어요'});
 assert.equal(await page.getByRole('tab',{name:'직무 역량 비교',exact:true}).getAttribute('aria-selected'),'true');
 assert.equal(await page.locator('.job-skills .skill-card').count(),0,'old skills are not attributed to new goal');
 assert.equal(await button('직무 분석 다시 실행').count(),1);
 assert.deepEqual(await counters(),before);assert.equal(paid.length,beforePaid);
 const tab=await context.newPage();await tab.goto(origin+'/input/basic');assert.equal(await tab.locator('[name=career_goal]').inputValue(),'데이터 엔지니어로 성장하고 싶어요');
 await edit();await editor().getByRole('textbox',{name:/희망 직무/}).fill('');await editor().getByRole('button',{name:'저장',exact:true}).click();await careerSaved();
 assert.deepEqual(patches.at(-1).changes,{target_role:null});assert.equal((await plan()).input.target_role,null);assert.equal(paid.length,beforePaid);
 console.log('PASS: cancel/required goal, changed-fields-only PATCH, optional empty role, tab retained, BasicForm reload consistency, save invokes no AI and clears old analysis');

 await edit();await editor().getByRole('textbox',{name:/목표·관심 분야/}).fill('충돌 전 작성한 목표');
 await tab.reload();await tab.locator('[name=target_role]').fill('다른 탭에서 저장한 직무');await tab.getByRole('button',{name:'저장',exact:true}).click();await tab.getByRole('status').filter({hasText:'저장되었습니다.'}).waitFor();
 await editor().getByRole('button',{name:'저장',exact:true}).click();await editor().getByRole('alert').filter({hasText:'다른 화면에서 정보가 변경'}).waitFor();
 assert.equal((await plan()).input.career_goal,'데이터 엔지니어로 성장하고 싶어요');assert.equal(await editor().getByRole('textbox',{name:/목표·관심 분야/}).inputValue(),'충돌 전 작성한 목표');
 await editor().getByRole('button',{name:'최신 정보 불러오기',exact:true}).click();
 await poll(()=>editor().getByRole('button',{name:'저장',exact:true}).isEnabled(),'conflict refresh');assert.equal(await editor().getByRole('textbox',{name:/희망 직무/}).inputValue(),'다른 탭에서 저장한 직무');
 await editor().getByRole('textbox',{name:/목표·관심 분야/}).fill('최신 진로로 데이터 파이프라인을 개발합니다');
 await page.route(/\/api\/roadmap-inputs\/[\da-f-]+$/,route=>route.request().method()==='PATCH'?route.fulfill({status:503,json:{message:'진로 저장 일시 실패'}}):route.continue(),{times:1});
 // Match only PATCH; the real request still checks expected_input_revision on retry.
 await editor().getByRole('button',{name:'저장',exact:true}).click();await editor().getByRole('alert').filter({hasText:'진로 저장 일시 실패'}).waitFor();
 assert.equal(await editor().getByRole('textbox',{name:/목표·관심 분야/}).inputValue(),'최신 진로로 데이터 파이프라인을 개발합니다');
 await editor().getByRole('button',{name:'저장',exact:true}).click();await careerSaved();assert.equal(paid.length,beforePaid);assert.deepEqual(await counters(),before);
 await tab.reload();assert.equal(await tab.locator('[name=career_goal]').inputValue(),'최신 진로로 데이터 파이프라인을 개발합니다');await tab.close();
 await button('직무 분석 다시 실행').click();await poll(()=>button('직무 분석 다시 실행').isEnabled(),'explicit reanalysis');assert.ok((await counters()).job_fixture>before.job_fixture);
 await cleanCopy();await page.addStyleTag({content:'nextjs-portal {display:none}'});
 await page.screenshot({path:`${artifacts}/career-desktop.png`,fullPage:true});
 for(const width of [390,320]){await page.setViewportSize({width,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const heading=await page.locator('.job-analysis-heading h3').boundingBox(),run=await button('직무 분석 다시 실행').boundingBox();assert.ok(run.y>=heading.y+heading.height||run.x>=heading.x+heading.width,'analysis heading/button do not overlap');await page.screenshot({path:`${artifacts}/career-${width}.png`,fullPage:true});}
 assert.deepEqual(errors,[]);console.log('PASS: real two-tab 409, draft retained, latest reload, save failure retry, explicit-only reanalysis, mobile layout');
 console.log('ALL EXPLORE BROWSER CHECKS PASSED');
}catch(error){await page.screenshot({path:`${artifacts}/failure.png`,fullPage:true}).catch(()=>{});console.error(await page.locator('body').innerText());throw error;}
finally{await context.close();await browser.close();}
