// Real Next UI, synthetic saved results; no external services are contacted.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RESULT_WEB_ORIGIN || 'http://localhost:15146';
const browser = await chromium.launch({ executablePath: process.env.P5_BROWSER || '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser', headless: true });
const input = { career_goal: '데이터 분석', target_role: '데이터 분석가' };
const plan = { request_id: 'test-plan', input_revision: 1, input };

try {
  const width = 1440;
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  const requests = [], errors = [];
  let count = 32;
  const skillName = i => `분석 기술 ${i + 1}`;
  const activityName = i => `데이터 분석 ${i % 2 ? '대외활동' : '공모전'} ${i + 1}`;
  const comparison = () => ({ ...input, input_revision: 1, comparisons: [], job_analysis: {
   status: 'success', snapshot_id: 'pagination-snapshot', canonical_role: input.target_role,
   skills: Array.from({ length: count }, (_, i) => ({ name: skillName(i), category: 'other',
    mentioned_job_count: 1, mention_frequency: 1, required_job_count: 1, preferred_job_count: 0,
    mentioned_only_job_count: 0, unknown_job_count: 0, direct_job_count: 1, related_job_count: 0,
    seniority_distribution: { unknown: 1 }, evidence: [],
   })),
  } });
  const activities = () => ({ request_id: plan.request_id, status: 'success', sources: [],
   activities: Array.from({ length: count }, (_, i) => ({ id: `activity-${i}`, title: activityName(i),
    source: 'contestkorea', source_label: '콘테스트코리아', kind: i % 2 ? 'extracurricular' : 'competition',
    status: 'open', target: '대학생', reasons: ['데이터 분석 목표와 관련된 활동입니다.'],
    url: `https://example.com/activity/${i}`, deadline_label: '접수 중', period: '테스트 접수 기간',
   })),
  });
  const result = () => ({ ...plan, run_id: 'pagination-run', status: 'success', generation_complete: true,
   roadmap: [], recommended_courses: [], skill_comparison: comparison(), activity_recommendations: activities(),
   basis: { review_status: 'confirmed', outside_completed_courses: [] },
  });
  await context.addInitScript(() => {
   localStorage.setItem('sb-job-skills-test-auth-token', JSON.stringify({ access_token: 'test.token.value', refresh_token: 'test-refresh', expires_at: Math.floor(Date.now() / 1000) + 3600, expires_in: 3600, token_type: 'bearer', user: { id: 'test-user', is_anonymous: true } }));
   sessionStorage.setItem('roadmap_request_id', 'test-plan');
   sessionStorage.setItem('roadmap_request_owner', 'test-user');
  });
  await context.route('https://**', route => route.abort());
  await context.route('**/api/**', route => {
   const request = route.request(), path = new URL(request.url()).pathname;
   requests.push({ method: request.method(), path });
   const json = path.endsWith('/roadmap') || path.includes('/roadmaps/') ? result()
    : path.endsWith('/skill-comparison') ? comparison()
    : path.endsWith('/activities') ? activities()
    : path.endsWith('/courses') ? { selected_courses: [] } : plan;
   return route.fulfill({ json });
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  try {
   for (const [tab, label, selector, name] of [
    ['skills', '직무 역량', '.job-skills', skillName],
    ['activities', '공모전·대외활동', '.activity-recommendations', activityName],
   ]) {
    await page.goto(`${origin}/result?tab=${tab}`);
    const panel = page.locator(selector), list = panel.getByRole('list', { name: `${label} 목록`, exact: true });
    const select = panel.getByRole('combobox', { name: `${label} 표시 개수`, exact: true });
    const nav = panel.getByRole('navigation', { name: `${label} 페이지 이동`, exact: true });
    const previous = nav.getByRole('button', { name: `${label} 이전 페이지`, exact: true });
    const next = nav.getByRole('button', { name: `${label} 다음 페이지`, exact: true });
    const headings = () => list.locator('.skill-title h3').allTextContents();
    const expected = (start, length) => Array.from({ length }, (_, i) => name(start + i));
    await select.waitFor();
    assert.equal(await select.inputValue(), '5');
    assert.deepEqual(await headings(), expected(0, 5));
    assert.equal(await previous.isDisabled(), true);
    const before = requests.length;
    await next.click();
    assert.deepEqual(await headings(), expected(5, 5));
    assert.equal(await nav.locator('[aria-current=page]').innerText(), '2');
    assert.match(await panel.locator('.result-list-toolbar [role=status]').innerText(), /6–10개 · 2 \/ 7페이지/);
    assert.equal(await panel.locator('.result-list-toolbar [role=status]').evaluate(el => el === document.activeElement), true);
    assert.ok((await panel.locator('.result-list-toolbar').boundingBox()).y >= 0);
    await previous.click();
    assert.deepEqual(await headings(), expected(0, 5));
    await nav.getByRole('button', { name: `${label} 5페이지`, exact: true }).click();
    assert.deepEqual(await headings(), expected(20, 5));
    await nav.getByRole('button', { name: `${label} 7페이지`, exact: true }).click();
    assert.deepEqual(await headings(), expected(30, 2));
    assert.equal(await next.isDisabled(), true);
    await select.selectOption('10');
    assert.deepEqual(await headings(), expected(0, 10));
    assert.equal(await previous.isDisabled(), true);
    await next.click();
    assert.deepEqual(await headings(), expected(10, 10));
    await nav.getByRole('button', { name: `${label} 4페이지`, exact: true }).click();
    assert.deepEqual(await headings(), expected(30, 2));
    assert.equal(await next.isDisabled(), true);
    await select.selectOption('5');
    assert.deepEqual(await headings(), expected(0, 5));
    assert.equal(requests.length, before, 'pagination only changes the displayed slice');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow');
    await next.click();
    await page.screenshot({ path: `/tmp/team18-pagination-${tab}-${width}.png` });
    await nav.screenshot({ path: `/tmp/team18-pagination-${tab}-${width}-controls.png` });
   }
   for (const size of [3, 0]) {
    count = size;
    for (const [tab, selector] of [['skills', '.job-skills'], ['activities', '.activity-recommendations']]) {
     await page.goto(`${origin}/result?tab=${tab}`);
     const panel = page.locator(selector);
     if (size) {
      await panel.locator('.paginated-results').waitFor();
      assert.equal(await panel.locator('.skill-card').count(), size);
      assert.equal(await panel.locator('.result-list-pagination button:disabled').count(), 2);
     } else {
      await panel.getByText(tab === 'skills' ? '분석한 공고에서 원문으로 확인할 수 있는 기술을 찾지 못했습니다.' : '현재 추천 조건에 맞는 공고가 없습니다. 목표 관련성, 접수 기간과 참가 대상을 확인한 공고만 표시합니다.', { exact: true }).waitFor();
      assert.equal(await panel.locator('.paginated-results').count(), 0);
     }
    }
   }
   assert.ok(requests.every(request => request.method === 'GET'), 'no generation or writes');
   assert.deepEqual(errors, []);
  } finally { await context.close(); }
 console.log('PASS: both lists, 5/10 items, previous/next/numbered pages, last-page boundaries, size reset, focus/scroll, short/empty results, desktop, no extra requests');
} finally { await browser.close(); }
