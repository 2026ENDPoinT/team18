// Real Next UI with synthetic browser responses; no providers or database are used.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { installRoadmapMock } from './roadmap.mock.mjs';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.JOB_SKILLS_WEB_ORIGIN || 'http://localhost:15101';
const artifacts = process.env.ROADMAP_ARTIFACTS || '/tmp/team18-roadmap-ui';
mkdirSync(artifacts, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(installRoadmapMock);
const page = await context.newPage(), errors = [];
page.on('pageerror', error => errors.push(error.message));
const button = name => page.getByRole('button', { name, exact: true });
const noExecutionUI = async () => {
 for (const name of ['현재 입력으로 다시 분석', '저장 결과 새로고침', '이 작업 완료로 표시']) assert.equal(await button(name).count(), 0);
 assert.equal(await page.locator('.next-task,.roadmap-tasks,.roadmap-history,.history-result').count(), 0);
 assert.equal(await page.locator('a[href*="view=steps"]').count(), 0);
};
const refreshSaved = async () => {
 await page.evaluate(() => sessionStorage.setItem('roadmap-test-state', JSON.stringify(mockRoadmap)));
 await page.reload();
};
try {
 await page.goto(origin + '/result');
 await page.getByText('아직 수강 추천이 없어요.', { exact: true }).waitFor();
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 0);
 await page.getByRole('link', { name: '로드맵 생성하러 가기 →', exact: true }).click();
 await page.waitForURL('**/result?tab=courses');
 await button('로드맵 생성').click();
 await page.getByRole('alert').filter({ hasText: '직무 분석을 먼저 실행해 주세요.' }).waitFor();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 0);
 await page.evaluate(() => { mockRoadmap.jobAvailable = true; mockRoadmap.limited = true; });
 await button('로드맵 생성').click();
 await page.getByRole('alert').filter({ hasText: 'Gemini 사용량 제한' }).waitFor();
 await page.evaluate(() => { mockRoadmap.limited = false; });
 await button('로드맵 생성').click();
 await page.locator('.course-candidates-list h3').filter({ hasText: '데이터베이스' }).waitFor();
 assert.equal(new URL(page.url()).search, '?tab=courses');
 assert.equal(await button('로드맵 생성').count(), 0);
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1);
 await page.locator('.course-learning summary').click();
 await page.getByText('공식 학습 내용이 제공되지 않았습니다.', { exact: true }).waitFor();
 await page.reload();
 await page.locator('.course-candidates-list').waitFor();
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1);
 await page.goto(origin + '/result?tab=roadmap&view=steps');
 await page.locator('.result-overview .result-course-summary h3').waitFor();
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1);
 await page.getByRole('tab', { name: '수강 후보', exact: true }).click();
 await page.locator('.course-candidates-list').waitFor();
 await page.evaluate(() => { mockRoadmap.revision++; });
 await refreshSaved();
 await page.getByText('이 수강 후보는 이전 입력·분석 기준으로 저장된 결과입니다.', { exact: true }).waitFor();
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1);
 for (const width of [1440, 390]) {
  await page.setViewportSize({ width, height: 900 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: `${artifacts}/courses-${width}.png`, fullPage: true });
 }
 await page.evaluate(() => { mockRoadmap.removed = true; mockRoadmap.revision++; });
 await refreshSaved();
 await page.getByText('문서 삭제·재추출 등으로 근거가 변경되어 저장된 수강 후보의 상세 내용을 확인할 수 없습니다.', { exact: true }).waitFor();
 assert.equal(await page.locator('.course-candidates-list').count(), 0);
 await noExecutionUI();
 assert.equal(await page.evaluate(() => mockRoadmap.patches), 0);
 assert.equal(await page.evaluate(() => mockRoadmap.posts), 1);
 assert.deepEqual(errors, []);
 console.log('PASS: initial generation and retry, saved courses and learning details, no reanalysis/refresh/task/history UI, legacy URL shows summary, no implicit writes, stale/restricted results, desktop/mobile');
} finally { await context.close(); await browser.close(); }
