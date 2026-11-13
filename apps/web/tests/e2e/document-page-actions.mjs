// Real Next + document_upload_ui_server.py with disposable SQLite/storage.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.DOCUMENT_WEB_ORIGIN || 'http://localhost:15115';
const browser = await chromium.launch({ executablePath:process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless:true });

try {
 for (const viewport of [{width:1280,height:720},{width:390,height:844},{width:320,height:640}]) {
  const context = await browser.newContext({viewport});
  const errors = [], external = [];
  await context.route('**/*', route => {
   const host = new URL(route.request().url()).hostname;
   if (['localhost','127.0.0.1'].includes(host)) return route.continue();
   if (host === 'job-skills-test.supabase.co') return route.fulfill({json:{access_token:'test.token.value',refresh_token:'test-refresh',expires_in:3600,token_type:'bearer',user:{id:'12345678-0000-4000-8000-000000000001',is_anonymous:true,aud:'authenticated'}}});
   external.push(host); return route.abort();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const button = name => page.getByRole('button',{name,exact:true});
  const documents = () => page.evaluate(async () => {
   const response = await fetch('/api/roadmap-inputs/'+sessionStorage.getItem('roadmap_request_id')+'/documents');
   if (!response.ok) throw Error(await response.text());
   return response.json();
  });
  try {
   await page.goto(origin);
   await button('로그인 없이 시작하기').click();
   await page.waitForURL('**/input/basic');
   await page.goto(origin+'/input/documents');
   await page.getByText('등록된 문서가 없습니다.',{exact:true}).waitFor();
   assert.ok(await button('문서 없이 계속').isVisible());
   const footer = page.locator('.documents-footer-actions');
   const refresh = footer.getByRole('button',{name:'최신 상태 불러오기',exact:true});
   const next = footer.getByRole('button',{name:'다음: 이수 과목',exact:true});
   const a = await refresh.boundingBox(), b = await next.boundingBox();
   assert.ok(a.x+a.width <= b.x && Math.abs(a.y-b.y)<1,'refresh and next are adjacent');

   const fixture = await context.request.get(origin+'/api/document-upload-qa/partial-ocr.docx');
   assert.equal(fixture.status(),200);
   let release, started, held = false;
   const gate = new Promise(resolve=>{release=resolve;}), entered = new Promise(resolve=>{started=resolve;});
   await page.route('**/documents',async route=>{
    if (route.request().method()==='POST'&&!held) {held=true;started();await gate;}
    await route.continue();
   });
   try {
    await page.getByLabel('프로젝트 문서 선택').setInputFiles({name:'부분 추출.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:await fixture.body()});
    await entered;
    assert.equal(await button('문서 없이 계속').count(),0,'skip is hidden during an upload');
   } finally { release(); }
   const row = page.locator('[data-document-id]');
   await row.getByRole('button',{name:'읽힌 범위 확인',exact:true}).waitFor();
   await page.unroute('**/documents');
   let data = await documents();
   assert.equal(data.documents[0].extraction_status,'partial');
   assert.equal(data.documents[0].extraction_error_code,'ocr_disabled');
   assert.equal(data.documents[0].retry_available,true);
   assert.equal(await button('문서 없이 계속').count(),0);
   await row.getByRole('button',{name:'읽힌 범위 확인',exact:true}).click();
   const dialog = page.getByRole('dialog',{name:'일부만 읽힌 문서 확인',exact:true});
   await dialog.getByText('제가 프로젝트 API를 구현했습니다.',{exact:true}).waitFor();
   assert.equal(await dialog.getByText('읽힌 위치',{exact:true}).count(),0);
   await dialog.getByRole('button',{name:'읽힌 범위를 확인했어요',exact:true}).click();
   await dialog.waitFor({state:'detached'});
   await row.getByText('일부 추출 · 범위 확인됨',{exact:true}).waitFor();
   assert.equal(await row.getByRole('button',{name:'다시 읽기',exact:true}).isEnabled(),true);
   assert.equal(await next.isEnabled(),true);
   await page.reload();
   await row.getByText('일부 추출 · 범위 확인됨',{exact:true}).waitFor();
   assert.equal(await button('문서 없이 계속').count(),0);

   const retryResponse = page.waitForResponse(response=>response.url().endsWith('/retry-extraction')&&response.request().method()==='POST');
   await row.getByRole('button',{name:'다시 읽기',exact:true}).click();
   assert.equal((await retryResponse).status(),202);
   await row.getByText('일부만 읽힘 · 확인 필요',{exact:true}).waitFor();
   data = await documents();
   assert.equal(data.documents[0].extraction_revision,2);
   assert.equal(data.documents[0].partial_confirmed_at,null);
   assert.equal(await button('문서 없이 계속').count(),0);
   page.once('dialog',dialog=>dialog.accept());
   await row.getByRole('button',{name:'삭제',exact:true}).click();
   await page.getByText('등록된 문서가 없습니다.',{exact:true}).waitFor();
   assert.ok(await button('문서 없이 계속').isVisible());
   await page.getByLabel('프로젝트 문서 선택').setInputFiles({name:'지원하지않음.png',mimeType:'image/png',buffer:Buffer.from('not uploaded')});
   await page.locator('[data-upload-status=failed]').waitFor();
   assert.ok(await button('문서 없이 계속').isVisible(),'a rejected file does not count as an uploaded document');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
   console.log(`PASS ${viewport.width}×${viewport.height}: partial review/retry, OCR protection, upload/empty states and footer`);
  } finally { await context.close(); }
 }
} finally { await browser.close(); }
