// Real Next UI, synthetic Gemini/API replies. Provider validation is tested in Python.
import assert from 'node:assert/strict';
import { installRoadmapMock } from './roadmap.mock.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RESULT_WEB_ORIGIN || 'http://localhost:15110';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(installRoadmapMock);
const page = await context.newPage(), errors = [];
page.on('pageerror', error => errors.push(error.message));
const reason = () => page.locator('.course-candidates-list .recommendation-reason');
const generated = () => reason().filter({ hasText: '데이터 분석 목표를 위해 데이터베이스에서 다루는 조회 개념' }).waitFor();
try {
 await page.goto(origin + '/result');
 await page.locator('.result-course-summary').getByText('아직 수강 추천이 없어요.', { exact: true }).waitFor();
 assert.equal(await page.evaluate(() => mockRoadmap.reasonRequests || 0), 0);
 await page.evaluate(() => { mockRoadmap.jobAvailable = true; mockRoadmap.holdReasons = true; });
 await page.getByRole('tab', { name: '수강 후보', exact: true }).click();
 await page.getByRole('button', { name: '로드맵 생성', exact: true }).click();
 await reason().filter({ hasText: '추천 이유를 작성하고 있어요' }).waitFor();
 await page.waitForFunction(() => typeof releaseReasons === 'function');
 assert.equal(await page.evaluate(() => mockRoadmap.reasonRequests), 1);
 await page.locator('.course-learning summary').click();
 await page.evaluate(() => { window.dispatchEvent(new Event('focus')); document.dispatchEvent(new Event('visibilitychange')); });
 assert.equal(await page.evaluate(() => mockRoadmap.reasonRequests), 1);
 await page.evaluate(() => releaseReasons()); await generated();
 assert.equal(await page.locator('.course-learning').getAttribute('open'), '');
 assert.ok(!(await reason().innerText()).includes('no_experience 응답 반영'));
 await page.getByRole('tab', { name: '실행 로드맵', exact: true }).click();
 await page.getByRole('tab', { name: '수강 후보', exact: true }).click(); await generated();
 assert.equal(await page.evaluate(() => mockRoadmap.reasonRequests), 1, 'tab visits reuse the client result');
 await page.reload(); await generated();
 assert.equal(await page.evaluate(() => mockRoadmap.reasonRequests), 2);
 assert.equal(await page.evaluate(() => mockRoadmap.reasonProviderCalls), 1, 'reload uses server cache');
 await page.evaluate(() => { mockRoadmap.reasonFailure = true; mockRoadmap.reasonCache = {}; sessionStorage.setItem('roadmap-test-state', JSON.stringify(mockRoadmap)); });
 await page.reload();
 await page.getByRole('alert').filter({ hasText: '추천 이유를 불러오지 못했어요' }).waitFor();
 assert.ok(!(await reason().innerText()).includes('no_experience 응답 반영'));
 assert.equal(await page.locator('.course-candidates-list h3').innerText(), '데이터베이스');
 await page.evaluate(() => { mockRoadmap.reasonFailure = false; });
 await page.getByRole('button', { name: '추천 이유 다시 불러오기', exact: true }).click(); await generated();
 for (const width of [1440, 390]) {
  await page.setViewportSize({ width, height: 900 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
 }
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1, 'reasons do not regenerate the roadmap');
 assert.deepEqual(errors, []);
 console.log('PASS: generated goal connection, loading/error/retry, cards preserved, no focus/tab duplicates, server cache on reload, no roadmap regeneration, desktop/mobile');
} finally { await context.close(); await browser.close(); }
